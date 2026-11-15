"""Independent public SQL acceptance for roads 1.0.0; called in all build modes."""
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import threading
import time

from make_roads_fixtures import encode, frame, blob, integer, packed, dense_field_fixtures

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'test/fixtures/roads'
SCHEMA = [
    ('feature_id', 'VARCHAR'), ('osm_type', 'VARCHAR'), ('osm_id', 'BIGINT'),
    ('osm_version', 'INTEGER'), ('name', 'VARCHAR'), ('geometry', 'GEOMETRY'),
    ('geometry_crs', 'VARCHAR'), ('tags', 'MAP(VARCHAR, VARCHAR)'),
    ('source_refs', 'STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[]'),
    ('status', 'VARCHAR'),
    ('issues', 'STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[]'),
    ('source_sha256', 'VARCHAR'), ('profile_version', 'VARCHAR'),
    ('schema_version', 'VARCHAR'), ('extension_version', 'VARCHAR'),
    ('road_class', 'VARCHAR'), ('surface', 'VARCHAR'),
    ('max_speed_kmh', 'DOUBLE'), ('oneway', 'VARCHAR'),
]


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def read(name='valid', options=''):
    return f'ducklocate_read({literal(FIX / (name + ".osm.pbf"))}{options})'


def failed(conn, sql, message):
    try:
        conn.execute(sql).fetchall()
    except Exception as error:
        assert message.lower() in str(error).lower(), (sql, error)
    else:
        raise AssertionError(f'expected {message}: {sql}')


def coords(wkb):
    assert struct.unpack('<BI', wkb[:5]) == (1, 2)
    n, = struct.unpack('<I', wkb[5:9])
    assert len(wkb) == 9 + 16*n
    return [struct.unpack_from('<dd', wkb, 9+16*i) for i in range(n)]


def issue(code, field, raw, severity='warning'):
    return dict(severity=severity, code=code, field=field, raw_value=raw,
                message=('value cannot be represented by this scalar field' if severity == 'warning'
                         else 'required road geometry cannot be established'))


def ref(kind, id, version=None):
    return dict(osm_type=kind, osm_id=id, osm_version=version)


def rows(conn, function):
    return [dict(zip([c for c, _ in SCHEMA], row)) for row in
            conn.execute(f'SELECT * FROM {function} ORDER BY osm_id').fetchall()]


def contract_checks(conn, identity):
    assert [(r[0], r[1]) for r in conn.execute(f'DESCRIBE SELECT * FROM {read()}').fetchall()] == SCHEMA
    rr = rows(conn, read())
    assert [r['osm_id'] for r in rr] == [100,101,*range(104,116)]
    hash = hashlib.sha256((FIX / 'valid.osm.pbf').read_bytes()).hexdigest()
    source = json.loads((FIX / 'valid.json').read_text())
    raw = {w['id']: w for w in source['ways']}
    expected_speed = {100:48.28032,101:50.,104:18.52,107:12.5}
    expected_direction = {100:'backward',104:'forward',107:'both',109:'forward',110:'both',111:'forward',112:'both'}
    warning_fields = {
        105:[('conditional_value','maxspeed:conditional'),('conditional_value','oneway:conditional')],
        106:[('unsupported_value','maxspeed'),('unsupported_value','oneway')],
        108:[('unsupported_value','maxspeed'),('unsupported_value','oneway')],
        **{n:[('unsupported_value','maxspeed')] for n in range(109,113)},
        113:[('conditional_value','maxspeed'),('conditional_value','oneway')],
        114:[('unsupported_value','maxspeed:forward'),('unsupported_value','oneway:bicycle')],
    }
    for r in rr:
        id = r['osm_id']
        assert r['feature_id'] == f'roads:way:{id}' and r['osm_type'] == 'way'
        assert r['osm_version'] == (2 if id == 101 else None)
        assert r['tags'] == raw[id]['tags']
        assert r['name'] == ('Straße 東京 🦆' if id == 100 else '' if id == 104 else None)
        assert r['surface'] == ('pavé' if id == 100 else None)
        assert r['road_class'] == raw[id]['tags']['highway']
        assert r['max_speed_kmh'] == expected_speed.get(id), r
        assert r['oneway'] == expected_direction.get(id), r
        assert r['status'] == 'ok' and r['geometry_crs'] == 'EPSG:4326'
        assert r['source_sha256'] == hash
        assert r['profile_version'] == r['schema_version'] == '1.0.0'
        assert r['extension_version'] == identity
        assert r['issues'] == [issue(code,k,raw[id]['tags'][k]) for code,k in warning_fields.get(id,[])], r
        points = ([(4.,51.),(2.,49.),(3.,50.),(2.,49.)] if id==100 else
                  [(2.,49.),(3.,50.),(2.,49.)] if id==101 else
                  [(3.,50.),(2.,49.)] if id==104 else [(2.,49.),(3.,50.)])
        assert coords(r['geometry']) == points
        node_refs = ([ref('node',3,3),ref('node',1,1),ref('node',2)] if id==100 else
                     [ref('node',2),ref('node',1,1)] if id==104 else [ref('node',1,1),ref('node',2)])
        assert r['source_refs'] == [ref('way',id,2 if id==101 else None)] + node_refs
    assert rows(conn, read(options=", on_error := 'report'")) == rr
    assert rows(conn, read(options=", expected_sha256 := NULL")) == rr
    assert rows(conn, read(options=f', expected_sha256 := {literal(hash.upper())}')) == rr
    assert conn.execute(f'SELECT count(*) FROM {read("empty")}').fetchone() == (0,)
    for name,id,points,refs in [
        ('dense',301,[(3.,50.),(2.,49.),(3.,50.)],[ref('node',2,3),ref('node',1,2)]),
        ('dense-absent',302,[(2.,49.),(3.,50.)],[ref('node',1),ref('node',2)]),
    ]:
        r, = rows(conn, read(name))
        assert coords(r['geometry']) == points
        assert r['source_refs'] == [ref('way',id)] + refs
    return hash


def error_checks(conn, directory):
    failed(conn, f'SELECT * FROM {read("rejected")}', 'missing_reference')
    rr = rows(conn, read('rejected', ", on_error := 'report'"))
    assert len(rr) == 7
    for r in rr:
        id = r['osm_id']
        if id == 206:
            assert r['status'] == 'ok' and r['issues'] == []
            assert coords(r['geometry']) == [(2.,49.),(2.,90.),(3.,50.)]
        else:
            code = 'missing_reference' if id==201 else 'invalid_geometry'
            assert r['status'] == 'rejected' and r['geometry'] is None
            assert r['issues'] == [issue(code,'geometry',None,'error')]
    assert rr[0]['source_refs'] == [ref('way',201),ref('node',1),ref('node',2)]
    assert rr[0]['max_speed_kmh'] == 50.
    failed(conn, "SELECT * FROM " + read("conflict", ", on_error := 'report'"), "duplicate/conflicting")
    args = [
        ('NULL','must not be NULL'), ("''",'non-empty local'), ("'https://example.com/data.pbf'",'local'),
        ("'*.pbf'",'glob'), ("'/absent/file.pbf'",'regular local'),
        (f"{literal(FIX/'valid.osm.pbf')},profile := NULL",'must not be NULL'),
        (f"{literal(FIX/'valid.osm.pbf')},profile := 'buildings'",'unknown profile'),
        (f"{literal(FIX/'valid.osm.pbf')},profile_version := '2.0.0'",'unknown profile_version'),
        (f"{literal(FIX/'valid.osm.pbf')},profile_version := NULL",'must not be NULL'),
        (f"{literal(FIX/'valid.osm.pbf')},on_error := 'skip'",'on_error'),
        (f"{literal(FIX/'valid.osm.pbf')},on_error := NULL",'must not be NULL'),
        (f"{literal(FIX/'valid.osm.pbf')},crs := NULL",'must not be NULL'),
        (f"{literal(FIX/'valid.osm.pbf')},crs := ''",'unsupported CRS'),
        (f"{literal(FIX/'valid.osm.pbf')},crs := 'EPSG:32632'",'unsupported CRS'),
        (f"{literal(FIX/'valid.osm.pbf')},expected_sha256 := 'no'",'64 hexadecimal'),
        (f"{literal(FIX/'valid.osm.pbf')},expected_sha256 := '{'0'*64}'",'mismatch'),
        (f"{literal(FIX/'valid.osm.pbf')},unused := 1",'unused'),
        (f"{literal(FIX/'valid.osm.pbf')},'roads'",'No function matches'),
    ]
    for arg,message in args:
        failed(conn,f'SELECT * FROM ducklocate_read({arg})',message)
    # Bind-only operations must not open nonexistent paths.
    conn.execute("EXPLAIN SELECT * FROM ducklocate_read('/absent/file.pbf')").fetchall()
    conn.execute("DESCRIBE SELECT * FROM ducklocate_read('/absent/file.pbf')").fetchall()
    raw = (FIX / 'valid.osm.pbf').read_bytes()
    header = frame('OSMHeader',blob(4,'OsmSchema-V0.6'),False)
    broken = [b'',raw[:-1],raw+b'\0',header+frame('OSMData',b'\x08\x80'),
              frame('OSMHeader',blob(4,'OsmSchema-V0.6')+blob(4,'HistoricalInformation')),
              header+frame('OSMData',blob(1,blob(1,b'\xff'))),
              header+frame('OSMData',blob(1,blob(1,''))+blob(2,blob(2,packed(1,[2])+packed(8,[])+packed(9,[2]))))]
    for i,data in enumerate(broken):
        p = directory / f'broken{i}.pbf'
        p.write_bytes(data)
        failed(conn,f"SELECT * FROM ducklocate_read({literal(p)},on_error := 'report')",'PBF' if i in [1,2,3,4,5,6] else 'header')
    # Resource failure must be a statement error even with report mode; sparse file.
    p = directory / 'overlimit.pbf'
    with p.open('wb') as f:
        f.truncate(512*1024*1024+1)
    failed(conn,f"SELECT * FROM ducklocate_read({literal(p)},on_error := 'report')",'resource limit')
    # Independently hand-encoded way with too many refs.
    way=integer(1,1)+packed(8,[2]*10001)
    p.write_bytes(header+frame('OSMData',blob(1,blob(1,''))+blob(2,blob(3,way))))
    failed(conn,f'SELECT * FROM ducklocate_read({literal(p)})','resource limit')

    # Exercise each geometry failure independently in fail mode, rather than
    # stopping at the first missing reference in the combined fixture.
    rejected = json.loads((FIX/'rejected.json').read_text())
    p = directory/'single-rejection.pbf'
    for way in rejected['ways']:
        p.write_bytes(encode({'nodes':rejected['nodes'],'ways':[way]}))
        fn = f'ducklocate_read({literal(p)})'
        if way['id'] == 206:
            fn = f"ducklocate_read({literal(p)},crs := 'EPSG:3857')"
            code = 'transformation_failed'
        else:
            code = 'missing_reference' if way['id'] == 201 else 'invalid_geometry'
        failed(conn,f'SELECT * FROM {fn}',code)
    # Relations are validated but neither select output nor contribute lineage.
    relation = integer(1,500) + packed(8,[0]) + packed(9,[2]) + packed(10,[1])
    p.write_bytes((FIX/'valid.osm.pbf').read_bytes() + frame('OSMData',blob(1,blob(1,''))+blob(2,blob(4,relation))))
    assert conn.execute(f'SELECT count(*) FROM ducklocate_read({literal(p)})').fetchone() == (14,)
    # Duplicate identities remain errors even when the bytes/records are identical.
    p.write_bytes(encode({'nodes':[{'id':1,'x':2,'y':49}]*2}))
    failed(conn,f'SELECT * FROM ducklocate_read({literal(p)})','duplicate/conflicting')


def crs_checks(conn):
    conn.execute(f'LOAD {literal(ROOT / ".cache/spatial/spatial.duckdb_extension")}')
    rr = rows(conn, read(options=",crs := 'EPSG:3857'"))
    for r in rr:
        assert r['geometry_crs'] == 'EPSG:3857'
    assert conn.execute(f'SELECT ST_AsText(geometry) FROM {read()} WHERE osm_id=100').fetchone() == ('LINESTRING (4 51, 2 49, 3 50, 2 49)',)
    points = coords(rr[0]['geometry'])
    for (x,y),(lon,lat) in zip(points,[(4,51),(2,49),(3,50),(2,49)]):
        assert math.isclose(x,6378137*math.radians(lon),rel_tol=0,abs_tol=1e-6)
        assert math.isclose(y,6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2)),rel_tol=0,abs_tol=1e-6)
    projected = rows(conn, read('rejected',",on_error := 'report',crs := 'EPSG:3857'"))
    assert projected[5]['status'] == 'rejected' and projected[5]['geometry'] is None
    assert projected[5]['issues'] == [issue('transformation_failed','geometry',None,'error')]


def lifecycle_checks(connect, directory, identity):
    source = {'nodes':[{'id':1,'x':2,'y':49},{'id':2,'x':3,'y':50}],
              'ways':[{'id':id,'refs':[2,1,2],'tags':{'highway':'track', 'name':f'road {id}',
                        **({'maxspeed':'50'} if id%3==0 else {'maxspeed':'walk'} if id%3==1 else {}),
                        **({'oneway':'yes'} if id%2==0 else {})}} for id in range(5000)]}
    p = directory / 'chunks.pbf'
    p.write_bytes(encode(source))
    query = f'ducklocate_read({literal(p)})'
    baseline = set(Path(tempfile.gettempdir()).glob('ducklocate-*'))
    with connect() as conn:
        expected = (5000,12497500)
        rr = rows(conn,query)
        assert len(rr)==5000
        for id,r in enumerate(rr):
            assert r['osm_id']==id and r['name']==f'road {id}'
            assert coords(r['geometry'])==[(3.,50.),(2.,49.),(3.,50.)]
            assert r['source_refs']==[ref('way',id),ref('node',2),ref('node',1)]
            assert r['max_speed_kmh']==(50. if id%3==0 else None)
            assert r['oneway']==('forward' if id%2==0 else None)
            assert r['issues']==([issue('unsupported_value','maxspeed','walk')] if id%3==1 else [])

        conn.execute(f'PREPARE roads_scan AS SELECT count(*),sum(osm_id) FROM {query}')
        for _ in range(3):
            assert conn.execute('EXECUTE roads_scan').fetchone() == expected
        conn.execute(f'CREATE VIEW roads_view AS SELECT * FROM {query}')
        for _ in range(2):
            assert conn.execute('SELECT count(*),sum(osm_id) FROM roads_view').fetchone() == expected
        assert conn.execute(f'SELECT count(*) FROM {query} WHERE osm_id>=4997').fetchone() == (3,)
        assert conn.execute(f'SELECT count(*) FROM {query} WHERE osm_id<0').fetchone() == (0,)
        assert len(conn.execute(f'SELECT * FROM {query} LIMIT 1').fetchall()) == 1
        assert rows(conn,read())[0]['extension_version'] == identity
        # Caller-owned transactions; a failed CTAS is rolled back, no publication.
        conn.execute('BEGIN')
        conn.execute(f'CREATE TABLE roads AS SELECT * FROM {query}')
        assert conn.execute('SELECT count(*) FROM roads').fetchone() == (5000,)
        failed(conn,f'CREATE TABLE broken AS SELECT * FROM {read("rejected")}','missing_reference')
        conn.execute('ROLLBACK')
        assert conn.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name IN ('roads','broken')").fetchone() == (0,)
        # Same-connection independent selections.
        assert conn.execute(f'SELECT a.n,b.n FROM (SELECT count(*) n FROM {read()}) a CROSS JOIN (SELECT count(*) n FROM {read("dense")}) b').fetchone() == (14,1)
    assert set(Path(tempfile.gettempdir()).glob('ducklocate-*')) == baseline
    def select(name):
        with connect() as conn:
            return conn.execute(f'SELECT count(*) FROM {read(name)}').fetchone()[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(select,['valid','dense'])) == [14,1]
    # Persistent CTAS retains genuine GEOMETRY and nested types after reopening.
    db = directory / 'retained.duckdb'
    with connect(str(db)) as conn:
        conn.execute(f'CREATE TABLE roads AS SELECT * FROM {read()}')
    with connect(str(db)) as conn:
        assert [(r[0],r[1]) for r in conn.execute('DESCRIBE roads').fetchall()] == SCHEMA
        assert conn.execute('SELECT count(*) FROM roads').fetchone() == (14,)
        conn.execute(f'LOAD {literal(ROOT/".cache/spatial/spatial.duckdb_extension")}')
        conn.execute('CREATE INDEX roads_geometry ON roads USING RTREE(geometry)')
        assert conn.execute('SELECT count(*) FROM roads WHERE ST_Intersects(geometry,ST_MakeEnvelope(1,48,5,52))').fetchone() == (14,)

        assert coords(conn.execute('SELECT geometry FROM roads WHERE osm_id=100').fetchone()[0]) == [(4.,51.),(2.,49.),(3.,50.),(2.,49.)]
    # Interrupt a real reader query while its scan-owned temporary files exist.
    conn = connect()
    errors = []
    def running():
        try:
            conn.execute(f'SELECT sum(osm_id) FROM {query}').fetchall()
        except Exception as error:
            errors.append(str(error))
    worker = threading.Thread(target=running)
    worker.start()
    deadline = time.monotonic()+10
    while not (set(Path(tempfile.gettempdir()).glob('ducklocate-*'))-baseline):
        assert worker.is_alive() and time.monotonic()<deadline, 'did not observe active scan'
        time.sleep(.001)
    conn.interrupt()
    worker.join(timeout=20)
    assert not worker.is_alive() and len(errors)==1 and 'interrupt' in errors[0].lower(), errors
    conn.close()
    assert set(Path(tempfile.gettempdir()).glob('ducklocate-*')) == baseline
    # Atomic path replacement after source open cannot retarget the private snapshot.
    conn = connect()
    result, errors = [], []
    worker = threading.Thread(target=lambda: result.extend(conn.execute(f'SELECT count(*),min(source_sha256),max(source_sha256) FROM {query}').fetchall()))
    original_hash = hashlib.sha256(p.read_bytes()).hexdigest()
    worker.start()
    deadline = time.monotonic()+10
    while not (set(Path(tempfile.gettempdir()).glob('ducklocate-*'))-baseline):
        assert worker.is_alive() and time.monotonic()<deadline
        time.sleep(.001)
    replacement = directory / 'replacement.pbf'
    replacement.write_bytes((FIX/'empty.osm.pbf').read_bytes())
    os.replace(replacement,p)
    worker.join(timeout=20)
    assert not worker.is_alive() and result == [(5000,original_hash,original_hash)], result
    conn.close()
    assert set(Path(tempfile.gettempdir()).glob('ducklocate-*')) == baseline

    # In-place source mutation after snapshotting must not affect projection.
    p.write_bytes(encode(source))
    conn = connect()
    result = []
    worker = threading.Thread(target=lambda: result.extend(conn.execute(f'SELECT count(*),min(source_sha256) FROM {query}').fetchall()))
    worker.start()
    deadline = time.monotonic()+10
    while True:
        private = set(Path(tempfile.gettempdir()).glob('ducklocate-*'))-baseline
        if any((d/'index.sqlite').exists() for d in private):
            break
        assert worker.is_alive() and time.monotonic()<deadline
        time.sleep(.001)
    with p.open('r+b') as live:
        live.seek(0)
        live.write(b'corrupted live file')
        live.truncate(20)
    worker.join(timeout=20)
    assert not worker.is_alive() and result == [(5000,original_hash)], result
    conn.close()
    assert set(Path(tempfile.gettempdir()).glob('ducklocate-*')) == baseline


def dense_field_checks(conn):
    for name, data in dense_field_fixtures().items():
        assert (FIX / (name + '.osm.pbf')).read_bytes() == data, name
    for mode in ['fail', 'report']:
        r, = rows(conn, read('split-dense', f",on_error := '{mode}'"))
        assert r['status'] == 'ok' and r['issues'] == []
        assert coords(r['geometry']) == [(2.,49.),(3.,50.)]
        assert r['source_refs'] == [ref('way',303),ref('node',1),ref('node',3)]
        failed(conn, 'SELECT * FROM ' + read('duplicate-dense', f",on_error := '{mode}'"),
               'invalid PBF: duplicate singular field')


def restricted_crs_checks(connect):
    # Each connection allowlists only its input; even an empty source must fail
    # before the isolated transform session can look up/load installed Spatial.
    for name, count in [('valid',14), ('empty',0)]:
        with connect() as conn:
            conn.execute(f'SET allowed_paths=[{literal(FIX / (name + ".osm.pbf"))}]')
            conn.execute('SET enable_external_access=false')
            conn.execute('SET lock_configuration=true')
            failed(conn, 'LOAD spatial', 'Loading external extensions is disabled')
            for mode in ['fail', 'report']:
                assert conn.execute(f'SELECT count(*) FROM {read(name, f",on_error := {literal(mode)}")}').fetchone() == (count,)
                fn = read(name, f",crs := 'EPSG:3857',on_error := '{mode}'")
                failed(conn, 'SELECT * FROM ' + fn,
                       'EPSG:3857 requires loading Spatial; caller has enable_external_access=false')
            assert conn.execute("SELECT current_setting('enable_external_access'), current_setting('lock_configuration')").fetchone() == (False,True)


def security_checks(connect):
    restricted_crs_checks(connect)
    with connect() as conn:
        conn.execute("SET disabled_filesystems='LocalFileSystem'")
        failed(conn,'SELECT * FROM '+read(),'disabled')
    with connect() as conn:
        conn.execute(f'SET allowed_directories=[{literal(FIX)}]')
        conn.execute('SET enable_external_access=false')
        assert conn.execute(f'SELECT count(*) FROM {read()}').fetchone() == (14,)
    with connect() as conn, tempfile.TemporaryDirectory(prefix='roads-no-spatial-') as directory:
        conn.execute(f'SET extension_directory={literal(directory)}')
        for mode in ['fail','report']:
            fn = read('empty',f",crs := 'EPSG:3857',on_error := '{mode}'")
            failed(conn,'SELECT * FROM '+fn,'spatial')
    with connect() as conn:
        conn.execute('SET enable_external_access=false')
        failed(conn,f'SELECT * FROM {read()}', 'disabled')
        failed(conn, "SELECT * FROM " + read(options=",crs := 'EPSG:3857'"), "disabled")
    with connect() as conn:
        conn.execute(f'SET allowed_paths=[{literal(FIX/"valid.osm.pbf")}]')
        conn.execute('SET enable_external_access=false')
        assert conn.execute(f'SELECT count(*) FROM {read()}').fetchone() == (14,)
        failed(conn,f'SELECT * FROM {read("dense")}', 'disabled')


def run(connect, identity):
    for path in FIX.glob('*.json'):
        assert encode(json.loads(path.read_text())) == path.with_suffix('.osm.pbf').read_bytes(), path
    # Isolate process-local scan files: parallel harnesses must not mistake each
    # other's active resources for leaks. Rust and Python use this same temp root.
    with tempfile.TemporaryDirectory(prefix='roads-checks-') as d:
        directory = Path(d)
        scan_root = directory/'scans'
        scan_root.mkdir()
        old_env = os.environ.get('TMPDIR')
        old_python_temp = tempfile.tempdir
        os.environ['TMPDIR'] = str(scan_root)
        tempfile.tempdir = str(scan_root)
        try:
            baseline = set(scan_root.iterdir())
            with connect() as conn:
                hash = contract_checks(conn,identity)
                error_checks(conn,directory)
                dense_field_checks(conn)
                crs_checks(conn)
            lifecycle_checks(connect,directory,identity)
            security_checks(connect)
            assert set(scan_root.iterdir()) == baseline
        finally:
            tempfile.tempdir = old_python_temp
            if old_env is None:
                os.environ.pop('TMPDIR',None)
            else:
                os.environ['TMPDIR'] = old_env
    return {'roads_rows':14,'roads_source_sha256':hash,'roads_checks':'passed'}
