//! Private immutable snapshot and bounded on-disk dependency resolution.
use crate::pbf::{self, Element, Way};
use duckdb_neo::{Error, Result};
use rusqlite::{Connection, OptionalExtension, params};
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::{Read, Write},
    path::Path,
};
use tempfile::TempDir;

pub(crate) const MAX_SOURCE: u64 = 512 * 1024 * 1024;
fn storage(error: impl std::fmt::Display) -> Error {
    Error::invalid_input(format!("source storage: {error}"))
}

pub(crate) struct Source {
    // Fields drop in order: close SQLite before removing its private directory.
    db: Connection,
    _directory: TempDir,
    pub hash: String,
}

impl Source {
    pub fn prepare(mut input: impl Read, expected: Option<&str>) -> Result<Self> {
        let directory = tempfile::Builder::new()
            .prefix("ducklocate-")
            .tempdir()
            .map_err(storage)?;
        let path = directory.path().join("snapshot.pbf");
        let mut file = File::create(&path).map_err(storage)?;
        let mut hasher = Sha256::new();
        let mut total = 0_u64;
        let mut buffer = [0_u8; 65536];
        loop {
            let n = input.read(&mut buffer).map_err(storage)?;
            if n == 0 {
                break;
            }
            total += n as u64;
            if total > MAX_SOURCE {
                return Err(storage("resource limit: source exceeds 512 MiB"));
            }
            file.write_all(&buffer[..n]).map_err(storage)?;
            hasher.update(&buffer[..n]);
        }
        drop(file);
        let hash = format!("{:x}", hasher.finalize());
        if expected.is_some_and(|expected| expected != hash) {
            return Err(storage("expected_sha256 mismatch"));
        }
        let db = Connection::open(directory.path().join("index.sqlite")).map_err(storage)?;
        db.execute_batch("PRAGMA page_size=4096; PRAGMA max_page_count=524288;
            PRAGMA cache_size=-8192; PRAGMA mmap_size=0; PRAGMA temp_store=FILE;
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            CREATE TABLE identities(kind INTEGER,id INTEGER,PRIMARY KEY(kind,id)) WITHOUT ROWID;
            CREATE TABLE nodes(id INTEGER PRIMARY KEY,version INTEGER,x REAL NOT NULL,y REAL NOT NULL);
            CREATE TABLE ways(id INTEGER PRIMARY KEY,payload TEXT NOT NULL);
            BEGIN;").map_err(storage)?;
        let mut source = Self {
            db,
            _directory: directory,
            hash,
        };
        source.decode(&path)?;
        source
            .db
            .execute_batch("COMMIT; PRAGMA query_only=ON;")
            .map_err(storage)?;
        Ok(source)
    }

    fn decode(&mut self, path: &Path) -> Result<()> {
        let mut reader = std::io::BufReader::new(File::open(path).map_err(storage)?);
        let Some((kind, data)) = pbf::next_blob(&mut reader)? else {
            return Err(storage("missing PBF header"));
        };
        if kind != "OSMHeader" {
            return Err(storage("expected OSMHeader"));
        }
        pbf::header(&data)?;
        drop(data);
        let mut count = 0;
        while let Some((kind, data)) = pbf::next_blob(&mut reader)? {
            if kind != "OSMData" {
                return Err(storage("unsupported PBF block type"));
            }
            pbf::block(&data, |element| {
                count += 1;
                if count > 10_000_000 {
                    return Err(storage("resource limit: elements"));
                }
                self.insert(element)
            })?;
        }
        Ok(())
    }

    fn insert(&self, element: Element) -> Result<()> {
        let (kind, id) = match &element {
            Element::Node { id, .. } => (0, *id),
            Element::Way(w) => (1, w.id),
            Element::Relation(id) => (2, *id),
        };
        self.db
            .prepare_cached("INSERT INTO identities VALUES(?1,?2)")
            .map_err(storage)?
            .execute(params![kind, id])
            .map_err(|e| {
                storage(format!(
                    "duplicate/conflicting record or resource failure ({kind}/{id}): {e}"
                ))
            })?;
        match element {
            Element::Node { id, version, x, y } => {
                self.db
                    .prepare_cached("INSERT INTO nodes VALUES(?1,?2,?3,?4)")
                    .map_err(storage)?
                    .execute(params![id, version, x, y])
                    .map_err(storage)?;
            }
            Element::Way(way) if crate::roads::selected(&way) => {
                let json = serde_json::to_string(&way).map_err(storage)?;
                self.db
                    .prepare_cached("INSERT INTO ways VALUES(?1,?2)")
                    .map_err(storage)?
                    .execute(params![way.id, json])
                    .map_err(storage)?;
            }
            _ => (),
        }
        Ok(())
    }

    pub fn next_way(&self, after: Option<i64>) -> Result<Option<Way>> {
        let json: Option<String> = if let Some(id) = after {
            self.db
                .query_row(
                    "SELECT payload FROM ways WHERE id>?1 ORDER BY id LIMIT 1",
                    [id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(storage)?
        } else {
            self.db
                .query_row("SELECT payload FROM ways ORDER BY id LIMIT 1", [], |r| {
                    r.get(0)
                })
                .optional()
                .map_err(storage)?
        };
        json.map(|s| serde_json::from_str(&s).map_err(storage))
            .transpose()
    }

    pub fn node(&self, id: i64) -> Result<Option<(Option<i32>, f64, f64)>> {
        self.db
            .prepare_cached("SELECT version,x,y FROM nodes WHERE id=?1")
            .map_err(storage)?
            .query_row([id], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))
            .optional()
            .map_err(storage)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn hash_assertion_precedes_decode() {
        let error = Source::prepare(&b"not a PBF"[..], Some(&"0".repeat(64)))
            .err()
            .unwrap();
        assert!(error.message.contains("mismatch"));
    }
}
