"""Reuse a verified shell or explicitly provision the official osx_arm64 runtime."""
import hashlib
import io
from pathlib import Path
import shutil
import tarfile
import urllib.request

root = Path(__file__).resolve().parents[1]
sha = '432e9c8012d0259e7c4630fa2136bf59fb832769ca7e0f6e374b8af2d2cebed9'
archive_sha = '188a36fe8883ef52e69165a0cbb6031ef679c8e6c448a1ce22951964149b7f96'
local = root / '.cache/bin/duckdb'
for candidate in [shutil.which('duckdb'), local]:
    if candidate and Path(candidate).is_file() and hashlib.sha256(Path(candidate).read_bytes()).hexdigest() == sha:
        print(f'Verified DuckDB v2.0.0 osx_arm64: {candidate}')
        break
else:
    archive = root / '.cache/duckdb-cli-osx-arm64.tar.gz'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != archive_sha:
        data = urllib.request.urlopen('https://github.com/duckdb/duckdb/releases/download/v2.0.0/duckdb-cli-osx-arm64.tar.gz', timeout=60).read()
        if hashlib.sha256(data).hexdigest() != archive_sha:
            raise SystemExit('DuckDB archive checksum mismatch')
        archive.write_bytes(data)
    with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as package:
        member = package.extractfile('duckdb')
        if member is None:
            raise SystemExit('No shell in verified archive')
        data = member.read()
    if hashlib.sha256(data).hexdigest() != sha:
        raise SystemExit('DuckDB shell checksum mismatch')
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)
    local.chmod(0o755)
    print(f'Verified DuckDB v2.0.0 osx_arm64: {local}')
