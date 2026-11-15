"""Inspect the PROJ database embedded in the hash-pinned local Spatial binary.

The payload was independently matched byte-for-byte to upstream proj_db.c at
Spatial a3dbcd1781ec26c3a1be9bd622be05b376d6f47a (Git blob a36ff67f...).
This is artifact inspection, not a supported SQL metadata API.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

root = Path(__file__).resolve().parents[1]
binary = (root / '.cache/spatial/spatial.duckdb_extension').read_bytes()
assert hashlib.sha256(binary).hexdigest() == '212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4'
database = binary[54775640:54775640 + 8302592]
sha = hashlib.sha256(database).hexdigest()
assert sha == 'eefcf24f76a86c617f9b3cec75babdad184ed5c4a3b8bee80ea29dc9846a20fc'
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'proj.db'
    path.write_bytes(database)
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        metadata = dict(conn.execute('SELECT key,value FROM metadata'))
print(json.dumps({'proj_db_sha256': sha, 'metadata': metadata}, indent=2))
