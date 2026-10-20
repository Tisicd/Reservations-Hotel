import re
import uuid

from .errors import CustomerNotFound, ValidationError
from .models import CustomerStore

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CustomerService:
    def __init__(self, store: CustomerStore):
        self.store = store

    def create(self, name: str, email: str) -> dict:
        name = (name or "").strip()
        email = (email or "").strip().lower()
        if not 1 <= len(name) <= 120:
            raise ValidationError("name debe tener entre 1 y 120 caracteres")
        if len(email) > 254 or not EMAIL_RE.match(email):
            raise ValidationError("email inválido")
        return self.store.create(uuid.uuid4(), name, email)

    def get(self, customer_id) -> dict:
        customer = self.store.get(customer_id)
        if customer is None:
            raise CustomerNotFound("cliente no encontrado")
        return customer

    def ping(self) -> None:
        self.store.ping()
