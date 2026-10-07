from sqlalchemy import Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


class UserModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)

    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)
