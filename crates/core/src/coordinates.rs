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
    if !longitude.is_finite()
        || !latitude.is_finite()
        || !(-180.0..=180.0).contains(&longitude)
        || !(-90.0..=90.0).contains(&latitude)
    {
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
        "SELECT g, ST_IsEmpty(g) OR (isfinite(ST_XMin(g)) AND isfinite(ST_YMin(g)) \
         AND isfinite(ST_XMax(g)) AND isfinite(ST_YMax(g))) \
         FROM (SELECT ST_Transform($1, $2, $3, always_xy := true) AS g)",
        Parameters::positional(&[&geometry, &source, &target]),
    )?;
    let chunk = result
        .next_chunk()?
        .ok_or_else(|| Error::api_error("Spatial returned no geometry"))?;
    if chunk.get_vector_at::<bool>(1)?.reader()?.get(0)? != Some(&true) {
        return Err(Error::invalid_input(
            "transformation_failed: non-finite output coordinates",
        ));
    }
    chunk.get_vector_at::<Unknown>(0)?.get_value_slow(0)
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
}
