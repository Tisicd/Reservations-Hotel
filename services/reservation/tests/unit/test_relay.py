import uuid
from dataclasses import replace

from app.application.relay import OutboxRelay
from app.domain.outbox import OutboxEvent


class FakeOutbox:
    def __init__(self, events):
        self.pending = list(events)
        self.sent = []
        self.rescheduled = []

    def claim_outbox(self, limit, lease_seconds):
        claimed = self.pending[:limit]
        self.pending = self.pending[limit:]
        return [replace(event, attempts=event.attempts + 1) for event in claimed]

    def mark_outbox_sent(self, outbox_id):
        self.sent.append(outbox_id)

    def reschedule_outbox(self, outbox_id, delay_seconds):
        self.rescheduled.append((outbox_id, delay_seconds))


class FakeSender:
    def __init__(self, failures=0):
        self.failures = failures
        self.events = []

    def send(self, event):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("notification caída")
        self.events.append(event)


def _event(attempts=0):
    return OutboxEvent(
        id=uuid.uuid4(),
        aggregate_id=uuid.uuid4(),
        type="reservation.confirmed",
        payload={"customer_id": str(uuid.uuid4())},
        attempts=attempts,
    )


def test_entrega_marca_enviado():
    repo = FakeOutbox([_event(), _event()])
    sender = FakeSender()
    relay = OutboxRelay(repo, sender)

    assert relay.relay_due(10) == 2
    assert len(repo.sent) == 2
    assert repo.rescheduled == []


def test_fallo_reprograma_sin_marcar_enviado():
    event = _event()
    repo = FakeOutbox([event])
    sender = FakeSender(failures=1)
    relay = OutboxRelay(repo, sender, backoff_base_seconds=0.5)

    assert relay.relay_due(10) == 0
    assert repo.sent == []
    assert repo.rescheduled == [(event.id, 0.5)]


def test_backoff_crece_con_los_intentos():
    relay = OutboxRelay(
        FakeOutbox([]), FakeSender(), backoff_base_seconds=0.5, backoff_max_seconds=3
    )
    assert relay._delay(1) == 0.5
    assert relay._delay(3) == 2.0
    assert relay._delay(10) == 3.0


def test_cuerpo_del_evento():
    event = _event()
    body = OutboxRelay.event_body(event)
    assert body["event_id"] == str(event.id)
    assert body["reservation_id"] == str(event.aggregate_id)
    assert body["customer_id"] == event.payload["customer_id"]
