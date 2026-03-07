"""Email Sender — SMTP email dispatch with templates and queue.

Send emails via SMTP with HTML/text bodies, attachments, templates,
draft management, send queue, and delivery history.
Designed for JARVIS voice-commanded email sending.
"""

from __future__ import annotations

import logging
import smtplib
import threading
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from enum import Enum
from pathlib import Path
from typing import Any, Callable


__all__ = [
    "EmailMessage",
    "EmailSender",
    "EmailStatus",
    "EmailTemplate",
    "SmtpConfig",
]

logger = logging.getLogger("jarvis.email_sender")


class EmailStatus(Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class EmailMessage:
    """An email message."""
    msg_id: str
    to: list[str]
    subject: str
    body: str
    html: bool = False
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)  # file paths
    status: EmailStatus = EmailStatus.DRAFT
    template: str = ""
    created_at: float = field(default_factory=time.time)
    sent_at: float | None = None
    error: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class EmailTemplate:
    """Reusable email template."""
    name: str
    subject: str
    body: str
    html: bool = False
    placeholders: list[str] = field(default_factory=list)


@dataclass
class SmtpConfig:
    """SMTP server configuration."""
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_address: str = ""


class EmailSender:
    """Send emails via SMTP with templates, queue, and history."""

    def __init__(self) -> None:
        self._config = SmtpConfig()
        self._messages: dict[str, EmailMessage] = {}
        self._templates: dict[str, EmailTemplate] = {}
        self._history: list[dict[str, Any]] = []
        self._counter = 0
        self._lock = threading.Lock()
        self._transport: Callable[[EmailMessage, SmtpConfig], bool] | None = None

    # ── Configuration ───────────────────────────────────────────────

    def configure(self, host: str, port: int = 587, username: str = "",
                  password: str = "", use_tls: bool = True, from_address: str = "") -> None:
        """Configure SMTP settings."""
        self._config = SmtpConfig(
            host=host, port=port, username=username,
            password=password, use_tls=use_tls, from_address=from_address,
        )

    def set_transport(self, fn: Callable[[EmailMessage, SmtpConfig], bool]) -> None:
        """Inject custom transport for testing."""
        self._transport = fn

    def is_configured(self) -> bool:
        return bool(self._config.host)

    # ── Templates ───────────────────────────────────────────────────

    def add_template(self, name: str, subject: str, body: str,
                     html: bool = False, placeholders: list[str] | None = None) -> EmailTemplate:
        """Register an email template."""
        tmpl = EmailTemplate(name=name, subject=subject, body=body, html=html,
                             placeholders=placeholders or [])
        with self._lock:
            self._templates[name] = tmpl
        return tmpl

    def remove_template(self, name: str) -> bool:
        with self._lock:
            if name in self._templates:
                del self._templates[name]
                return True
            return False

    def list_templates(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": t.name, "subject": t.subject, "html": t.html,
                 "placeholders": t.placeholders}
                for t in self._templates.values()
            ]

    # ── Message Creation ────────────────────────────────────────────

    def create(self, to: list[str], subject: str, body: str,
               html: bool = False, cc: list[str] | None = None,
               bcc: list[str] | None = None, attachments: list[str] | None = None,
               tags: list[str] | None = None) -> EmailMessage:
        """Create a draft email."""
        with self._lock:
            self._counter += 1
            msg_id = f"email_{self._counter}"
            msg = EmailMessage(
                msg_id=msg_id, to=to, subject=subject, body=body, html=html,
                cc=cc or [], bcc=bcc or [], attachments=attachments or [],
                tags=tags or [],
            )
            self._messages[msg_id] = msg
            return msg

    def create_from_template(self, template_name: str, to: list[str],
                             variables: dict[str, str] | None = None,
                             **kwargs: Any) -> EmailMessage | None:
        """Create email from template with variable substitution."""
        with self._lock:
            tmpl = self._templates.get(template_name)
            if not tmpl:
                return None
        variables = variables or {}
        subject = tmpl.subject
        body = tmpl.body
        for key, val in variables.items():
            subject = subject.replace(f"{{{{{key}}}}}", val)
            body = body.replace(f"{{{{{key}}}}}", val)
        msg = self.create(to=to, subject=subject, body=body, html=tmpl.html, **kwargs)
        msg.template = template_name
        return msg

    # ── Sending ─────────────────────────────────────────────────────

    def send(self, msg_id: str) -> dict[str, Any]:
        """Send an email by ID."""
        with self._lock:
            msg = self._messages.get(msg_id)
            if not msg:
                return {"success": False, "error": "Message not found"}
            if msg.status == EmailStatus.SENT:
                return {"success": False, "error": "Already sent"}
            msg.status = EmailStatus.QUEUED

        success = False
        error = ""

        if self._transport:
            try:
                success = self._transport(msg, self._config)
            except Exception as e:
                error = str(e)
        elif self._config.host:
            try:
                success = self._smtp_send(msg)
            except Exception as e:
                error = str(e)
        else:
            error = "SMTP not configured"

        with self._lock:
            if success:
                msg.status = EmailStatus.SENT
                msg.sent_at = time.time()
            else:
                msg.status = EmailStatus.FAILED
                msg.error = error
            self._history.append({
                "msg_id": msg_id, "to": msg.to, "subject": msg.subject,
                "status": msg.status.value, "timestamp": time.time(), "error": error,
            })

        return {"success": success, "msg_id": msg_id, "error": error}

    def _smtp_send(self, msg: EmailMessage) -> bool:
        """Actually send via SMTP."""
        mime = MIMEMultipart()
        mime["From"] = self._config.from_address
        mime["To"] = ", ".join(msg.to)
        mime["Subject"] = msg.subject
        if msg.cc:
            mime["Cc"] = ", ".join(msg.cc)

        content_type = "html" if msg.html else "plain"
        mime.attach(MIMEText(msg.body, content_type))

        for filepath in msg.attachments:
            p = Path(filepath)
            if p.exists():
                part = MIMEBase("application", "octet-stream")
                part.set_payload(p.read_bytes())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={p.name}")
                mime.attach(part)

        all_recipients = msg.to + msg.cc + msg.bcc

        if self._config.use_tls:
            with smtplib.SMTP(self._config.host, self._config.port) as server:
                server.starttls()
                if self._config.username:
                    server.login(self._config.username, self._config.password)
                server.sendmail(self._config.from_address, all_recipients, mime.as_string())
        else:
            with smtplib.SMTP(self._config.host, self._config.port) as server:
                if self._config.username:
                    server.login(self._config.username, self._config.password)
                server.sendmail(self._config.from_address, all_recipients, mime.as_string())
        return True

    def queue_send(self, to: list[str], subject: str, body: str, **kwargs: Any) -> dict[str, Any]:
        """Create and immediately send an email."""
        msg = self.create(to=to, subject=subject, body=body, **kwargs)
        return self.send(msg.msg_id)

    # ── Query ───────────────────────────────────────────────────────

    def get(self, msg_id: str) -> EmailMessage | None:
        with self._lock:
            return self._messages.get(msg_id)

    def list_messages(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            msgs = list(self._messages.values())
            if status:
                msgs = [m for m in msgs if m.status.value == status]
            return [
                {"msg_id": m.msg_id, "to": m.to, "subject": m.subject,
                 "status": m.status.value, "template": m.template,
                 "created_at": m.created_at, "sent_at": m.sent_at, "tags": m.tags}
                for m in msgs[-limit:]
            ]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            by_status: dict[str, int] = {}
            for m in self._messages.values():
                by_status[m.status.value] = by_status.get(m.status.value, 0) + 1
            return {
                "total_messages": len(self._messages),
                "by_status": by_status,
                "total_templates": len(self._templates),
                "total_sent": by_status.get("sent", 0),
                "total_failed": by_status.get("failed", 0),
                "configured": self.is_configured(),
            }


# ── Singleton ───────────────────────────────────────────────────────
email_sender = EmailSender()
