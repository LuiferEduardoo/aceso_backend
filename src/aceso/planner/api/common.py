from typing import Annotated, Any

from fastapi import Path

from aceso.shared.domain.errors import InvalidOperationError

ResourceId = Annotated[int, Path(ge=1)]


def reject_nulls(changes: dict[str, Any], *fields: str) -> None:
    for name in fields:
        if name in changes and changes[name] is None:
            raise InvalidOperationError(f"{name} cannot be null")
