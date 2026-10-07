class DomainError(Exception):
    """Base class for errors raised by domain and application layers."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class InvalidOperationError(DomainError):
    pass


class AuthenticationError(DomainError):
    pass


class IntegrationError(DomainError):
    """An external provider (Strava, Garmin...) failed or is not configured."""
