"""
The Config Field type: one setting a Spider or Notificator needs from the user.

Spiders and Notificators declare a sequence of these, and the Core renders each one as a form
input. Deliberately framework-free, so Plugins can depend on it without pulling in Django.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigField:
    """
    :param key: Key the value is stored under in the Query's or Notification Profile's config.
    :param label: Human-readable label shown next to the input.
    :param required: Whether a value must be entered before saving.
    :param secret: Whether the input is rendered as a password input. Values are still stored
        as plain text.
    :param help_text: Optional hint shown under the input.
    :param choices: If set, the value must be one of these, and the input is rendered as a select.
    :param default: Value pre-filled when there's no stored value yet.
    """

    key: str
    label: str
    required: bool = False
    secret: bool = False
    help_text: str = ""
    choices: tuple[str, ...] | None = None
    default: str | None = None
