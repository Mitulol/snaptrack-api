"""Outbound-message delivery.

There is no SMTP server in a laptop-only stack, so "delivery" is pluggable:

* ``console`` — log the message (the default; what CI and the dev stack use).
* ``file``    — write an RFC-822 ``.eml`` into ``NOTIFICATION_MAIL_DIR`` so you
  can open it in a mail client. The compose ``worker`` mounts that dir.

Swapping in a real backend (SMTP, SES, a push provider) is a new branch here
and nothing else changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.config import settings

logger = logging.getLogger("snaptrack.mailer")


class NotificationDeliveryError(Exception):
    """Delivery failed in a way a retry might fix."""


def deliver_email(*, to: str, subject: str, body: str) -> str:
    """Deliver one message via the configured backend. Returns a transport id."""
    backend = settings.notification_backend
    if backend == "console":
        logger.info("email delivered (console) to=%s subject=%s\n%s", to, subject, body)
        return "console"
    if backend == "file":
        return _write_eml(to=to, subject=subject, body=body)
    raise NotificationDeliveryError(f"unknown notification backend: {backend!r}")


def _write_eml(*, to: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["From"] = settings.notification_from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    msg.set_content(body)

    out_dir = Path(settings.notification_mail_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.eml"
    path = out_dir / name
    try:
        path.write_bytes(bytes(msg))
    except OSError as exc:  # disk full, permissions, ...
        raise NotificationDeliveryError(f"could not write {path}: {exc}") from exc
    logger.info("email delivered (file) to=%s path=%s", to, path)
    return str(path)
