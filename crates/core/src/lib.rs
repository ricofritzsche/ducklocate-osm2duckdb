//! Shared Ducklocate functionality; the native crate only owns the entrypoint.
mod catalogue;
pub mod coordinates;
#[cfg(feature = "foundation-probes")]
mod probes;
#[cfg(feature = "foundation-probes")]
mod transaction_probe;

pub fn register(extension: &duckdb_neo::extension::Extension) -> duckdb_neo::Result<()> {
    catalogue::register(extension)?;
    #[cfg(feature = "foundation-probes")]
    {
        probes::register(extension)?;
        transaction_probe::register(extension)?;
    }
    Ok(())
}
