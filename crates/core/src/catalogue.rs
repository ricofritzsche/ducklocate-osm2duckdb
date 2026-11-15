use duckdb_neo::{
    DuckDBType, Result, ToValue,
    bind_arguments::BindArgument,
    connection::Context,
    data_chunk::DataChunkRef,
    extension::Extension,
    signature::SignatureBuilder,
    table_function::{
        BindFunctionHandle, ExecColumnInfo, InitColumnData, TableFunctionBuilder,
        TableFunctionCallbacks,
    },
    types::List,
};

struct Profiles;

impl TableFunctionCallbacks for Profiles {
    type BindData = ();
    type GlobalState = ();
    type LocalState = bool;

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
        bind.set_cardinality(1, true)?;
        Ok(())
    }

    fn init_local_state(
        &self,
        _context: &Context,
        _bind: &(),
        _global: Option<&()>,
        _columns: InitColumnData<'_>,
    ) -> Result<Option<bool>> {
        Ok(Some(false))
    }

    fn exec(
        &self,
        context: &Context,
        _bind: &(),
        local: Option<&mut bool>,
        _global: Option<&()>,
        mut output: DataChunkRef<'_>,
        _columns: ExecColumnInfo<'_>,
    ) -> Result<()> {
        let done = local.ok_or_else(|| duckdb_neo::Error::api_error("missing catalogue scan"))?;
        let count = usize::from(!*done);
        for col in 0..output.col_count() {
            output
                .get_vector_at_mut::<duckdb_neo::vector::Unknown>(col)?
                .set_size(count)?;
        }
        if *done {
            return Ok(());
        }
        let values = [
            "roads".value(context)?,
            crate::roads::PROFILE_VERSION.value(context)?,
            crate::roads::SCHEMA_VERSION.value(context)?,
            true.value(context)?,
            "Highway-tagged linear ways; excludes area=yes; no relations or routing topology"
                .value(context)?,
            List(vec![Some("LineString".to_owned())]).value(context)?,
        ];
        for (col, value) in values.into_iter().enumerate() {
            output
                .get_vector_at_mut::<duckdb_neo::vector::Unknown>(col)?
                .write_value_slow(0, &value)?;
        }
        *done = true;
        Ok(())
    }
}

pub(crate) fn register(extension: &Extension) -> Result<()> {
    TableFunctionBuilder::new("ducklocate_profiles", SignatureBuilder::new(), Profiles)
        .register(extension)
}
