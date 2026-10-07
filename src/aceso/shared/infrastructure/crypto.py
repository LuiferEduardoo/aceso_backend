import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from aceso.shared.domain.errors import IntegrationError


class FernetCipher:
    """Symmetric encryption for secrets stored in the database."""

    def __init__(self, key: str) -> None:
        if not key:
            raise IntegrationError("FERNET_KEY is not configured")
        self._fernet = Fernet(key.encode())

    def encrypt_json(self, payload: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode()).decode()

    def decrypt_json(self, token: str) -> dict[str, Any]:
        try:
            return json.loads(self._fernet.decrypt(token.encode()))
        except InvalidToken as exc:
            raise IntegrationError("Stored credentials cannot be decrypted") from exc
