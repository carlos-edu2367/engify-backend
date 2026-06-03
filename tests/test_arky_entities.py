"""Unit tests for ArkyActionPreview domain entity."""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.entities.arky import ArkyActionPreview


def _make_preview(**kwargs) -> ArkyActionPreview:
    defaults = dict(
        team_id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        action_type="prepare_create_obra",
        payload={"title": "Test"},
        summary="Criar obra: Test",
        risk_level="preparacao",
    )
    defaults.update(kwargs)
    return ArkyActionPreview(**defaults)


class TestArkyActionPreview:
    def test_new_preview_is_pending(self):
        p = _make_preview()
        assert p.status == "pending"

    def test_confirm_changes_status(self):
        p = _make_preview()
        p.confirm()
        assert p.status == "confirmed"
        assert p.confirmed_at is not None

    def test_reject_changes_status(self):
        p = _make_preview()
        p.reject()
        assert p.status == "rejected"
        assert p.rejected_at is not None

    def test_cannot_confirm_already_confirmed(self):
        p = _make_preview()
        p.confirm()
        with pytest.raises(ValueError):
            p.confirm()

    def test_cannot_confirm_expired(self):
        p = _make_preview(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        with pytest.raises(ValueError):
            p.confirm()
        assert p.status == "expired"

    def test_cannot_reject_already_rejected(self):
        p = _make_preview()
        p.reject()
        with pytest.raises(ValueError):
            p.reject()

    def test_is_expired_when_past_expires_at(self):
        p = _make_preview(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        assert p.is_expired() is True

    def test_not_expired_when_within_window(self):
        p = _make_preview()
        assert p.is_expired() is False
