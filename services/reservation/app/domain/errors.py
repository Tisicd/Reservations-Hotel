class DomainError(Exception):
    pass


class IllegalTransition(DomainError):
    pass


class ValidationError(DomainError):
    pass


class IdempotencyKeyReused(DomainError):
    pass


class ReservationNotFound(DomainError):
    pass


class CustomerNotFound(DomainError):
    pass


class RoomNotFound(DomainError):
    pass


class InvalidState(DomainError):
    pass


class Forbidden(DomainError):
    pass


class ConcurrentModification(DomainError):
    pass


class DependencyUnavailable(DomainError):
    def __init__(self, message: str = "dependencia no disponible", ambiguous: bool = False) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous
