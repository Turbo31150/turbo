"""Tests for src/email_sender.py — SMTP email dispatch with templates.

Covers: EmailStatus, EmailMessage, EmailTemplate, SmtpConfig, EmailSender
(configure, is_configured, set_transport, add/remove/list templates,
create, create_from_template, send, queue_send, get, list_messages,
get_history, get_stats), email_sender singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.email_sender import (
    EmailStatus, EmailMessage, EmailTemplate, SmtpConfig, EmailSender, email_sender,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestEmailStatus:
    def test_values(self):
        assert EmailStatus.DRAFT.value == "draft"
        assert EmailStatus.QUEUED.value == "queued"
        assert EmailStatus.SENT.value == "sent"
        assert EmailStatus.FAILED.value == "failed"


class TestEmailMessage:
    def test_defaults(self):
        m = EmailMessage(msg_id="e1", to=["a@b.com"], subject="Hi", body="Hello")
        assert m.html is False
        assert m.cc == []
        assert m.bcc == []
        assert m.attachments == []
        assert m.status == EmailStatus.DRAFT
        assert m.template == ""
        assert m.created_at > 0
        assert m.sent_at is None
        assert m.error == ""
        assert m.tags == []


class TestEmailTemplate:
    def test_defaults(self):
        t = EmailTemplate(name="welcome", subject="Welcome", body="Hi {{name}}")
        assert t.html is False
        assert t.placeholders == []


class TestSmtpConfig:
    def test_defaults(self):
        c = SmtpConfig()
        assert c.host == ""
        assert c.port == 587
        assert c.use_tls is True


# ===========================================================================
# EmailSender — configure
# ===========================================================================

class TestConfigure:
    def test_configure(self):
        es = EmailSender()
        es.configure("smtp.gmail.com", 465, "user", "pass", from_address="me@x.com")
        assert es.is_configured() is True
        assert es._config.host == "smtp.gmail.com"
        assert es._config.port == 465

    def test_not_configured(self):
        es = EmailSender()
        assert es.is_configured() is False


# ===========================================================================
# EmailSender — templates
# ===========================================================================

class TestTemplates:
    def test_add_template(self):
        es = EmailSender()
        t = es.add_template("welcome", "Hello {{name}}", "Body {{name}}")
        assert t.name == "welcome"

    def test_list_templates(self):
        es = EmailSender()
        es.add_template("a", "Subject A", "Body A")
        es.add_template("b", "Subject B", "Body B", html=True)
        result = es.list_templates()
        assert len(result) == 2
        assert any(t["name"] == "a" for t in result)

    def test_remove_template(self):
        es = EmailSender()
        es.add_template("x", "S", "B")
        assert es.remove_template("x") is True
        assert es.remove_template("x") is False

    def test_list_templates_empty(self):
        es = EmailSender()
        assert es.list_templates() == []


# ===========================================================================
# EmailSender — create
# ===========================================================================

class TestCreate:
    def test_create_draft(self):
        es = EmailSender()
        msg = es.create(to=["a@b.com"], subject="Test", body="Hello")
        assert msg.msg_id == "email_1"
        assert msg.status == EmailStatus.DRAFT
        assert msg.to == ["a@b.com"]

    def test_create_with_options(self):
        es = EmailSender()
        msg = es.create(
            to=["a@b.com"], subject="S", body="B",
            html=True, cc=["c@d.com"], bcc=["e@f.com"],
            attachments=["file.txt"], tags=["urgent"],
        )
        assert msg.html is True
        assert msg.cc == ["c@d.com"]
        assert msg.tags == ["urgent"]

    def test_increments_counter(self):
        es = EmailSender()
        m1 = es.create(to=["a@b.com"], subject="1", body="1")
        m2 = es.create(to=["a@b.com"], subject="2", body="2")
        assert m1.msg_id == "email_1"
        assert m2.msg_id == "email_2"


# ===========================================================================
# EmailSender — create_from_template
# ===========================================================================

class TestCreateFromTemplate:
    def test_with_variables(self):
        es = EmailSender()
        es.add_template("welcome", "Hello {{name}}", "Dear {{name}}, welcome!")
        msg = es.create_from_template("welcome", ["a@b.com"], variables={"name": "Turbo"})
        assert msg is not None
        assert msg.subject == "Hello Turbo"
        assert "Dear Turbo" in msg.body
        assert msg.template == "welcome"

    def test_nonexistent_template(self):
        es = EmailSender()
        assert es.create_from_template("nope", ["a@b.com"]) is None


# ===========================================================================
# EmailSender — send
# ===========================================================================

class TestSend:
    def test_not_found(self):
        es = EmailSender()
        result = es.send("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_already_sent(self):
        es = EmailSender()
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        msg.status = EmailStatus.SENT
        result = es.send(msg.msg_id)
        assert result["success"] is False
        assert "Already sent" in result["error"]

    def test_custom_transport_success(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: True)
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert result["success"] is True
        assert msg.status == EmailStatus.SENT
        assert msg.sent_at is not None

    def test_custom_transport_failure(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: False)
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert result["success"] is False
        assert msg.status == EmailStatus.FAILED

    def test_custom_transport_exception(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: (_ for _ in ()).throw(Exception("SMTP down")))
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert result["success"] is False
        assert "SMTP down" in result["error"]

    def test_not_configured_error(self):
        es = EmailSender()
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert result["success"] is False
        assert "not configured" in result["error"]

    def test_records_history(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: True)
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        es.send(msg.msg_id)
        assert len(es.get_history()) == 1
        assert es.get_history()[0]["status"] == "sent"


# ===========================================================================
# EmailSender — queue_send
# ===========================================================================

class TestQueueSend:
    def test_creates_and_sends(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: True)
        result = es.queue_send(to=["a@b.com"], subject="Quick", body="Fast")
        assert result["success"] is True


# ===========================================================================
# EmailSender — query
# ===========================================================================

class TestQuery:
    def test_get_existing(self):
        es = EmailSender()
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        assert es.get(msg.msg_id) is not None

    def test_get_missing(self):
        es = EmailSender()
        assert es.get("nope") is None

    def test_list_messages_empty(self):
        es = EmailSender()
        assert es.list_messages() == []

    def test_list_messages_with_data(self):
        es = EmailSender()
        es.create(to=["a@b.com"], subject="1", body="1")
        es.create(to=["b@c.com"], subject="2", body="2")
        result = es.list_messages()
        assert len(result) == 2

    def test_list_messages_filter_status(self):
        es = EmailSender()
        es.set_transport(lambda msg, cfg: True)
        es.create(to=["a@b.com"], subject="Draft", body="D")
        m = es.create(to=["a@b.com"], subject="Sent", body="S")
        es.send(m.msg_id)
        drafts = es.list_messages(status="draft")
        assert len(drafts) == 1
        sent = es.list_messages(status="sent")
        assert len(sent) == 1


# ===========================================================================
# EmailSender — get_stats
# ===========================================================================

class TestGetStats:
    def test_empty(self):
        es = EmailSender()
        stats = es.get_stats()
        assert stats["total_messages"] == 0
        assert stats["total_templates"] == 0
        assert stats["configured"] is False

    def test_with_data(self):
        es = EmailSender()
        es.configure("smtp.test.com")
        es.add_template("t1", "S", "B")
        es.set_transport(lambda msg, cfg: True)
        es.create(to=["a@b.com"], subject="Draft", body="D")
        m = es.create(to=["a@b.com"], subject="Sent", body="S")
        es.send(m.msg_id)
        stats = es.get_stats()
        assert stats["total_messages"] == 2
        assert stats["total_templates"] == 1
        assert stats["total_sent"] == 1
        assert stats["configured"] is True


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert email_sender is not None
        assert isinstance(email_sender, EmailSender)
