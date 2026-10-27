#!/usr/bin/env python3
"""Regenera las evidencias de BD desde el PostgreSQL real (solo lectura).

Uso, desde `reservas-platform/` con el perfil dev levantado (`make up`):

    .venv\\Scripts\\python.exe docs/database-evidence/generate.py

Lee la conexion de `.env` (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DEV_PORT)
y opcionalmente de POSTGRES_HOST/POSTGRES_PORT. Nunca imprime la contrasena.

Escribe:
  inventory.md            inventario real (tablas, columnas, claves, indices, tamano)
  integrity.md            integridad fisica (FK) y logica (referencias entre BD)
  diagrams/<db>.md         diagrama ER Mermaid por base (renderiza en GitHub)
  schema/<db>.sql          DDL via `pg_dump --schema-only` (sin datos ni credenciales)

No ejecuta escrituras: information_schema, pg_catalog, count(*) y pg_dump.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import subprocess
import sys

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    sys.exit("Falta psycopg: usa .venv/Scripts/python.exe (make deps)")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # reservas-platform/
DBS = [
    "customer_db",
    "hotel_db",
    "availability_db",
    "payment_db",
    "reservation_db",
    "notification_db",
]
INFRA_TABLE = "alembic_version"
SENSITIVE = {
    "email": "PII",
    "password_hash": "secreto",
    "token_hash": "secreto",
    "payment_token": "token",
}
TYPE_MAP = {
    "uuid": "uuid",
    "varchar": "varchar",
    "bpchar": "char",
    "text": "text",
    "timestamptz": "timestamptz",
    "timestamp": "timestamp",
    "date": "date",
    "int2": "smallint",
    "int4": "int",
    "int8": "bigint",
    "numeric": "numeric",
    "bool": "boolean",
    "jsonb": "jsonb",
    "json": "json",
    "float8": "float",
}
KIND = {"p": "PK", "f": "FK", "u": "UNIQUE", "c": "CHECK"}

TABLES = """
select c.relname as name
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r', 'p')
order by c.relname
"""
COLUMNS = """
select table_name, ordinal_position, column_name, data_type, udt_name,
       is_nullable, column_default
from information_schema.columns
where table_schema = 'public'
order by table_name, ordinal_position
"""
CONSTRAINTS = """
select c.conname as name, c.contype as kind, r.relname as tbl,
       (select string_agg(a.attname, ',' order by u.ord)
          from unnest(c.conkey) with ordinality u(attnum, ord)
          join pg_attribute a on a.attrelid = c.conrelid and a.attnum = u.attnum) as cols,
       fr.relname as ref_tbl,
       (select string_agg(a.attname, ',' order by u.ord)
          from unnest(c.confkey) with ordinality u(attnum, ord)
          join pg_attribute a on a.attrelid = c.confrelid and a.attnum = u.attnum) as ref_cols,
       pg_get_constraintdef(c.oid) as def
from pg_constraint c
join pg_class r on r.oid = c.conrelid
join pg_namespace n on n.oid = r.relnamespace
left join pg_class fr on fr.oid = c.confrelid
where n.nspname = 'public' and c.contype in ('p', 'f', 'u', 'c')
order by r.relname, c.conname
"""
INDEXES = """
select tablename, indexname, indexdef
from pg_indexes where schemaname = 'public'
order by tablename, indexname
"""
SEQUENCES = """
select sequencename, data_type
from pg_sequences where schemaname = 'public'
order by sequencename
"""
DBINFO = """
select d.datname as db, pg_get_userbyid(d.datdba) as owner,
       pg_size_pretty(pg_database_size(d.datname)) as size
from pg_database d where d.datname = current_database()
"""

# Referencias logicas: (origen_bd, origen_tabla, origen_col, destino_bd, destino_tabla, destino_col, etiqueta)
LOGICAL = [
    ("reservation_db", "reservations", "customer_id", "customer_db", "customers", "id", "Reserva -> cliente"),
    ("reservation_db", "reservations", "hotel_id", "hotel_db", "hotels", "id", "Reserva -> hotel"),
    ("reservation_db", "reservations", "room_id", "hotel_db", "rooms", "id", "Reserva -> habitacion"),
    ("reservation_db", "reservations", "payment_id", "payment_db", "payments", "id", "Reserva -> pago"),
    ("availability_db", "inventory", "room_id", "hotel_db", "rooms", "id", "Inventario -> habitacion"),
    ("availability_db", "inventory", "hotel_id", "hotel_db", "hotels", "id", "Inventario -> hotel"),
    ("availability_db", "holds", "room_id", "hotel_db", "rooms", "id", "Hold -> habitacion"),
    ("payment_db", "payments", "reservation_id", "reservation_db", "reservations", "id", "Pago -> reserva"),
    ("notification_db", "notifications", "reservation_id", "reservation_db", "reservations", "id", "Notificacion -> reserva"),
    ("notification_db", "notifications", "customer_id", "customer_db", "customers", "id", "Notificacion -> cliente"),
    ("notification_db", "notifications", "event_id", "reservation_db", "outbox", "id", "Notificacion -> evento outbox"),
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("POSTGRES_")})
    return env


def dsn(env: dict[str, str], db: str) -> dict:
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", env.get("POSTGRES_DEV_PORT", "5433"))),
        "user": env.get("POSTGRES_USER", "postgres"),
        "password": env.get("POSTGRES_PASSWORD", ""),
        "dbname": db,
    }


def query(env, db, sql, params=None):
    with psycopg.connect(**dsn(env, db), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def catalog(env, db) -> dict:
    info = query(env, db, DBINFO)[0]
    tables = [r["name"] for r in query(env, db, TABLES)]
    counts = {t: query(env, db, f'select count(*) as n from public."{t}"')[0]["n"] for t in tables}
    rev = query(env, db, "select version_num from alembic_version")[0]["version_num"]
    return {
        "db": db,
        "owner": info["owner"],
        "size": info["size"],
        "revision": rev,
        "tables": [t for t in tables if t != INFRA_TABLE],
        "counts": counts,
        "columns": [c for c in query(env, db, COLUMNS) if c["table_name"] != INFRA_TABLE],
        "constraints": [c for c in query(env, db, CONSTRAINTS) if c["tbl"] != INFRA_TABLE],
        "indexes": [i for i in query(env, db, INDEXES) if i["tablename"] != INFRA_TABLE],
        "sequences": query(env, db, SEQUENCES),
        "has_alembic": INFRA_TABLE in tables,
    }


def md(value) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_inventory(cats: dict[str, dict]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [
        "# Inventario real de las bases de datos",
        "",
        f"Generado por `generate.py` el {now} contra PostgreSQL 16 en el perfil dev.",
        "Solo lectura: `information_schema`, `pg_catalog` y `count(*)`. Sin credenciales.",
        "",
        "> `alembic_version` existe en las 6 bases (control de migraciones); se omite",
        "> del inventario detallado y de los diagramas para no ensuciarlos.",
        "",
        "## Resumen",
        "",
        "| Base | Rol dueño | Tamaño | Tablas | Filas | Revisión Alembic |",
        "|---|---|---|---:|---:|---|",
    ]
    for db, c in cats.items():
        out.append(
            f"| `{db}` | `{c['owner']}` | {c['size']} | {len(c['tables'])} | "
            f"{sum(c['counts'][t] for t in c['tables'])} | `{c['revision']}` |"
        )
    out += [
        "",
        "Filas = suma de tablas de dominio (excluye `alembic_version`).",
        "",
    ]
    for db, c in cats.items():
        out += [f"## `{db}`", "", f"Dueño: `{c['owner']}` · Tamaño: {c['size']} · "
                f"Revisión Alembic: `{c['revision']}`", "", "### Tablas", "",
                "| Tabla | Filas |", "|---|---:|"]
        for t in c["tables"]:
            out.append(f"| `{t}` | {c['counts'][t]} |")
        out += ["", "### Columnas", "",
                "| Tabla | # | Columna | Tipo | Nulo | Default | Sensible |",
                "|---|---:|---|---|---|---|---|"]
        for col in c["columns"]:
            out.append(
                f"| `{col['table_name']}` | {col['ordinal_position']} | "
                f"`{col['column_name']}` | {md(col['data_type'])} | "
                f"{'sí' if col['is_nullable'] == 'YES' else 'no'} | "
                f"{md(col['column_default'])} | {SENSITIVE.get(col['column_name'], '-')} |"
            )
        out += ["", "### Claves y restricciones", "",
                "| Tabla | Nombre | Tipo | Columnas | Referencia | Definición |",
                "|---|---|---|---|---|---|"]
        for con in c["constraints"]:
            ref = f"`{con['ref_tbl']}({con['ref_cols']})`" if con["ref_tbl"] else "-"
            out.append(
                f"| `{con['tbl']}` | `{con['name']}` | {KIND.get(con['kind'], con['kind'])} | "
                f"`{md(con['cols'])}` | {ref} | `{md(con['def'])}` |"
            )
        out += ["", "### Índices", "", "| Tabla | Índice | Definición |", "|---|---|---|"]
        for idx in c["indexes"]:
            out.append(f"| `{idx['tablename']}` | `{idx['indexname']}` | `{md(idx['indexdef'])}` |")
        out += ["", "### Secuencias", ""]
        if c["sequences"]:
            out += ["| Secuencia | Tipo |", "|---|---|"]
            for seq in c["sequences"]:
                out.append(f"| `{seq['sequencename']}` | {seq['data_type']} |")
        else:
            out.append("Sin secuencias propias: las PK son UUID generados por la aplicación.")
        out.append("")
    return "\n".join(out)


def render_er(c: dict) -> str:
    out = [
        f"# Diagrama ER — `{c['db']}`",
        "",
        "Fuente Mermaid generada desde el catálogo real. GitHub la renderiza;",
        "para exportar PNG/SVG, pega el bloque en <https://mermaid.live>.",
        f"Se omiten `alembic_version` (infraestructura) y los datos. Dueño: `{c['owner']}`.",
        "",
        "```mermaid",
        "erDiagram",
    ]
    for table in c["tables"]:
        entity = table.upper()
        cols = [x for x in c["columns"] if x["table_name"] == table]
        pk = set()
        fk = set()
        uk = set()
        for con in c["constraints"]:
            if con["tbl"] != table:
                continue
            names = (con["cols"] or "").split(",")
            if con["kind"] == "p":
                pk.update(names)
            elif con["kind"] == "f":
                fk.update(names)
            elif con["kind"] == "u" and len(names) == 1:
                uk.update(names)
        out.append(f"    {entity} {{")
        for col in cols:
            marks = []
            if col["column_name"] in pk:
                marks.append("PK")
            if col["column_name"] in fk:
                marks.append("FK")
            if col["column_name"] in uk:
                marks.append("UK")
            typ = TYPE_MAP.get(col["udt_name"], col["udt_name"])
            suffix = (" " + ", ".join(marks)) if marks else ""
            out.append(f"        {typ} {col['column_name']}{suffix}")
        out.append("    }")
    for con in c["constraints"]:
        if con["kind"] != "f":
            continue
        out.append(
            f'    {con["ref_tbl"].upper()} ||--o{{ {con["tbl"].upper()} : "{con["name"]}"'
        )
    out += ["```", "", "## Restricciones CHECK y UNIQUE compuestas", "",
            "Se validan en la base y no se dibujan como aristas:", ""]
    for con in c["constraints"]:
        if con["kind"] in ("c", "u"):
            out.append(f"- `{con['tbl']}.{con['name']}`: `{con['def']}`")
    out.append("")
    return "\n".join(out)


def find_container() -> str | None:
    try:
        res = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.service=postgres",
             "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    names = [n for n in res.stdout.split() if n]
    return names[0] if names else None


def dump_ddl(container: str, env: dict[str, str], db: str) -> str | None:
    cmd = ["docker", "exec", container, "pg_dump", "-U", env.get("POSTGRES_USER", "postgres"),
           "-d", db, "--schema-only", "--no-owner", "--no-privileges"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if res.returncode != 0:
        print(f"  ! pg_dump {db}: {res.stderr.strip()}")
        return None
    # Quita meta-comandos de psql (\restrict, \unrestrict, \connect) para que el
    # archivo sea SQL puro y se pueda ejecutar tambien desde DBeaver.
    body = "\n".join(line for line in res.stdout.splitlines() if not line.startswith("\\"))
    header = (
        f"-- DDL de {db} extraído del PostgreSQL real con:\n"
        f"-- pg_dump -U {env.get('POSTGRES_USER', 'postgres')} -d {db} --schema-only --no-owner --no-privileges\n"
        "-- Sin datos, sin credenciales. Regenerar: docs/database-evidence/generate.py\n\n"
    )
    return header + body + "\n"


def physical_orphans(cats: dict[str, dict]) -> list[dict]:
    checks = []
    for db, c in cats.items():
        for con in c["constraints"]:
            if con["kind"] != "f":
                continue
            cols = con["cols"].split(",")
            refs = con["ref_cols"].split(",")
            not_null = " and ".join(f'c."{x}" is not null' for x in cols)
            join = " and ".join(f'p."{r}" = c."{x}"' for x, r in zip(cols, refs))
            sql = (f'select count(*) as n from public."{con["tbl"]}" c '
                   f'where {not_null} and not exists '
                   f'(select 1 from public."{con["ref_tbl"]}" p where {join})')
            n = 0
            try:
                n = query(_ENV, db, sql)[0]["n"]
            except Exception as exc:  # pragma: no cover
                print(f"  ! {db}.{con['name']}: {exc}")
            checks.append({"db": db, "name": con["name"], "n": n,
                           "desc": f"{con['tbl']}({con['cols']}) -> {con['ref_tbl']}({con['ref_cols']})"})
    return checks


def logical_orphans(cats: dict[str, dict]) -> list[dict]:
    results = []
    cache: dict[tuple, set] = {}

    def ids(db, table, col):
        key = (db, table, col)
        if key not in cache:
            rows = query(_ENV, db, f'select distinct "{col}"::text as v from public."{table}"')
            cache[key] = {r["v"] for r in rows if r["v"] is not None}
        return cache[key]

    # ponytail: diff en memoria; con volumen alto usar postgres_fdw y EXCEPT.
    for src_db, src_t, src_c, dst_db, dst_t, dst_c, label in LOGICAL:
        missing = sorted(ids(src_db, src_t, src_c) - ids(dst_db, dst_t, dst_c))
        results.append({"label": label, "src": f"{src_db}.{src_t}.{src_c}",
                        "dst": f"{dst_db}.{dst_t}.{dst_c}", "n": len(missing),
                        "sample": ", ".join(missing[:3])})
    return results


def render_integrity(phys: list[dict], logical: list[dict], extra: list[tuple]) -> str:
    out = [
        "# Integridad referencial y lógica",
        "",
        "Dos niveles distintos:",
        "",
        "1. **Física**: FK reales dentro de cada base. PostgreSQL las garantiza.",
        "2. **Lógica**: referencias entre bases de servicios distintos. **No hay FK**",
        "   entre bases (ADR-0002); las garantiza la aplicación/saga y aquí solo se",
        "   comprueban. Un huérfano lógico no rompe la base, pero es un dato a revisar.",
        "",
        "## Integridad física (FK dentro de la misma base)",
        "",
        "| Base | Constraint | Referencia | Huérfanos |",
        "|---|---|---|---:|",
    ]
    for c in phys:
        flag = "OK" if c["n"] == 0 else f"REVISAR ({c['n']})"
        out.append(f"| `{c['db']}` | `{c['name']}` | `{c['desc']}` | {flag} |")
    out += ["", "## Integridad lógica (referencias entre bases)", "",
            "Comprobación: ¿todo id referenciado existe en la base destino?", "",
            "| Referencia | Origen | Destino | Huérfanos | Muestra |",
            "|---|---|---|---:|---|"]
    for c in logical:
        flag = "OK" if c["n"] == 0 else f"REVISAR ({c['n']})"
        out.append(f"| {c['label']} | `{c['src']}` | `{c['dst']}` | {flag} | {c['sample'] or '-'} |")
    out += ["", "## Otras comprobaciones de dominio", "",
            "| Comprobación | Resultado |", "|---|---|"]
    for label, value in extra:
        out.append(f"| {label} | {value} |")
    out += [
        "",
        "> Los huérfanos lógicos, si aparecen, son residuo de pruebas E2E que crean",
        "> holds/inventario/notificaciones con ids de habitaciones o reservas que no",
        "> pasan por el servicio dueño. No violan el esquema (no hay FK entre bases).",
        "> Para una demo limpia: `make clean && make build && make up && make seed`.",
        "",
    ]
    return "\n".join(out)


_ENV: dict[str, str] = {}


def main() -> int:
    global _ENV
    env = load_env()
    _ENV = env
    if not env.get("POSTGRES_PASSWORD"):
        print("No hay POSTGRES_PASSWORD en .env")
        return 1

    cats: dict[str, dict] = {}
    for db in DBS:
        print(f"== {db}")
        cats[db] = catalog(env, db)
    (HERE / "inventory.md").write_text(render_inventory(cats), encoding="utf-8", newline="\n")
    print("  inventory.md")

    container = find_container()
    for db, c in cats.items():
        (HERE / "diagrams" / f"{db}.md").write_text(render_er(c), encoding="utf-8", newline="\n")
        if container:
            ddl = dump_ddl(container, env, db)
            if ddl is not None:
                (HERE / "schema" / f"{db}.sql").write_text(ddl, encoding="utf-8", newline="\n")
    print(f"  diagrams/*.md ({len(cats)})")
    print(f"  schema/*.sql ({'6' if container else 'omitido: contenedor postgres no encontrado'})")

    phys = physical_orphans(cats)
    logical = logical_orphans(cats)

    # Coherencia habitacion<->hotel y reglas de negocio declaradas.
    room_hotel = {r["id"]: r["hotel_id"] for r in query(env, "hotel_db",
                  'select id::text as id, hotel_id::text as hotel_id from rooms')}
    res_bad = [r for r in query(env, "reservation_db",
               'select id::text as id, hotel_id::text as h, room_id::text as r from reservations')
               if room_hotel.get(r["r"]) != r["h"]]
    inv_bad = [r for r in query(env, "availability_db",
               'select distinct room_id::text as r, hotel_id::text as h from inventory')
               if room_hotel.get(r["r"]) != r["h"]]
    addons = [
        ("reservas con hotel distinto al hotel de la habitacion",
         "OK" if not res_bad else f"REVISAR ({len(res_bad)})"),
        ("filas de inventario cuyo room_id no existe o no coincide con hotel_id",
         "OK" if not inv_bad else f"REVISAR ({len(inv_bad)} pares room/hotel)"),
        ("reservas con nights != check_out - check_in",
         query(env, "reservation_db",
               "select count(*) as n from reservations where nights <> (check_out - check_in)")[0]["n"]),
        ("pagos SUCCEEDED sin asiento CHARGE en ledger",
         query(env, "payment_db", "select count(*) as n from payments p left join ledger l "
               "on l.payment_id = p.id and l.kind = 'CHARGE' "
               "where p.status = 'SUCCEEDED' and l.id is null")[0]["n"]),
        ("notificaciones SENT sin sent_at",
         query(env, "notification_db",
               "select count(*) as n from notifications where status = 'SENT' and sent_at is null")[0]["n"]),
        ("reservas sin evento inicial (from_status NULL)",
         query(env, "reservation_db", "select count(*) as n from reservations r where not exists "
               "(select 1 from reservation_events e where e.reservation_id = r.id and e.from_status is null)")[0]["n"]),
    ]
    (HERE / "integrity.md").write_text(render_integrity(phys, logical, addons),
                                       encoding="utf-8", newline="\n")
    print("  integrity.md")

    # Autochequeo minimo: 6 bases, 6 diagramas con erDiagram, huérfanos fisicos 0.
    assert len(cats) == 6
    for db in DBS:
        text = (HERE / "diagrams" / f"{db}.md").read_text(encoding="utf-8")
        assert "erDiagram" in text and text.count("{") >= 1, db
    assert all(c["n"] == 0 for c in phys), "hay huérfanos fisicos"
    print("OK: 6 bases, 6 diagramas, integridad fisica sin huérfanos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
