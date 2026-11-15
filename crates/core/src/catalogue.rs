use duckdb_neo::{
    DuckDBType, Result,
    bind_arguments::BindArgument,
    connection::Context,
    data_chunk::DataChunkRef,
    extension::Extension,
    signature::SignatureBuilder,
    table_function::{
        BindFunctionHandle, ExecColumnInfo, TableFunctionBuilder, TableFunctionCallbacks,
    },
    types::List,
};

struct Profiles;

impl TableFunctionCallbacks for Profiles {
    type BindData = ();
    type GlobalState = ();
    type LocalState = ();

    fn bind(
        &self,
        context: &Context,
        _args: Vec<BindArgument>,
        bind: BindFunctionHandle<'_>,
    ) -> Result<()> {
        for name in ["profile", "profile_version", "schema_version"] {
            bind.add_result_column(name, &String::logical_type(context)?)?;
        }
        bind.add_result_column("is_default", &bool::logical_type(context)?)?;
        bind.add_result_column("description", &String::logical_type(context)?)?;
        bind.add_result_column("geometry_types", &List::<String>::logical_type(context)?)?;
        bind.set_cardinality(0, true)?;
        Ok(())
    }

    fn exec(
        &self,
        _context: &Context,
        _bind: &(),
        _local: Option<&mut ()>,
        _global: Option<&()>,
        mut output: DataChunkRef<'_>,
        _columns: ExecColumnInfo<'_>,
    ) -> Result<()> {
        output
            .get_vector_at_mut::<duckdb_neo::vector::Unknown>(0)?
            .set_size(0)
    }
}

pub(crate) fn register(extension: &Extension) -> Result<()> {
    TableFunctionBuilder::new("ducklocate_profiles", SignatureBuilder::new(), Profiles)
        .register(extension)
}
