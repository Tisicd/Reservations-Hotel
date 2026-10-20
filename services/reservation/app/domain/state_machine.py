from .errors import IllegalTransition

RECEIVED = "RECEIVED"
HELD = "HELD"
PAYMENT_PENDING = "PAYMENT_PENDING"
PAYMENT_UNKNOWN = "PAYMENT_UNKNOWN"
PAID = "PAID"
CONFIRMED = "CONFIRMED"
PAYMENT_DECLINED = "PAYMENT_DECLINED"
REFUND_REQUIRED = "REFUND_REQUIRED"
CANCELLING = "CANCELLING"
CANCELLED = "CANCELLED"
REJECTED_NO_INVENTORY = "REJECTED_NO_INVENTORY"
FAILED_TECHNICAL = "FAILED_TECHNICAL"
MANUAL_REVIEW = "MANUAL_REVIEW"

STATES = frozenset(
    {
        RECEIVED,
        HELD,
        PAYMENT_PENDING,
        PAYMENT_UNKNOWN,
        PAID,
        CONFIRMED,
        PAYMENT_DECLINED,
        REFUND_REQUIRED,
        CANCELLING,
        CANCELLED,
        REJECTED_NO_INVENTORY,
        FAILED_TECHNICAL,
        MANUAL_REVIEW,
    }
)

STABLE_STATES = frozenset(
    {CONFIRMED, REJECTED_NO_INVENTORY, FAILED_TECHNICAL, CANCELLED, MANUAL_REVIEW}
)

# Terminales sin salida: solo CONFIRMED puede cambiar (a CANCELLING).
TERMINAL_STATES = STABLE_STATES - {CONFIRMED}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    RECEIVED: frozenset({HELD, REJECTED_NO_INVENTORY, FAILED_TECHNICAL}),
    HELD: frozenset({PAYMENT_PENDING}),
    PAYMENT_PENDING: frozenset({PAID, PAYMENT_DECLINED, PAYMENT_UNKNOWN}),
    PAYMENT_UNKNOWN: frozenset({PAID, PAYMENT_DECLINED, PAYMENT_PENDING, MANUAL_REVIEW}),
    PAID: frozenset({CONFIRMED, REFUND_REQUIRED, MANUAL_REVIEW}),
    PAYMENT_DECLINED: frozenset({CANCELLED}),
    REFUND_REQUIRED: frozenset({CANCELLED, MANUAL_REVIEW}),
    CONFIRMED: frozenset({CANCELLING}),
    CANCELLING: frozenset({CANCELLED}),
    CANCELLED: frozenset(),
    REJECTED_NO_INVENTORY: frozenset(),
    FAILED_TECHNICAL: frozenset(),
    MANUAL_REVIEW: frozenset(),
}


def is_stable(status: str) -> bool:
    return status in STABLE_STATES


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES


def ensure_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(f"transición inválida {current} -> {target}")
