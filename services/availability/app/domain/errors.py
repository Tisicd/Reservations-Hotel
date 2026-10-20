class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class InvalidDateRange(DomainError):
    pass


class NoInventory(DomainError):
    pass


class HoldConflict(DomainError):
    pass


class HoldExpired(DomainError):
    pass


class InvalidState(DomainError):
    pass


class HoldNotFound(DomainError):
    pass


class InventoryBelowCommitted(DomainError):
    pass


class DependencyUnavailable(DomainError):
    pass
