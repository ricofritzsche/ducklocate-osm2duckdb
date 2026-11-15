//! Snapshot PBF decoding, independent of roads selection and DuckDB vectors.
mod wire;
use duckdb_neo::Result;
use flate2::read::ZlibDecoder;
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    io::{Read, Seek},
};
use wire::{Message, bad, bytes, text, zigzag};

pub(crate) const MAX_BLOCK: usize = 32 * 1024 * 1024;
const MAX_REFS: usize = 10_000;

#[derive(Serialize, Deserialize)]
pub(crate) struct Way {
    pub id: i64,
    pub version: Option<i32>,
    pub tags: BTreeMap<String, String>,
    pub refs: Vec<i64>,
}

pub(crate) enum Element {
    Node {
        id: i64,
        version: Option<i32>,
        x: f64,
        y: f64,
    },
    Way(Way),
    Relation(i64),
}

/// Exactly one bounded blob per call. EOF is distinct from truncated framing.
pub(crate) fn next_blob(reader: &mut (impl Read + Seek)) -> Result<Option<(String, Vec<u8>)>> {
    let mut size = [0; 4];
    let n = reader.read(&mut size[..1]).map_err(bad)?;
    if n == 0 {
        return Ok(None);
    }
    reader.read_exact(&mut size[1..]).map_err(bad)?;
    let size = u32::from_be_bytes(size) as usize;
    if size == 0 || size >= 65536 {
        return Err(bad("blob header size"));
    }
    let mut data = vec![0; size];
    reader.read_exact(&mut data).map_err(bad)?;
    let header = Message::parse(&data)?;
    let kind = text(header.required_bytes(1)?)?.to_owned();
    let len = header.required_int(3)?;
    if len == 0 || len > MAX_BLOCK as u64 {
        return Err(bad("resource limit: encoded blob"));
    }
    let mut data = vec![0; len as usize];
    reader.read_exact(&mut data).map_err(bad)?;
    let blob = Message::parse(&data)?;
    if blob
        .values(4)
        .chain(blob.values(5))
        .chain(blob.values(6))
        .chain(blob.values(7))
        .next()
        .is_some()
    {
        return Err(bad("unsupported compression"));
    }
    let decoded = match (blob.bytes(1)?, blob.bytes(3)?) {
        (Some(raw), None) => {
            if let Some(size) = blob.int(2)?
                && size != raw.len() as u64
            {
                return Err(bad("raw size mismatch"));
            }
            raw.to_vec()
        }
        (None, Some(compressed)) => {
            let size = blob.required_int(2)?;
            if size > MAX_BLOCK as u64 {
                return Err(bad("resource limit: decompressed blob"));
            }
            let mut decoder = ZlibDecoder::new(compressed);
            let mut decoded = Vec::new();
            decoder
                .by_ref()
                .take(size + 1)
                .read_to_end(&mut decoded)
                .map_err(bad)?;
            if decoded.len() as u64 != size || decoder.total_in() != compressed.len() as u64 {
                return Err(bad("compressed size mismatch"));
            }
            decoded
        }
        _ => return Err(bad("expected one raw or zlib payload")),
    };
    Ok(Some((kind, decoded)))
}

pub(crate) fn header(data: &[u8]) -> Result<()> {
    let h = Message::parse(data)?;
    let mut schema = false;
    for f in h.values(4) {
        match text(bytes(f)?)? {
            "OsmSchema-V0.6" => schema = true,
            "DenseNodes" => (),
            _ => {
                return Err(bad(
                    "unsupported required feature (history/locations unsupported)",
                ));
            }
        }
    }
    if !schema {
        return Err(bad("missing OsmSchema-V0.6"));
    }
    Ok(())
}

fn string<'a>(table: &[&'a str], index: u64) -> Result<&'a str> {
    usize::try_from(index)
        .ok()
        .and_then(|i| table.get(i).copied())
        .ok_or_else(|| bad("string table index"))
}

fn tags(m: &Message<'_>, table: &[&str]) -> Result<BTreeMap<String, String>> {
    let keys = m.packed(2, 4096)?;
    let vals = m.packed(3, 4096)?;
    if keys.len() != vals.len() {
        return Err(bad("tag array lengths"));
    }
    tag_pairs(keys.into_iter().zip(vals), table)
}

fn tag_pairs(
    pairs: impl Iterator<Item = (u64, u64)>,
    table: &[&str],
) -> Result<BTreeMap<String, String>> {
    let mut result = BTreeMap::new();
    let mut size = 0;
    for (k, v) in pairs {
        let (k, v) = (string(table, k)?, string(table, v)?);
        size += k.len() + v.len();
        if result.len() >= 4096 || size > 65536 {
            return Err(bad("resource limit: tags"));
        }
        if result.insert(k.to_owned(), v.to_owned()).is_some() {
            return Err(bad("duplicate tag key"));
        }
    }
    Ok(result)
}

fn version(raw: Option<u64>) -> Result<Option<i32>> {
    raw.map(|n| {
        i32::try_from(n)
            .ok()
            .filter(|n| *n > 0)
            .ok_or_else(|| bad("invalid version"))
    })
    .transpose()
}

fn info(m: &Message<'_>) -> Result<Option<i32>> {
    m.bytes(4)?
        .map(|raw| {
            let i = Message::parse(raw)?;
            if i.int(6)?.is_some_and(|v| v != 1) {
                return Err(bad("deleted/invisible records unsupported"));
            }
            version(i.int(1)?)
        })
        .transpose()
        .map(Option::flatten)
}

fn delta(prev: &mut i64, raw: u64) -> Result<i64> {
    *prev = prev
        .checked_add(zigzag(raw))
        .ok_or_else(|| bad("delta overflow"))?;
    Ok(*prev)
}

struct Grid {
    granularity: i64,
    lon: i64,
    lat: i64,
}
impl Grid {
    fn coordinate(&self, raw: i64, offset: i64) -> Result<f64> {
        let nano = raw
            .checked_mul(self.granularity)
            .and_then(|n| n.checked_add(offset))
            .ok_or_else(|| bad("coordinate overflow"))?;
        Ok(nano as f64 * 1e-9)
    }
}

pub(crate) fn block(data: &[u8], mut emit: impl FnMut(Element) -> Result<()>) -> Result<()> {
    let m = Message::parse(data)?;
    let st = Message::parse(m.required_bytes(1)?)?;
    let mut table = Vec::new();
    for entry in st.values(1) {
        if table.len() >= 100_000 {
            return Err(bad("resource limit: string table"));
        }
        table.push(text(bytes(entry)?)?);
    }
    if table.first() != Some(&"") {
        return Err(bad("string table entry zero"));
    }
    let grid = Grid {
        granularity: m.int(17)?.unwrap_or(100) as i64,
        lon: m.int(20)?.unwrap_or(0) as i64,
        lat: m.int(19)?.unwrap_or(0) as i64,
    };
    if grid.granularity <= 0 || grid.granularity > i32::MAX as i64 {
        return Err(bad("granularity"));
    }
    for group in m.values(2) {
        let group = Message::parse(bytes(group)?)?;
        for raw in group.values(1) {
            let node = Message::parse(bytes(raw)?)?;
            tags(&node, &table)?;
            emit(Element::Node {
                id: zigzag(node.required_int(1)?),
                version: info(&node)?,
                x: grid.coordinate(zigzag(node.required_int(9)?), grid.lon)?,
                y: grid.coordinate(zigzag(node.required_int(8)?), grid.lat)?,
            })?;
        }
        if let Some(raw) = group.bytes(2)? {
            dense(raw, &table, &grid, &mut emit)?;
        }
        for raw in group.values(3) {
            let way = Message::parse(bytes(raw)?)?;
            if way.values(9).chain(way.values(10)).next().is_some() {
                return Err(bad("LocationsOnWays unsupported"));
            }
            let mut prev = 0;
            let refs = way
                .packed(8, MAX_REFS)?
                .into_iter()
                .map(|n| delta(&mut prev, n))
                .collect::<Result<Vec<_>>>()?;
            emit(Element::Way(Way {
                id: way.required_int(1)? as i64,
                version: info(&way)?,
                tags: tags(&way, &table)?,
                refs,
            }))?;
        }
        for raw in group.values(4) {
            let rel = Message::parse(bytes(raw)?)?;
            tags(&rel, &table)?;
            info(&rel)?;
            let roles = rel.packed(8, MAX_REFS)?;
            let members = rel.packed(9, MAX_REFS)?;
            let types = rel.packed(10, MAX_REFS)?;
            if roles.len() != members.len() || roles.len() != types.len() {
                return Err(bad("relation array lengths"));
            }
            let mut prev = 0;
            for ((role, member), kind) in roles.into_iter().zip(members).zip(types) {
                string(&table, role)?;
                delta(&mut prev, member)?;
                if kind > 2 {
                    return Err(bad("relation member type"));
                }
            }
            emit(Element::Relation(rel.required_int(1)? as i64))?;
        }
        if group.values(5).next().is_some() {
            return Err(bad("change groups unsupported"));
        }
    }
    Ok(())
}

fn dense(
    data: &[u8],
    table: &[&str],
    grid: &Grid,
    emit: &mut impl FnMut(Element) -> Result<()>,
) -> Result<()> {
    let m = Message::parse(data)?;
    let ids = m.packed(1, 1_000_000)?;
    let lats = m.packed(8, 1_000_000)?;
    let lons = m.packed(9, 1_000_000)?;
    if ids.len() != lats.len() || ids.len() != lons.len() {
        return Err(bad("dense coordinate array lengths"));
    }
    let versions = if let Some(raw) = m.bytes(5)? {
        let info = Message::parse(raw)?;
        // Validate all parallel metadata lengths even though only version is retained.
        for field in [1, 2, 3, 4, 5, 6] {
            let vals = info.packed(field, 1_000_000)?;
            if !vals.is_empty() && vals.len() != ids.len() {
                return Err(bad("dense metadata array lengths"));
            }
            if field == 6 && vals.iter().any(|v| *v != 1) {
                return Err(bad("deleted dense records unsupported"));
            }
        }
        info.packed(1, 1_000_000)?
    } else {
        Vec::new()
    };
    let kv = m.packed(10, 1_000_000)?;
    let mut kv = kv.iter().copied();
    let has_tags = kv.len() > 0;
    let (mut id, mut lat, mut lon) = (0, 0, 0);
    for (i, ((di, dy), dx)) in ids.into_iter().zip(lats).zip(lons).enumerate() {
        if has_tags {
            let mut pairs = Vec::new();
            loop {
                let k = kv
                    .next()
                    .ok_or_else(|| bad("missing dense tag terminator"))?;
                if k == 0 {
                    break;
                }
                if pairs.len() >= 4096 {
                    return Err(bad("resource limit: dense tags"));
                }
                let v = kv.next().ok_or_else(|| bad("odd dense tags"))?;
                pairs.push((k, v));
            }
            tag_pairs(pairs.into_iter(), table)?;
        }
        emit(Element::Node {
            id: delta(&mut id, di)?,
            version: version(versions.get(i).copied())?,
            x: grid.coordinate(delta(&mut lon, dx)?, grid.lon)?,
            y: grid.coordinate(delta(&mut lat, dy)?, grid.lat)?,
        })?;
    }
    if kv.next().is_some() {
        return Err(bad("extra dense tags"));
    }
    Ok(())
}
