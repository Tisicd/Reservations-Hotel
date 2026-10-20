import contextvars
import json
import logging
import sys
import uuid

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def current_request_id() -> str:
    value = request_id_var.get()
    if value:
        return value
    return str(uuid.uuid4())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "level": record.levelname,
            "logger": record.name,
            "service": "reservation",
            "message": record.getMessage(),
        }
        for key in ("request_id", "reservation_id", "payment_id"):
            value = getattr(record, key, None)
            if value:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
