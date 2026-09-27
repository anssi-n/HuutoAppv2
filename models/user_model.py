from db import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Enum
from common import common_types

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[common_types.UserRole] = mapped_column(Enum(common_types.UserRole), default=common_types.UserRole.user, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    