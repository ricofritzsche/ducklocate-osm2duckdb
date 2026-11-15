"""Refresh the footer identity from build inputs, including uncommitted changes."""
import hashlib
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
inputs = [root / name for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', 'Makefile', 'requirements-dev.txt', '.gitmodules')]
inputs.extend(sorted((root / 'crates').rglob('*.rs')))
inputs.extend(sorted((root / 'crates').rglob('Cargo.toml')))
inputs.extend(sorted((root / 'scripts').glob('*.py')))
digest = hashlib.sha256()
for path in inputs:
    digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes())
tooling = subprocess.check_output(['git', '-C', 'extension-ci-tools', 'rev-parse', 'HEAD'], cwd=root)
digest.update(tooling)
revision = subprocess.check_output(['git', 'rev-parse', '--short=10', 'HEAD'], cwd=root, text=True).strip()
# 32-byte metadata field; include source hash even before the local commit exists.
identity = f'0.1.0-{revision}-{digest.hexdigest()[:10]}'
(root / 'configure').mkdir(exist_ok=True)
(root / 'configure/extension_version.txt').write_text(identity)
