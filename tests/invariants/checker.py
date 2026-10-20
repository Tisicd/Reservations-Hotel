"""Chequeador de invariantes I1-I7 sobre las BDs del stack.

Uso: python tests/invariants/checker.py [--grace SEGUNDOS]
Solo lee; devuelve código de salida 1 si hay violaciones.
"""

import argparse
import dataclasses
import datetime as dt
import os
import pathlib
import sys

import sqlalchemy as sa

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "services" / "reservation"))

from app.domain.state_machine import (  # noqa: E402
    ALLOWED_TRANSITIONS,
    CONFIRMED,
    MANUAL_REVIEW,
    STABLE_STATES,
)

DATABASES = ("availability_db", "reservation_db", "payment_db")


@dataclasses.dataclass(frozen=True)
class Violation:
    code: str
    invariant: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code} [{self.invariant}] {self.detail}"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _postgres_password() -> str:
    secret = REPO_ROOT / "secrets" / "postgres_password.txt"
    if secret.exists():
        return secret.read_text(encoding="utf-8").strip()
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "POSTGRES_PASSWORD" and value.strip():
                return value.strip()
    return os.environ.get("POSTGRES_PASSWORD", "change-me")


def _url(db: str) -> str:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_DEV_PORT", "5433")
    user = os.environ.get("POSTGRES_USER", "postgres")
    return f"postgresql+psycopg://{user}:{_postgres_password()}@{host}:{port}/{db}"


def open_connections(
    read_only: bool = True,
) -> tuple[dict[str, sa.Connection], list[sa.Engine]]:
    options = {"connect_timeout": 5}
    if read_only:
        options["options"] = "-c default_transaction_read_only=on"
    engines = {
        db: sa.create_engine(_url(db), poolclass=sa.pool.NullPool, connect_args=options)
        for db in DATABASES
    }
    conns = {db: engines[db].connect() for db in DATABASES}
    return conns, list(engines.values())


def close_connections(conns: dict[str, sa.Connection], engines: list[sa.Engine]) -> None:
    for conn in conns.values():
        conn.close()
    for engine in engines:
        engine.dispose()


def max_deadline_seconds() -> int:
    defaults = {
        "SAGA_HOLD_DEADLINE_SECONDS": 60,
        "CONFIRM_DEADLINE_SECONDS": 120,
        "CANCEL_DEADLINE_SECONDS": 120,
        "PAYMENT_RECONCILE_DEADLINE_SECONDS": 900,
    }
    values = [int(os.environ.get(name, str(default))) for name, default in defaults.items()]
    return max(values)


def check_availability(conn: sa.Connection) -> list[Violation]:
    violations = []
    rows = conn.execute(
        sa.text(
            "SELECT room_id, night, total, held, confirmed FROM inventory "
            "WHERE held + confirmed > total"
        )
    )
    for row in rows:
        violations.append(
            Violation(
                "OVERSELL",
                "I1",
                f"room={row.room_id} night={row.night} total={row.total} "
                f"held={row.held} confirmed={row.confirmed}",
            )
        )
    drift = conn.execute(
        sa.text(
            """
            SELECT i.room_id, i.night, i.held, i.confirmed,
                   COALESCE(h.held, 0) AS held_holds,
                   COALESCE(h.confirmed, 0) AS confirmed_holds
            FROM inventory i
            LEFT JOIN LATERAL (
                SELECT sum(units) FILTER (WHERE status = 'HELD') AS held,
                       sum(units) FILTER (WHERE status = 'CONFIRMED') AS confirmed
                FROM holds h
                WHERE h.room_id = i.room_id
                  AND h.check_in <= i.night
                  AND h.check_out > i.night
            ) h ON true
            WHERE i.held <> COALESCE(h.held, 0)
               OR i.confirmed <> COALESCE(h.confirmed, 0)
            """
        )
    )
    for row in drift:
        violations.append(
            Violation(
                "INVENTORY_DRIFT",
                "I1",
                f"room={row.room_id} night={row.night} "
                f"inventory=({row.held},{row.confirmed}) "
                f"holds=({row.held_holds},{row.confirmed_holds})",
            )
        )
    return violations


def _event_chain_violations(conn: sa.Connection) -> list[Violation]:
    rows = conn.execute(
        sa.text(
            """
            SELECT r.id, r.status, e.from_status, e.to_status
            FROM reservations r
            LEFT JOIN reservation_events e ON e.reservation_id = r.id
            ORDER BY r.id, e.id
            """
        )
    ).all()
    grouped: dict = {}
    statuses: dict = {}
    for row in rows:
        statuses[row.id] = row.status
        grouped.setdefault(row.id, []).append(row)
    violations = []
    for reservation_id, events in grouped.items():
        events = [event for event in events if event.to_status is not None]
        if not events:
            violations.append(
                Violation("EVENT_CHAIN_BROKEN", "I2", f"reservation={reservation_id} sin eventos")
            )
            continue
        if events[0].from_status is not None or events[0].to_status != "RECEIVED":
            violations.append(
                Violation(
                    "EVENT_CHAIN_BROKEN",
                    "I2",
                    f"reservation={reservation_id} primer evento "
                    f"({events[0].from_status}->{events[0].to_status})",
                )
            )
            continue
        broken = None
        previous = events[0].to_status
        for event in events[1:]:
            if event.from_status != previous or event.to_status not in ALLOWED_TRANSITIONS.get(
                previous, frozenset()
            ):
                broken = f"{event.from_status}->{event.to_status} tras {previous}"
                break
            previous = event.to_status
        if broken is None and previous != statuses[reservation_id]:
            broken = f"último evento {previous} != estado {statuses[reservation_id]}"
        if broken is not None:
            violations.append(
                Violation("EVENT_CHAIN_BROKEN", "I2", f"reservation={reservation_id} {broken}")
            )
    return violations


def check_reservation(conn: sa.Connection, grace_seconds: int = 60) -> list[Violation]:
    violations = _event_chain_violations(conn)

    deadline = max_deadline_seconds() + grace_seconds
    stuck = conn.execute(
        sa.text(
            "SELECT id, status FROM reservations "
            "WHERE status <> ALL(:stable) "
            "AND phase_started_at < now() - make_interval(secs => :deadline)"
        ),
        {"stable": list(STABLE_STATES), "deadline": deadline},
    )
    for row in stuck:
        violations.append(
            Violation("STUCK_RESERVATION", "I5", f"reservation={row.id} status={row.status}")
        )

    outbox = conn.execute(
        sa.text("SELECT aggregate_id, type, count(*) FROM outbox GROUP BY 1, 2")
    ).all()
    counts = {(row[0], row[1]): row[2] for row in outbox}
    confirmed = conn.execute(
        sa.text("SELECT id FROM reservations WHERE status = :status"), {"status": CONFIRMED}
    ).scalars()
    for reservation_id in confirmed:
        _check_outbox(
            violations, counts, reservation_id, "reservation.confirmed", "I6", "CONFIRMED"
        )

    cancelled = conn.execute(
        sa.text(
            """
            SELECT DISTINCT r.id
            FROM reservations r
            JOIN reservation_events e ON e.reservation_id = r.id
            WHERE r.status = 'CANCELLED' AND e.from_status = 'CONFIRMED'
            """
        )
    ).scalars()
    for reservation_id in cancelled:
        _check_outbox(
            violations, counts, reservation_id, "reservation.cancelled", "I6", "CANCELLED"
        )
    return violations


def _check_outbox(
    violations: list[Violation],
    counts: dict,
    reservation_id,
    event_type: str,
    invariant: str,
    state: str,
) -> None:
    total = counts.get((reservation_id, event_type), 0)
    if total == 0:
        violations.append(
            Violation(
                "MISSING_OUTBOX", invariant, f"reservation={reservation_id} {state} sin {event_type}"
            )
        )
    elif total > 1:
        violations.append(
            Violation(
                "DUPLICATE_OUTBOX",
                invariant,
                f"reservation={reservation_id} {state} con {total} {event_type}",
            )
        )


def check_payment(conn: sa.Connection) -> list[Violation]:
    violations = []
    double = conn.execute(
        sa.text(
            """
            SELECT p.reservation_id, count(*) AS charges
            FROM ledger l JOIN payments p ON p.id = l.payment_id
            WHERE l.kind = 'CHARGE'
            GROUP BY p.reservation_id
            HAVING count(*) > 1
            """
        )
    )
    for row in double:
        violations.append(
            Violation(
                "DOUBLE_CHARGE",
                "I3",
                f"reservation={row.reservation_id} con {row.charges} CHARGE",
            )
        )
    missing_charge = conn.execute(
        sa.text(
            """
            SELECT p.id FROM payments p
            WHERE p.status = 'SUCCEEDED'
              AND NOT EXISTS (
                SELECT 1 FROM ledger l WHERE l.payment_id = p.id AND l.kind = 'CHARGE'
              )
            """
        )
    )
    for row in missing_charge:
        violations.append(
            Violation("LEDGER_MISMATCH", "I3", f"payment={row.id} SUCCEEDED sin CHARGE")
        )
    charge_without_success = conn.execute(
        sa.text(
            """
            SELECT p.id, p.status FROM payments p
            WHERE p.status NOT IN ('SUCCEEDED', 'REFUNDED')
              AND EXISTS (
                SELECT 1 FROM ledger l WHERE l.payment_id = p.id AND l.kind = 'CHARGE'
              )
            """
        )
    )
    for row in charge_without_success:
        violations.append(
            Violation(
                "LEDGER_MISMATCH", "I3", f"payment={row.id} {row.status} con CHARGE"
            )
        )
    missing_refund = conn.execute(
        sa.text(
            """
            SELECT p.id FROM payments p
            WHERE p.status = 'REFUNDED'
              AND NOT EXISTS (
                SELECT 1 FROM ledger l WHERE l.payment_id = p.id AND l.kind = 'REFUND'
              )
            """
        )
    )
    for row in missing_refund:
        violations.append(
            Violation("LEDGER_MISMATCH", "I3", f"payment={row.id} REFUNDED sin REFUND")
        )
    return violations


def check_cross(conns: dict[str, sa.Connection], grace_seconds: int = 60) -> list[Violation]:
    violations = []
    reservations = {
        row.id: row.status
        for row in conns["reservation_db"].execute(
            sa.text("SELECT id, status FROM reservations")
        )
    }
    payments = {
        row.reservation_id: row.status
        for row in conns["payment_db"].execute(
            sa.text("SELECT reservation_id, status FROM payments")
        )
    }
    holds = conns["availability_db"].execute(
        sa.text("SELECT hold_id, status, expires_at FROM holds")
    ).all()

    confirmed = [rid for rid, status in reservations.items() if status == CONFIRMED]
    for reservation_id in confirmed:
        payment_status = payments.get(reservation_id)
        if payment_status != "SUCCEEDED":
            violations.append(
                Violation(
                    "CONFIRMED_WITHOUT_PAYMENT",
                    "I4",
                    f"reservation={reservation_id} payment={payment_status}",
                )
            )
        hold = next((h for h in holds if h.hold_id == reservation_id), None)
        if hold is None or hold.status != "CONFIRMED":
            violations.append(
                Violation(
                    "CONFIRMED_WITHOUT_PAYMENT",
                    "I4",
                    f"reservation={reservation_id} hold={getattr(hold, 'status', None)}",
                )
            )

    for reservation_id, payment_status in payments.items():
        if payment_status != "SUCCEEDED":
            continue
        status = reservations.get(reservation_id)
        if status in STABLE_STATES and status not in (CONFIRMED, MANUAL_REVIEW):
            violations.append(
                Violation(
                    "PAID_WITHOUT_SERVICE",
                    "I4",
                    f"reservation={reservation_id} status={status} payment=SUCCEEDED",
                )
            )

    now = _now()
    for hold in holds:
        if hold.status != "HELD":
            continue
        status = reservations.get(hold.hold_id)
        expired = hold.expires_at < now - dt.timedelta(seconds=grace_seconds)
        if status in STABLE_STATES and status != MANUAL_REVIEW:
            violations.append(
                Violation(
                    "LEAKED_HOLD",
                    "I5",
                    f"hold={hold.hold_id} reservation={status}",
                )
            )
        elif status is None and expired:
            violations.append(
                Violation(
                    "LEAKED_HOLD",
                    "I5",
                    f"hold={hold.hold_id} sin reserva y vencido",
                )
            )
        if status != MANUAL_REVIEW and expired:
            violations.append(
                Violation(
                    "EXPIRY_LAG",
                    "I5",
                    f"hold={hold.hold_id} vencido {hold.expires_at.isoformat()}",
                )
            )
    return violations


def check_all(grace_seconds: int = 60) -> list[Violation]:
    conns, engines = open_connections()
    try:
        return (
            check_availability(conns["availability_db"])
            + check_reservation(conns["reservation_db"], grace_seconds)
            + check_payment(conns["payment_db"])
            + check_cross(conns, grace_seconds)
        )
    finally:
        close_connections(conns, engines)


def snapshot_committed() -> dict:
    conns, engines = open_connections()
    try:
        return {
            "reservations": conns["reservation_db"].execute(
                sa.text("SELECT count(*) FROM reservations")
            ).scalar_one(),
            "confirmed": conns["reservation_db"].execute(
                sa.text("SELECT count(*) FROM reservations WHERE status = 'CONFIRMED'")
            ).scalar_one(),
            "events": conns["reservation_db"].execute(
                sa.text("SELECT count(*) FROM reservation_events")
            ).scalar_one(),
            "outbox": conns["reservation_db"].execute(
                sa.text("SELECT count(*) FROM outbox")
            ).scalar_one(),
            "payments": conns["payment_db"].execute(
                sa.text("SELECT count(*) FROM payments")
            ).scalar_one(),
            "ledger": conns["payment_db"].execute(
                sa.text("SELECT count(*) FROM ledger")
            ).scalar_one(),
            "inventory": conns["availability_db"].execute(
                sa.text("SELECT count(*) FROM inventory")
            ).scalar_one(),
            "holds": conns["availability_db"].execute(
                sa.text("SELECT count(*) FROM holds")
            ).scalar_one(),
        }
    finally:
        close_connections(conns, engines)


def assert_no_loss(before: dict, after: dict) -> None:
    for key, value in before.items():
        if after.get(key, 0) < value:
            raise AssertionError(f"se perdió {key}: {value} -> {after.get(key, 0)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="chequeador de invariantes I1-I7")
    parser.add_argument("--grace", type=int, default=60, help="margen en segundos")
    args = parser.parse_args()
    violations = check_all(grace_seconds=args.grace)
    if not violations:
        print("OK: 0 violaciones")
        return 0
    for violation in violations:
        print(violation)
    print(f"{len(violations)} violaciones")
    return 1


if __name__ == "__main__":
    sys.exit(main())
