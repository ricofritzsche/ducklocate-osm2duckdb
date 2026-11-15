//! Alternative to a CALL table function: return a SQL statement group to DuckDB.
//! No effects occur in this callback; DuckDB executes the generated group itself.
use duckdb_neo::{
    Error, Result,
    bind_arguments::BindArguments,
    connection::Context,
    extension::Extension,
    pragma_function::{PragmaFunctionBuilder, PragmaQueryCallbacks},
    signature::{FunctionParameter, SignatureBuilder},
};

struct TransactionProbe;

impl PragmaQueryCallbacks for TransactionProbe {
    fn query(&self, _context: &Context, args: BindArguments<'_>) -> Result<String> {
        let fail = args
            .value(0)?
            .and_then(|v| v.get::<bool>().transpose())
            .transpose()?
            .ok_or_else(|| Error::invalid_input("failure switch must not be NULL"))?;
        let second_write = if fail {
            "INSERT INTO ducklocate_probe_first VALUES (CAST('deliberate_failure' AS INTEGER));"
        } else {
            "CREATE TABLE ducklocate_probe_second AS SELECT 2 AS value;"
        };
        Ok(format!(
            "CREATE TABLE ducklocate_probe_first AS SELECT nextval('ducklocate_probe_write_witness')::INTEGER AS value; {second_write} SELECT 2 AS completed_tables;"
        ))
    }
}

pub(crate) fn register(extension: &Extension) -> Result<()> {
    PragmaFunctionBuilder::query(
        "ducklocate_probe_transaction",
        SignatureBuilder::new().param(FunctionParameter::new::<bool>("fail")),
        TransactionProbe,
    )
    .register(extension)
}
