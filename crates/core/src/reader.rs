//! SQL boundary: bind validation, execution-owned state, source access, chunks.
use crate::{
    coordinates::{self, OutputCrs},
    output, roads,
    source::{MAX_SOURCE, Source},
};
use duckdb_neo::{
    Error, FromValue, Parameters, Result,
    bind_arguments::BindArgument,
    connection::{Connection, Context},
    data_chunk::DataChunkRef,
    environment::Environment,
    extension::Extension,
    file::{File, FileBuilder, FileSystem},
    instance::InstanceBuilder,
    signature::{FunctionParameter, FunctionParameterKind, SignatureBuilder},
    table_function::{
        BindFunctionHandle, ExecColumnInfo, InitColumnData, TableFunctionBuilder,
        TableFunctionCallbacks,
    },
    vector::Unknown,
};
use std::io::Read;

struct Reader;
struct Bound {
    path: String,
    expected: Option<String>,
    report: bool,
    crs: OutputCrs,
}
struct Scan {
    source: Option<Source>,
    after: Option<i64>,
    transform: Option<Connection>,
}

fn required<T: FromValue>(args: &[BindArgument], index: usize) -> Result<T> {
    args.get(index)
        .and_then(|a| a.value.as_ref())
        .ok_or_else(|| Error::invalid_input("arguments must be bind-time constants"))?
        .get::<T>()?
        .ok_or_else(|| Error::invalid_input("arguments must not be NULL"))
}

struct Input(File);
impl Read for Input {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        self.0
            .read_into(buf)
            .map_err(|e| std::io::Error::other(e.message))
    }
}

fn transformer(context: &Context, crs: OutputCrs) -> Result<Option<Connection>> {
    if crs == OutputCrs::Wgs84 {
        return Ok(None);
    }
    let directory = context
        .config()?
        .get_value("extension_directory")?
        .0
        .get::<String>()?
        .ok_or_else(|| Error::invalid_input("missing extension_directory"))?;
    let env = Environment::new()?;
    let instance = InstanceBuilder::new()
        .option("autoinstall_known_extensions", "false")
        .option("autoload_known_extensions", "false")
        .option("threads", "1")
        .option("extension_directory", &directory)
        .build(&env)?;
    let connection = instance.connect()?;
    connection.execute("LOAD spatial", Parameters::None)?;
    {
        let mut result = connection.query(
            "SELECT extension_version, DuckDB_Proj_Version(), DuckDB_PROJ_Compiled_Version() FROM duckdb_extensions() WHERE extension_name='spatial' AND loaded",
            Parameters::None,
        )?;
        let chunk = result
            .next_chunk()?
            .ok_or_else(|| Error::invalid_input("Spatial identity unavailable"))?;
        for (col, expected) in [
            (0, "a3dbcd1781"),
            (1, "9.1.1"),
            (2, "Rel. 9.1.1, December 1st, 2022"),
        ] {
            if chunk.get_vector_at::<String>(col)?.reader()?.get(0)? != Some(expected) {
                return Err(Error::invalid_input(
                    "unqualified Spatial/PROJ version; require Spatial a3dbcd1781 with PROJ 9.1.1",
                ));
            }
        }
    }

    connection.execute("SET enable_external_access=false", Parameters::None)?;
    // Configuration/library errors are statement errors, even for an empty source.
    coordinates::transform_geometry(
        &connection,
        coordinates::geometry_from_wkb(&connection, coordinates::point_wkb(2., 49.)?)?,
        crs,
    )?;
    Ok(Some(connection))
}

impl TableFunctionCallbacks for Reader {
    type BindData = Bound;
    type GlobalState = ();
    type LocalState = Scan;
    fn bind(
        &self,
        context: &Context,
        args: Vec<BindArgument>,
        bind: BindFunctionHandle<'_>,
    ) -> Result<Bound> {
        let path: String = required(&args, 0)?;
        if path.is_empty() || path.chars().any(|c| ":*?[]\0".contains(c)) {
            return Err(Error::invalid_input(
                "path must be a non-empty local file without schemes or glob syntax",
            ));
        }
        if required::<String>(&args, 1)? != "roads" {
            return Err(Error::invalid_input(
                "unknown profile; only roads is installed",
            ));
        }
        if required::<String>(&args, 2)? != roads::PROFILE_VERSION {
            return Err(Error::invalid_input(
                "unknown profile_version; roads requires 1.0.0",
            ));
        }
        let expected = args
            .get(3)
            .and_then(|a| a.value.as_ref())
            .ok_or_else(|| Error::invalid_input("expected_sha256 must be constant"))?
            .get::<String>()?;
        if expected
            .as_ref()
            .is_some_and(|s| s.len() != 64 || !s.bytes().all(|b| b.is_ascii_hexdigit()))
        {
            return Err(Error::invalid_input(
                "expected_sha256 must contain exactly 64 hexadecimal digits",
            ));
        }
        let report = match required::<String>(&args, 4)?.as_str() {
            "fail" => false,
            "report" => true,
            _ => return Err(Error::invalid_input("on_error must be fail or report")),
        };
        let crs = OutputCrs::parse(&required::<String>(&args, 5)?)?;
        output::schema(context, &bind)?;
        Ok(Bound {
            path,
            expected: expected.map(|s| s.to_ascii_lowercase()),
            report,
            crs,
        })
    }
    fn init_local_state(
        &self,
        context: &Context,
        bind: &Bound,
        _global: Option<&()>,
        _columns: InitColumnData<'_>,
    ) -> Result<Option<Scan>> {
        let fs = FileSystem::new(context)?;
        if fs.is_remote(&bind.path)? {
            return Err(Error::invalid_input("remote input is unsupported"));
        }
        let path = fs.expand(&bind.path)?;
        // Require regular local input; actual byte access still goes through caller policy.
        if !std::fs::metadata(&path).is_ok_and(|m| m.is_file()) {
            return Err(Error::invalid_input(
                "input must be an existing regular local file",
            ));
        }
        let file = FileBuilder::new(&fs, &path)?.read().open()?;
        if file.size()? > MAX_SOURCE {
            return Err(Error::invalid_input(
                "resource limit: source exceeds 512 MiB",
            ));
        }
        let transform = transformer(context, bind.crs)?;
        let source = Source::prepare(Input(file), bind.expected.as_deref())?;
        Ok(Some(Scan {
            source: Some(source),
            after: None,
            transform,
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
        let scan = local.ok_or_else(|| Error::api_error("missing reader scan"))?;
        let limit = output.capacity()?.min(32);
        for col in 0..output.col_count() {
            output.get_vector_at_mut::<Unknown>(col)?.set_size(limit)?;
        }
        let mut count = 0;
        let result = (|| {
            if let Some(source) = scan.source.as_ref() {
                while count < limit {
                    let Some(way) = source.next_way(scan.after)? else {
                        break;
                    };
                    scan.after = Some(way.id);
                    let mut feature = roads::project(source, way, bind.crs, bind.report)?;
                    let mut geometry = None;
                    if !feature.rejected {
                        let value = coordinates::geometry_from_wkb(
                            context,
                            coordinates::line_wkb(&feature.points)?,
                        )?;
                        geometry = if let Some(connection) = &scan.transform {
                            match coordinates::transform_geometry(connection, value, bind.crs) {
                                Ok(g) => Some(g),
                                Err(e) if e.message.contains("transformation_failed:") => {
                                    feature.reject_transform(bind.report)?;
                                    None
                                }
                                Err(e) => return Err(e),
                            }
                        } else {
                            Some(value)
                        };
                    }
                    output::write(
                        context,
                        &mut output,
                        count,
                        feature,
                        geometry,
                        &source.hash,
                        bind.crs,
                    )?;
                    count += 1;
                }
            }
            Ok(())
        })();
        // Release disk storage immediately at EOF/error, also via Drop on LIMIT/cancel.
        if result.is_err() || count == 0 {
            scan.source.take();
        }
        result?;
        for col in 0..output.col_count() {
            output.get_vector_at_mut::<Unknown>(col)?.set_size(count)?;
        }
        Ok(())
    }
}

pub(crate) fn register(extension: &Extension) -> Result<()> {
    let named = |name, default: &str| {
        FunctionParameter::with_default(name, default.to_owned()).kind(FunctionParameterKind::Named)
    };
    let signature = SignatureBuilder::new()
        .param(FunctionParameter::new::<String>("path"))
        .param(named("profile", "roads"))
        .param(named("profile_version", roads::PROFILE_VERSION))
        .param(
            FunctionParameter::with_default("expected_sha256", Option::<String>::None)
                .kind(FunctionParameterKind::Named),
        )
        .param(named("on_error", "fail"))
        .param(named("crs", "EPSG:4326"));
    TableFunctionBuilder::new("ducklocate_read", signature, Reader).register(extension)
}
