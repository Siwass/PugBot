from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
    )

    title: Mapped[str] = mapped_column(String(255))

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    admins: Mapped[list["ChannelAdmin"]] = relationship(
        back_populates="channel",
    )

    posts: Mapped[list["Post"]] = relationship(
        back_populates="channel",
    )


class ChannelAdmin(Base):
    __tablename__ = "channel_admins"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_admin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger)

    role: Mapped[str] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    channel: Mapped["Channel"] = relationship(
        back_populates="admins",
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)

    author_id: Mapped[int] = mapped_column(BigInteger)

    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id"),
        nullable=True,
    )

    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    media: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    buttons: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
    )

    publish_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Данные опубликованного сообщения в Telegram (для удаления)
    telegram_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Автоудаление: через сколько часов после публикации удалить (None = не удалять)
    auto_delete_hours: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    auto_delete_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    channel: Mapped["Channel | None"] = relationship(
        back_populates="posts",
    )


class Template(Base):
    """Шаблон поста. Позже можно расширить полями variables/schema."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger)

    name: Mapped[str] = mapped_column(String(120))

    text: Mapped[str] = mapped_column(Text)

    buttons: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    default_channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id"),
        nullable=True,
    )

    # IANA timezone, например Europe/Kyiv
    timezone: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Дефолтное автоудаление для новых постов (часы): 24/48/72/96 или None
    default_auto_delete_hours: Mapped[int | None] = mapped_column(
        nullable=True,
    )


class BotAdmin(Base):
    """Пользователи, которым разрешено пользоваться PugBot."""

    __tablename__ = "bot_admins"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_owner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
