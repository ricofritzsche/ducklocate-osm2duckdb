//! Native schema and owned nested values; no OSM decoding or interpretation.
use crate::{
    coordinates::OutputCrs,
    roads::{Feature, Issue, PROFILE_VERSION, SCHEMA_VERSION, SourceRef},
};
use duckdb_neo::{
    DuckDBType, Result, ToValue,
    connection::Context,
    data_chunk::DataChunkRef,
    logical_type::LogicalType,
    table_function::BindFunctionHandle,
    types::{List, Map},
    value::Value,
    vector::Unknown,
};

pub(crate) fn schema(context: &Context, bind: &BindFunctionHandle<'_>) -> Result<()> {
    for (name, kind) in [
        ("feature_id", "VARCHAR"),
        ("osm_type", "VARCHAR"),
        ("osm_id", "BIGINT"),
        ("osm_version", "INTEGER"),
        ("name", "VARCHAR"),
        ("geometry", "GEOMETRY"),
        ("geometry_crs", "VARCHAR"),
    ] {
        bind.add_result_column(name, &LogicalType::from_text(context, kind)?)?;
    }
    bind.add_result_column("tags", &Map::<String, String>::logical_type(context)?)?;
    bind.add_result_column("source_refs", &List::<SourceRef>::logical_type(context)?)?;
    bind.add_result_column("status", &String::logical_type(context)?)?;
    bind.add_result_column("issues", &List::<Issue>::logical_type(context)?)?;
    for name in [
        "source_sha256",
        "profile_version",
        "schema_version",
        "extension_version",
        "road_class",
        "surface",
    ] {
        bind.add_result_column(name, &String::logical_type(context)?)?;
    }
    bind.add_result_column("max_speed_kmh", &f64::logical_type(context)?)?;
    bind.add_result_column("oneway", &String::logical_type(context)?)?;
    Ok(())
}

pub(crate) fn write(
    context: &Context,
    output: &mut DataChunkRef<'_>,
    row: usize,
    feature: Feature,
    geometry: Option<Value>,
    hash: &str,
    crs: OutputCrs,
) -> Result<()> {
    let w = feature.way;
    let values = [
        format!("roads:way:{}", w.id).value(context)?,
        "way".value(context)?,
        w.id.value(context)?,
        w.version.value(context)?,
        w.tags.get("name").cloned().value(context)?,
        geometry.unwrap_or(Option::<String>::None.value(context)?),
        crs.name().value(context)?,
        Map(w
            .tags
            .iter()
            .map(|(k, v)| (k.clone(), Some(v.clone())))
            .collect())
        .value(context)?,
        List(feature.refs.into_iter().map(Some).collect()).value(context)?,
        (if feature.rejected { "rejected" } else { "ok" }).value(context)?,
        List(feature.issues.into_iter().map(Some).collect()).value(context)?,
        hash.value(context)?,
        PROFILE_VERSION.value(context)?,
        SCHEMA_VERSION.value(context)?,
        env!("DUCKLOCATE_VERSION").value(context)?,
        w.tags.get("highway").cloned().value(context)?,
        w.tags.get("surface").cloned().value(context)?,
        feature.speed.value(context)?,
        feature.oneway.value(context)?,
    ];
    for (col, value) in values.into_iter().enumerate() {
        output
            .get_vector_at_mut::<Unknown>(col)?
            .write_value_slow(row, &value)?;
    }
    Ok(())
}
