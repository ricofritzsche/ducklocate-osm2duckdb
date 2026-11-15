"""Verify/recover the pinned Python environment, including partial upstream setup."""
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
runner_commit = '2ac8dbc012ddbd96a57dca37784fd8ee3c0eb021'


def verified():
    try:
        for package, version in [('duckdb', '2.0.0'), ('packaging', '26.3'), ('termcolor', '3.3.0')]:
            if metadata.version(package) != version:
                return False
        origin = json.loads(metadata.distribution('duckdb_sqllogictest').read_text('direct_url.json') or '{}')
        return origin.get('vcs_info', {}).get('commit_id') == runner_commit
    except metadata.PackageNotFoundError:
        return False


if not verified():
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'requirements-dev.txt')], check=True)
if not verified():
    raise SystemExit('Python dependencies do not match the recorded pins')
(root / 'configure/python-ready').touch()
print('Verified DuckDB 2.0.0 and pinned SQLLogicTest environment')
