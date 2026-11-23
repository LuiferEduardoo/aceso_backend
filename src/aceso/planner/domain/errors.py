from aceso.shared.domain.errors import IntegrationError


class SyncTokenExpiredError(IntegrationError):
    """Google answered 410 Gone: the incremental sync token is no longer valid."""


class RemoteEventMissingError(IntegrationError):
    """The Google event we tried to change no longer exists (404/410)."""
