import pytest

from app.domain.errors import IllegalTransition
from app.domain.state_machine import (
    ALLOWED_TRANSITIONS,
    CONFIRMED,
    STABLE_STATES,
    STATES,
    ensure_transition,
    is_stable,
    is_terminal,
)


def test_tabla_completa_de_transiciones():
    for current in STATES:
        for target in STATES:
            if target in ALLOWED_TRANSITIONS[current]:
                ensure_transition(current, target)
            else:
                with pytest.raises(IllegalTransition):
                    ensure_transition(current, target)


def test_transiciones_declaradas_son_estados_validos():
    for current, targets in ALLOWED_TRANSITIONS.items():
        assert current in STATES
        assert targets <= STATES


def test_confirmado_es_estable_pero_no_terminal():
    assert is_stable(CONFIRMED)
    assert not is_terminal(CONFIRMED)
    assert ALLOWED_TRANSITIONS[CONFIRMED] == frozenset({"CANCELLING"})


def test_estados_terminales_sin_salida():
    for status in STABLE_STATES - {CONFIRMED}:
        assert is_terminal(status)
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_ningun_estado_intermedio_es_estable():
    for status in STATES - STABLE_STATES:
        assert not is_stable(status)
