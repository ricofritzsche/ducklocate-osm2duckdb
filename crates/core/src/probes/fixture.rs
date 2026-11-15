//! Synthetic nested values; no OSM interpretation rules.
use crate::coordinates::OutputCrs;
use duckdb_neo::{
    AsDuckDB, Result, ToValue,
    connection::Context,
    data_chunk::DataChunkRef,
    types::{List, Map},
    value::Value,
    vector::Unknown,
};

#[derive(AsDuckDB)]
pub(super) struct SourceRef {
    osm_type: String,
    osm_id: i64,
    osm_version: Option<i32>,
}

#[derive(AsDuckDB)]
pub(super) struct Issue {
    severity: String,
    code: String,
    field: Option<String>,
    raw_value: Option<String>,
    message: String,
}

pub(super) fn write_row(
    context: &Context,
    output: &mut DataChunkRef<'_>,
    row: usize,
    id: usize,
    geometry: &Value,
    crs: OutputCrs,
) -> Result<()> {
    let null = id % 3 == 1;
    if null {
        for col in 1..output.col_count() {
            output
                .get_vector_at_mut::<Unknown>(col)?
                .set_null_slow(row)?;
        }
        return Ok(());
    }
    output
        .get_vector_at_mut::<Unknown>(1)?
        .write_value_slow(row, geometry)?;
    output
        .get_vector_at_mut::<String>(2)?
        .writer()?
        .set(row, crs.name())?;
    let empty = id % 3 == 2;
    let tags = if empty {
        Map::default()
    } else {
        Map(vec![
            ("name".to_owned(), Some("synthetic 🦆".to_owned())),
            ("missing".to_owned(), None),
        ])
    };
    let refs = if empty {
        List(Vec::new())
    } else {
        List(vec![
            Some(SourceRef {
                osm_type: "node".to_owned(),
                osm_id: 42,
                osm_version: None,
            }),
            None,
        ])
    };
    let issues = if empty {
        List(Vec::new())
    } else {
        List(vec![Some(Issue {
            severity: "warning".to_owned(),
            code: "synthetic".to_owned(),
            field: None,
            raw_value: None,
            message: "test only".to_owned(),
        })])
    };
    for (col, value) in [
        (3, tags.value(context)?),
        (4, refs.value(context)?),
        (5, issues.value(context)?),
    ] {
        output
            .get_vector_at_mut::<Unknown>(col)?
            .write_value_slow(row, &value)?;
    }
    Ok(())
}
