fn main() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../configure/extension_version.txt");
    println!("cargo:rerun-if-changed={}", path.display());
    let identity = std::fs::read_to_string(path).unwrap_or_else(|_| "0.1.0-unpackaged".into());
    println!("cargo:rustc-env=DUCKLOCATE_VERSION={}", identity.trim());
}
