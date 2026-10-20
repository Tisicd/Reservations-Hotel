import json

import psycopg

from conftest import dsn, run_compose

SERVICES = ["customer", "hotel", "availability", "reservation", "payment", "notification"]
DBS = [f"{s}_db" for s in SERVICES]


def test_existen_exactamente_las_6_bds(admin_conn):
    rows = admin_conn.execute(
        "SELECT datname FROM pg_database WHERE datname LIKE '%_db' ORDER BY datname"
    ).fetchall()
    assert {r[0] for r in rows} == set(DBS)


def test_roles_sin_privilegios_altos(admin_conn):
    rows = admin_conn.execute(
        "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole "
        "FROM pg_roles WHERE rolname = ANY(%s)",
        (SERVICES,),
    ).fetchall()
    assert {r[0] for r in rows} == set(SERVICES)
    for name, super_, createdb, createrole in rows:
        assert not super_, f"{name} es superusuario"
        assert not createdb, f"{name} tiene createdb"
        assert not createrole, f"{name} tiene createrole"


def test_durabilidad_on(admin_conn):
    for setting in ("fsync", "synchronous_commit", "full_page_writes", "data_checksums"):
        val = admin_conn.execute("SHOW " + setting).fetchone()[0]
        assert val == "on", f"{setting}={val}"


def test_timeouts_acordados(admin_conn):
    expected = {
        "statement_timeout": "15000",
        "lock_timeout": "10000",
        "idle_in_transaction_session_timeout": "60000",
    }
    for setting, want_ms in expected.items():
        got = admin_conn.execute(
            "SELECT setting FROM pg_settings WHERE name = %s", (setting,)
        ).fetchone()[0]
        assert got == want_ms, f"{setting}={got}"


def test_compose_sin_puertos_y_redes_internas():
    r = run_compose(["config", "--format", "json"])
    assert r.returncode == 0, r.stderr
    cfg = json.loads(r.stdout)
    assert "ports" not in cfg["services"]["postgres"]
    assert cfg["networks"]["backend-net"]["internal"] is True
    assert cfg["networks"]["data-net"]["internal"] is True


def test_persistencia_sobrevive_recreacion():
    with psycopg.connect(dsn("customer_db"), autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS _persist_test")
        conn.execute("CREATE TABLE _persist_test (id int)")
        conn.execute("INSERT INTO _persist_test VALUES (42)")

    r = run_compose(["-f", "compose.yaml", "-f", "compose.dev.yaml", "rm", "-sf", "postgres"])
    assert r.returncode == 0, r.stderr
    r = run_compose(["-f", "compose.yaml", "-f", "compose.dev.yaml", "up", "-d", "--wait", "postgres"])
    assert r.returncode == 0, r.stderr

    with psycopg.connect(dsn("customer_db"), autocommit=True) as conn:
        assert conn.execute("SELECT id FROM _persist_test").fetchone() == (42,)
        conn.execute("DROP TABLE _persist_test")
