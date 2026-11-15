//! Shared coordinate path for SQL adapters and a future embedded CLI.
//!
//! Only the no-transform path and EPSG:4326 -> EPSG:3857 are qualified here.
//! The connection must already have the pinned Spatial extension loaded offline.
use duckdb_neo::{
    Error, Parameters, Result, ToValue,
    connection::{Connection, FFILink},
    logical_type::LogicalType,
    types::BlobValue,
    value::Value,
    vector::Unknown,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutputCrs {
    Wgs84,
    WebMercator,
}

impl OutputCrs {
    pub fn parse(name: &str) -> Result<Self> {
        match name {
            "EPSG:4326" => Ok(Self::Wgs84),
            "EPSG:3857" => Ok(Self::WebMercator),
            _ => Err(Error::invalid_input(
                "unsupported CRS: this foundation qualifies only EPSG:4326 and EPSG:3857",
            )),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::Wgs84 => "EPSG:4326",
            Self::WebMercator => "EPSG:3857",
        }
    }
}

/// Encode a finite WGS84 point in standard little-endian OGC WKB, longitude first.
/// This is an interchange representation, never a claim about DuckDB vector layout.
pub fn point_wkb(longitude: f64, latitude: f64) -> Result<Vec<u8>> {
    if !valid_wgs84(longitude, latitude) {
        return Err(Error::invalid_input("invalid WGS84 longitude/latitude"));
    }
    let mut wkb = Vec::with_capacity(21);
    wkb.push(1);
    wkb.extend_from_slice(&1_u32.to_le_bytes());
    wkb.extend_from_slice(&longitude.to_le_bytes());
    wkb.extend_from_slice(&latitude.to_le_bytes());
    Ok(wkb)
}

/// Convert standard WKB through DuckDB's validating cast, obtaining an owned
/// genuine GEOMETRY value. No borrowed native storage escapes this call.
pub fn geometry_from_wkb(link: &impl FFILink, wkb: Vec<u8>) -> Result<Value> {
    let geometry_type = LogicalType::from_text(link, "GEOMETRY")?;
    link.value_cast(&BlobValue(wkb).value(link)?, &geometry_type)
}

/// Transform an assembled geometry exactly once. The default returns it intact.
/// Explicit projection delegates to Spatial/PROJ with bound parameters and XY.
/// The caller owns the connection; this method neither opens a database nor writes.
pub fn transform_geometry(
    connection: &Connection,
    geometry: Value,
    target: OutputCrs,
) -> Result<Value> {
    if target == OutputCrs::Wgs84 {
        return Ok(geometry);
    }
    let source = "EPSG:4326";
    let target = target.name();
    let mut result = connection.query(
        "SELECT g, ST_AsWKB(g) FROM (SELECT ST_Transform($1, $2, $3, always_xy := true) AS g)",
        Parameters::positional(&[&geometry, &source, &target]),
    )?;
    let chunk = result
        .next_chunk()?
        .ok_or_else(|| Error::api_error("Spatial returned no geometry"))?;
    let wkb = chunk
        .get_vector_at::<Unknown>(1)?
        .get_value_slow(0)?
        .get::<BlobValue>()?;
    if !wkb.is_some_and(|wkb| finite_wkb(&wkb.0)) {
        return Err(Error::invalid_input(
            "transformation_failed: non-finite output coordinates",
        ));
    }
    chunk.get_vector_at::<Unknown>(0)?.get_value_slow(0)
}

pub(crate) fn valid_wgs84(x: f64, y: f64) -> bool {
    x.is_finite() && y.is_finite() && (-180.0..=180.0).contains(&x) && (-90.0..=90.0).contains(&y)
}

pub(crate) fn line_wkb(points: &[(f64, f64)]) -> Result<Vec<u8>> {
    if points.len() < 2 || points.iter().any(|(x, y)| !valid_wgs84(*x, *y)) {
        return Err(Error::invalid_input(
            "invalid_geometry: invalid line coordinates",
        ));
    }
    let mut wkb = Vec::with_capacity(9 + points.len() * 16);
    wkb.push(1);
    wkb.extend_from_slice(&2_u32.to_le_bytes());
    wkb.extend_from_slice(&(points.len() as u32).to_le_bytes());
    for (x, y) in points {
        wkb.extend_from_slice(&x.to_le_bytes());
        wkb.extend_from_slice(&y.to_le_bytes());
    }
    Ok(wkb)
}

/// Validate every coordinate of standard XY WKB, not merely its envelope.
/// Empty point NaN/NaN is the OGC empty encoding; partial NaNs are invalid.
fn finite_wkb(mut input: &[u8]) -> bool {
    fn take<const N: usize>(input: &mut &[u8]) -> Option<[u8; N]> {
        let bytes = input.get(..N)?.try_into().ok()?;
        *input = &input[N..];
        Some(bytes)
    }
    fn geometry(input: &mut &[u8], depth: u8) -> Option<()> {
        if depth > 32 {
            return None;
        }
        let le = match take::<1>(input)?[0] {
            0 => false,
            1 => true,
            _ => return None,
        };
        let u32_at = |input: &mut &[u8]| -> Option<u32> {
            let b = take(input)?;
            Some(if le {
                u32::from_le_bytes(b)
            } else {
                u32::from_be_bytes(b)
            })
        };
        let point = |input: &mut &[u8], empty: bool| -> Option<()> {
            let x = take(input)?;
            let y = take(input)?;
            let (x, y) = if le {
                (f64::from_le_bytes(x), f64::from_le_bytes(y))
            } else {
                (f64::from_be_bytes(x), f64::from_be_bytes(y))
            };
            (x.is_finite() && y.is_finite() || empty && x.is_nan() && y.is_nan()).then_some(())
        };
        let line = |input: &mut &[u8]| -> Option<()> {
            let n = u32_at(input)? as usize;
            if n > input.len() / 16 {
                return None;
            }
            for _ in 0..n {
                point(input, false)?;
            }
            Some(())
        };
        match u32_at(input)? {
            1 => point(input, true)?,
            2 => line(input)?,
            3 => {
                let n = u32_at(input)? as usize;
                if n > input.len() / 4 {
                    return None;
                }
                for _ in 0..n {
                    line(input)?;
                }
            }
            4..=7 => {
                let n = u32_at(input)? as usize;
                if n > input.len() / 5 {
                    return None;
                }
                for _ in 0..n {
                    geometry(input, depth + 1)?;
                }
            }
            _ => return None,
        }
        Some(())
    }
    geometry(&mut input, 0).is_some() && input.is_empty()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wkb_is_longitude_first_and_rejects_invalid_coordinates() -> Result<()> {
        // POINT(2 49), hand-encoded OGC WKB, independently visible in PROJ's example.
        assert_eq!(
            point_wkb(2.0, 49.0)?,
            [
                1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 64, 0, 0, 0, 0, 0, 128, 72, 64
            ]
        );
        for (x, y) in [
            (181.0, 0.0),
            (0.0, -91.0),
            (f64::NAN, 0.0),
            (0.0, f64::INFINITY),
        ] {
            assert!(point_wkb(x, y).is_err());
        }
        Ok(())
    }
    #[test]
    fn checks_every_vertex_not_just_bounds() {
        let mut wkb = vec![1, 2, 0, 0, 0, 3, 0, 0, 0];
        for (x, y) in [(2_f64, 49_f64), (3., 50.), (4., 51.)] {
            wkb.extend_from_slice(&x.to_le_bytes());
            wkb.extend_from_slice(&y.to_le_bytes());
        }
        assert!(finite_wkb(&wkb));
        wkb[25..33].copy_from_slice(&f64::NAN.to_le_bytes());
        assert!(!finite_wkb(&wkb));
        assert!(!finite_wkb(&wkb[..20]));
    }
}
