"""Opt-in, offline real-PBF evaluation. Setup/downloads are deliberately separate.

Usage: configure/venv/bin/python3 scripts/evaluate_roads.py --help
Requires the pinned native runtime, locally installed Spatial and Osmium CLI.
Output must be a new directory outside the repository. Failures exit nonzero;
only a complete evaluation writes evaluation.json. Never run with Python -O.
"""
import argparse
import datetime
import errno
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

from roads_oracle import decode
from roads_eval_native import sha256
from roads_eval_compare import compare, reference_summary

ROOT = Path(__file__).resolve().parents[1]
SPATIAL_SHA = '212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4'


def storage(directory):
    logical = allocated = 0
    for path in directory.rglob('*'):
        try:
            if path.is_file():
                stat = path.stat()
                logical += stat.st_size
                allocated += stat.st_blocks * 512
        except FileNotFoundError:
            pass  # Cleanup/SQLite rename can race with a sample.
    return logical, allocated


def native_run(base, name, **options):
    run = Path(base['output']) / name
    run.mkdir()
    temp = run / 'tmp'
    temp.mkdir()
    spec = dict(base, task='materialize', mode='report', crs='EPSG:4326',
                expect_error=None, run=str(run), temp=str(temp))
    spec.update(options)
    (run / 'spec.json').write_text(json.dumps(spec, indent=2)+'\n')
    command = ['/usr/bin/time', '-l', '-o', str(run/'time.txt'), sys.executable,
               str(ROOT/'scripts/roads_eval_native.py'), str(run/'spec.json')]
    peak_logical = peak_allocated = peak_working = samples = 0
    with (run/'stdout.txt').open('w') as out, (run/'stderr.txt').open('w') as err:
        with subprocess.Popen(command, stdout=out, stderr=err,
                              env=dict(os.environ, TMPDIR=str(temp))) as process:
            while process.poll() is None:
                if (run/'projection.started').exists():
                    logical, allocated = storage(temp)
                    peak_logical = max(peak_logical, logical)
                    peak_allocated = max(peak_allocated, allocated)
                    working = logical
                    for file in run.glob('roads.duckdb*'):
                        try:
                            working += file.stat().st_size
                        except FileNotFoundError:
                            pass
                    peak_working = max(peak_working, working)
                    samples += 1
                time.sleep(0.02)
            assert process.returncode == 0, f'Native worker failed: {run}/stderr.txt'
    result = json.loads((run/'result.json').read_text())
    timing = (run/'time.txt').read_text()
    match = re.search(r'(\d+)\s+maximum resident set size', timing)
    assert match, f'No macOS process high-water RSS: {timing}'
    assert not any(p.is_file() for p in temp.rglob('*')), f'Temporary files leaked: {temp}'
    result.update(peak_process_rss_bytes=int(match[1]),
                  sampled_peak_temp_logical_bytes=peak_logical,
                  sampled_peak_temp_allocated_bytes=peak_allocated,
                  sampled_peak_working_logical_bytes=peak_working, samples=samples,
                  temp_cleanup=True)
    return result, spec


def main():
    if not __debug__:
        raise SystemExit('Assertions must remain enabled; do not use Python -O/PYTHONOPTIMIZE')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('expected_sha256')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--extension', type=Path, default=ROOT/'build/release/ducklocate.duckdb_extension')
    parser.add_argument('--osmium', default=shutil.which('osmium'))
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--source-manifest', type=Path)
    parser.add_argument('--require-network-denied', action='store_true')
    args = parser.parse_args()
    assert platform.system() == 'Darwin', 'Measurement worker currently qualifies macOS only'
    source, output = args.source.resolve(), args.output.resolve()
    expected = args.expected_sha256.lower()
    assert re.fullmatch('[0-9a-f]{64}', expected), 'Expected SHA-256 must be 64 hex digits'
    assert source.is_file() and source.stat().st_size <= 512*1024**2
    assert sha256(source) == expected, 'Source SHA-256 mismatch'
    assert not output.is_relative_to(ROOT), 'Keep generated results outside the repository'
    assert args.osmium, 'Install Osmium explicitly during setup'
    if args.require_network_denied:
        with socket.socket() as probe:
            probe.settimeout(1)
            denied = probe.connect_ex(('1.1.1.1', 443))
        assert denied in (errno.EPERM, errno.EACCES), f'OS network denial not proven: errno {denied}'
    output.mkdir(parents=True, exist_ok=False)
    spatial = ROOT/'.cache/spatial/spatial.duckdb_extension'
    assert sha256(spatial) == SPATIAL_SHA, 'Run explicit setup_spatial.py first'
    report = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source_sha256=expected, source_bytes=source.stat().st_size,
                  extension_sha256=sha256(args.extension), spatial_sha256=SPATIAL_SHA,
                  python=sys.version, platform=platform.platform(),
                  osmium_version=subprocess.check_output([args.osmium, '--version'], text=True),
                  osmium_sha256=sha256(args.osmium), network_denial_asserted=args.require_network_denied,
                  configuration=dict(threads=2, duckdb_memory_limit='256MB', sample_interval_seconds=0.02))
    if args.source_manifest:
        manifest = json.loads(args.source_manifest.read_text())
        assert manifest['sha256'] == expected and manifest['size_bytes'] == source.stat().st_size
        report['source_manifest'] = manifest
    report['fileinfo'] = json.loads(subprocess.check_output(
        [args.osmium, 'fileinfo', '-e', '-j', '--no-crc', str(source)], text=True))
    started = time.perf_counter()
    reference = output/'oracle.sqlite'
    print('Decoding independently with Osmium', flush=True)
    report['oracle'] = decode(source, reference, args.osmium)
    report['reference'] = reference_summary(reference, args.cases, expected)
    assert report['oracle']['counts']['selected'] == report['reference']['counts']['selected']
    for kind in ('node', 'way', 'relation'):
        assert report['oracle']['counts'][kind] == report['fileinfo']['data']['count'][kind+'s']
    report['oracle_seconds'] = time.perf_counter()-started
    (output/'reference.json').write_text(json.dumps(report, indent=2)+'\n')
    base = dict(output=str(output), source=str(source), sha256=expected,
                extension=str(args.extension.resolve()), spatial=str(spatial),
                extension_directory=str(ROOT/'.cache/roads-extensions'))
    print('Materializing complete report-mode table in isolated process', flush=True)
    report['materialization'], spec = native_run(base, 'materialize')
    report['comparison'] = compare(output/'materialize/roads.duckdb', reference, spec)
    rejected = report['reference']['rejected']
    print('Exercising complete fail mode and deterministic repeat', flush=True)
    report['fail_mode'], fail_spec = native_run(base, 'fail', mode='fail',
                                               expect_error=next(iter(rejected.values()), None))
    if not rejected:
        report['fail_comparison'] = compare(output/'fail/roads.duckdb', reference, fail_spec)
        assert report['fail_comparison']['logical_sha256'] == report['comparison']['logical_sha256']
    report['repeat'], _ = native_run(base, 'repeat', task='repeat')
    assert report['repeat']['rows'] == report['comparison']['rows']
    assert report['repeat']['logical_sha256'] == report['comparison']['logical_sha256']
    print('Materializing EPSG:3857 and checking every vertex against independent equations', flush=True)
    report['mercator'], mercator_spec = native_run(base, 'mercator', crs='EPSG:3857')
    report['mercator_comparison'] = compare(output/'mercator/roads.duckdb', reference, mercator_spec)
    assert sha256(source) == expected, 'Source changed during evaluation'
    report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (output/'evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: {output}/evaluation.json', flush=True)


if __name__ == '__main__':
    main()
