from aceso.shared.domain.errors import IntegrationError


class SyncTokenExpiredError(IntegrationError):
    """Google answered 410 Gone: the incremental sync token is no longer valid."""
