//! Bounded, borrowed protobuf wire decoding. No generated graph of allocations.
use duckdb_neo::{Error, Result};

pub(super) fn bad(message: impl std::fmt::Display) -> Error {
    Error::invalid_input(format!("invalid PBF: {}", message))
}

#[derive(Clone, Copy)]
pub(super) enum Value<'a> {
    Int(u64),
    Bytes(&'a [u8]),
    Fixed,
}

pub(super) struct Message<'a>(Vec<(u32, Value<'a>)>);

pub(super) fn varint(input: &mut &[u8]) -> Result<u64> {
    let mut value = 0;
    for shift in (0..70).step_by(7) {
        let (&b, rest) = input.split_first().ok_or_else(|| bad("truncated varint"))?;
        *input = rest;
        if shift == 63 && b > 1 {
            return Err(bad("overflowing varint"));
        }
        value |= u64::from(b & 127) << shift;
        if b < 128 {
            return Ok(value);
        }
    }
    Err(bad("overflowing varint"))
}

fn take<'a>(input: &mut &'a [u8], len: usize) -> Result<&'a [u8]> {
    let bytes = input.get(..len).ok_or_else(|| bad("truncated field"))?;
    *input = &input[len..];
    Ok(bytes)
}

pub(super) fn zigzag(n: u64) -> i64 {
    ((n >> 1) as i64) ^ -((n & 1) as i64)
}

impl<'a> Message<'a> {
    pub(super) fn parse(mut input: &'a [u8]) -> Result<Self> {
        let mut fields = Vec::new();
        while !input.is_empty() {
            if fields.len() >= 1_000_000 {
                return Err(bad("resource limit: protobuf fields"));
            }
            let key = varint(&mut input)?;
            let number = u32::try_from(key >> 3).map_err(|_| bad("field number"))?;
            if number == 0 || number > 536_870_911 {
                return Err(bad("field number"));
            }
            let value = match key & 7 {
                0 => Value::Int(varint(&mut input)?),
                1 => {
                    take(&mut input, 8)?;
                    Value::Fixed
                }
                2 => {
                    let len = usize::try_from(varint(&mut input)?).map_err(|_| bad("length"))?;
                    Value::Bytes(take(&mut input, len)?)
                }
                5 => {
                    take(&mut input, 4)?;
                    Value::Fixed
                }
                _ => return Err(bad("unsupported wire type")),
            };
            fields.push((number, value));
        }
        Ok(Self(fields))
    }

    pub(super) fn values(&self, number: u32) -> impl Iterator<Item = Value<'a>> + '_ {
        self.0
            .iter()
            .filter(move |(n, _)| *n == number)
            .map(|(_, v)| *v)
    }

    fn one(&self, number: u32) -> Result<Option<Value<'a>>> {
        let mut values = self.values(number);
        let value = values.next();
        if values.next().is_some() {
            return Err(bad("duplicate singular field"));
        }
        Ok(value)
    }

    pub(super) fn int(&self, number: u32) -> Result<Option<u64>> {
        self.one(number)?
            .map(|v| match v {
                Value::Int(n) => Ok(n),
                _ => Err(bad("expected integer")),
            })
            .transpose()
    }

    pub(super) fn bytes(&self, number: u32) -> Result<Option<&'a [u8]>> {
        self.one(number)?.map(bytes).transpose()
    }

    pub(super) fn required_int(&self, number: u32) -> Result<u64> {
        self.int(number)?
            .ok_or_else(|| bad("missing required integer"))
    }

    pub(super) fn required_bytes(&self, number: u32) -> Result<&'a [u8]> {
        self.bytes(number)?
            .ok_or_else(|| bad("missing required bytes"))
    }

    pub(super) fn packed(&self, number: u32, limit: usize) -> Result<Vec<u64>> {
        let mut result = Vec::new();
        for value in self.values(number) {
            match value {
                Value::Int(n) => {
                    if result.len() >= limit {
                        return Err(bad("resource limit: packed field"));
                    }
                    result.push(n);
                }
                Value::Bytes(mut data) => {
                    while !data.is_empty() {
                        if result.len() >= limit {
                            return Err(bad("resource limit: packed field"));
                        }
                        result.push(varint(&mut data)?);
                    }
                }
                _ => return Err(bad("invalid packed field")),
            }
        }
        Ok(result)
    }
}

pub(super) fn bytes(value: Value<'_>) -> Result<&[u8]> {
    match value {
        Value::Bytes(b) => Ok(b),
        _ => Err(bad("expected bytes")),
    }
}

pub(super) fn text(value: &[u8]) -> Result<&str> {
    std::str::from_utf8(value).map_err(|_| bad("invalid UTF-8"))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn malformed_wire_is_an_error() {
        for input in [&[0][..], &[10, 4, 1], &[8, 128], &[15], &[255; 11]] {
            assert!(Message::parse(input).is_err());
        }
        assert!(Message::parse(&[8, 1, 8, 2]).unwrap().int(1).is_err());
    }
}
