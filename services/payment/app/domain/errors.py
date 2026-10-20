class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class IdempotencyKeyReused(DomainError):
    pass


class InvalidState(DomainError):
    pass


class PaymentNotFound(DomainError):
    pass


class SimulationDisabled(DomainError):
    pass


class DependencyUnavailable(DomainError):
    pass
