"""Explicit setup acquisition. Reuse only the exact verified osx_arm64 artifact."""
import gzip
import hashlib
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
directory = root / '.cache/spatial'
directory.mkdir(parents=True, exist_ok=True)
artifact = directory / 'spatial.duckdb_extension'
compressed = directory / 'spatial.duckdb_extension.gz'
sha = '212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4'
gz_sha = '16dadc65e6eb5a212160070063b57cc0ded6ebc24cc8c20c401a17a9e0032cee'
if not artifact.exists() or hashlib.sha256(artifact.read_bytes()).hexdigest() != sha:
    if not compressed.exists() or hashlib.sha256(compressed.read_bytes()).hexdigest() != gz_sha:
        url = 'https://extensions.duckdb.org/v2.0.0/osx_arm64/spatial.duckdb_extension.gz'
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != gz_sha:
            raise SystemExit('Upstream Spatial bytes changed; review compatibility before updating pins')
        compressed.write_bytes(data)
    data = gzip.decompress(compressed.read_bytes())
    if hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit('Spatial checksum mismatch')
    artifact.write_bytes(data)
print(f'Verified Spatial: {artifact} sha256={sha}')
