# domain/feed/value_objects.py
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from src.domain.shared.base_value_object import ValueObject


class FeedItemStatus(StrEnum):
    UNREAD  = "unread"
    READ    = "read"
    SAVED   = "saved"
    SKIPPED = "skipped"


class NotificationChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL    = "email"
    PUSH     = "push"
    NONE     = "none"


@dataclass(frozen=True)
class UserPreference(ValueObject):
    max_items_per_feed: int = 50
    notification_channel: NotificationChannel = NotificationChannel.NONE
    recency_decay_hours: float = 24.0  # score * e^(-age/decay)
    show_rejected: bool = False