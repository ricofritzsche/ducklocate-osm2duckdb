//! Synthetic native boundary experiments, compiled only with foundation-probes.
//! No source files, OSM profiles, download or product import operations exist here.
use crate::coordinates::{self, OutputCrs};
mod fixture;
use duckdb_neo::{
    DuckDBType, Error, FromValue, Parameters, Result,
    bind_arguments::BindArgument,
    connection::{Connection, Context},
    data_chunk::DataChunkRef,
    environment::Environment,
    extension::Extension,
    instance::InstanceBuilder,
    logical_type::LogicalType,
    signature::{FunctionParameter, FunctionParameterKind, SignatureBuilder},
    table_function::{
        BindFunctionHandle, ExecColumnInfo, InitColumnData, TableFunctionBuilder,
        TableFunctionCallbacks,
    },
    types::{BlobValue, List, Map},
    value::Value,
    vector::Unknown,
};
use fixture::{Issue, SourceRef};

struct Probe;
struct Bound {
    count: usize,
    wide: bool,
    crs: OutputCrs,
    spatial_path: String,
    wkb: Vec<u8>,
}

// A cursor belongs to a fresh execution, never the reusable bind data.
// Connection is Send but not Sync; DuckDB lends local state to one worker only.
struct Scan {
    cursor: usize,
    geometry: Value,
    _connection: Connection,
}

fn required<T: FromValue>(args: &[BindArgument], index: usize) -> Result<T> {
    args.get(index)
        .and_then(|arg| arg.value.as_ref())
        .ok_or_else(|| Error::invalid_input("probe arguments must be bind-time constants"))?
        .get::<T>()?
        .ok_or_else(|| Error::invalid_input("probe arguments must not be NULL"))
}

impl TableFunctionCallbacks for Probe {
    type BindData = Bound;
    type LocalState = Scan;
    type GlobalState = ();

    fn bind(
        &self,
        context: &Context,
        args: Vec<BindArgument>,
        bind: BindFunctionHandle<'_>,
    ) -> Result<Bound> {
        let count: i64 = required(&args, 0)?;
        if !(0..=100_000).contains(&count) {
            return Err(Error::invalid_input(
                "probe count must be between 0 and 100000",
            ));
        }
        let shape: String = required(&args, 1)?;
        let wide = match shape.as_str() {
            "wide" => true,
            "id" => false,
            _ => return Err(Error::invalid_input("probe shape must be wide or id")),
        };
        let crs = OutputCrs::parse(&required::<String>(&args, 2)?)?;
        let spatial_path = required(&args, 3)?;
        let wkb = args
            .get(4)
            .and_then(|arg| arg.value.as_ref())
            .ok_or_else(|| Error::invalid_input("probe WKB must be a bind-time constant"))?
            .get::<BlobValue>()?
            .map(|blob| blob.0)
            .map(Ok)
            .unwrap_or_else(|| coordinates::point_wkb(2.0, 49.0))?;
        if wkb.len() > 1_048_576 {
            return Err(Error::invalid_input("probe WKB exceeds 1 MiB"));
        }
        bind.add_result_column("id", &i64::logical_type(context)?)?;
        if wide {
            bind.add_result_column("geometry", &LogicalType::from_text(context, "GEOMETRY")?)?;
            bind.add_result_column("geometry_crs", &String::logical_type(context)?)?;
            bind.add_result_column("tags", &Map::<String, String>::logical_type(context)?)?;
            bind.add_result_column("source_refs", &List::<SourceRef>::logical_type(context)?)?;
            bind.add_result_column("issues", &List::<Issue>::logical_type(context)?)?;
        }
        bind.set_cardinality(count as usize, true)?;
        Ok(Bound {
            count: count as usize,
            wide,
            crs,
            spatial_path,
            wkb,
        })
    }

    fn init_local_state(
        &self,
        context: &Context,
        bind: &Bound,
        _global: Option<&()>,
        _columns: InitColumnData<'_>,
    ) -> Result<Option<Scan>> {
        // Isolated in-memory engine used only for read-only Spatial transformations.
        // It cannot write to or participate in the calling transaction.
        let env = Environment::new()?;
        let instance = InstanceBuilder::new()
            .option("autoinstall_known_extensions", "false")
            .option("autoload_known_extensions", "false")
            .option("threads", "1")
            .build(&env)?;
        let connection = instance.connect()?;
        if bind.crs != OutputCrs::Wgs84 {
            // LOAD requires a literal; escape SQL string literals, never interpolate a CRS.
            let local_path = std::path::Path::new(&bind.spatial_path);
            if !local_path.is_absolute() || !local_path.is_file() {
                return Err(Error::invalid_input(
                    "local Spatial artifact not found; supply an absolute path",
                ));
            }
            let path = bind.spatial_path.replace('\'', "''");
            connection.execute(format!("LOAD '{path}'"), Parameters::None)?;
        }
        let geometry = coordinates::geometry_from_wkb(context, bind.wkb.clone())?;
        let geometry = coordinates::transform_geometry(&connection, geometry, bind.crs)?;
        Ok(Some(Scan {
            cursor: 0,
            geometry,
            _connection: connection,
        }))
    }

    fn exec(
        &self,
        context: &Context,
        bind: &Bound,
        local: Option<&mut Scan>,
        _global: Option<&()>,
        mut output: DataChunkRef<'_>,
        _columns: ExecColumnInfo<'_>,
    ) -> Result<()> {
        let scan = local.ok_or_else(|| Error::api_error("missing probe scan state"))?;
        // Deliberately small chunks exercise repeated exec and validity reset.
        let count = (bind.count - scan.cursor).min(output.capacity()?).min(127);
        for col in 0..output.col_count() {
            output.get_vector_at_mut::<Unknown>(col)?.set_size(count)?;
        }
        for row in 0..count {
            let id = scan.cursor + row;
            output
                .get_vector_at_mut::<i64>(0)?
                .writer()?
                .set(row, &(id as i64))?;
            if !bind.wide {
                continue;
            }
            fixture::write_row(context, &mut output, row, id, &scan.geometry, bind.crs)?;
        }
        scan.cursor += count;
        Ok(())
    }
}

pub(crate) fn register(extension: &Extension) -> Result<()> {
    TableFunctionBuilder::new(
        "ducklocate_probe_rows",
        SignatureBuilder::new()
            .param(FunctionParameter::new::<i64>("count"))
            .param(
                FunctionParameter::with_default("shape", "wide".to_owned())
                    .kind(FunctionParameterKind::Named),
            )
            .param(
                FunctionParameter::with_default("crs", "EPSG:4326".to_owned())
                    .kind(FunctionParameterKind::Named),
            )
            .param(
                FunctionParameter::with_default("spatial_path", "".to_owned())
                    .kind(FunctionParameterKind::Named),
            )
            .param(
                FunctionParameter::with_default("geometry_wkb", Option::<BlobValue>::None)
                    .kind(FunctionParameterKind::Named),
            ),
        Probe,
    )
    .register(extension)
}
