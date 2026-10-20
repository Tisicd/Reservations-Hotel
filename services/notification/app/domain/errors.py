class DomainError(Exception):
    """Error de negocio del servicio de notificaciones."""


class ValidationError(DomainError):
    pass


class DependencyUnavailable(DomainError):
    pass
