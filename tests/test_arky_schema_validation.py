"""Unit tests for Arky Pydantic schemas — input validation."""
import pytest
from pydantic import ValidationError

from app.http.schemas.arky import ArkyChatRequest, ScreenContextSchema, UIStateSchema


class TestArkyChatRequest:
    def test_valid_minimal_request(self):
        req = ArkyChatRequest(message="olá Arky")
        assert req.message == "olá Arky"
        assert req.screen is None
        assert req.conversation_id is None

    def test_message_is_required(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest()

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="")

    def test_message_whitespace_only_rejected(self):
        # strip() + min_length=1 should catch this
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="   ")

    def test_message_max_length_2000(self):
        ArkyChatRequest(message="x" * 2000)

    def test_message_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="x" * 2001)

    def test_message_is_stripped(self):
        req = ArkyChatRequest(message="  hello world  ")
        assert req.message == "hello world"

    def test_screenshot_max_length(self):
        # Just under limit should pass
        ArkyChatRequest(message="test", screenshot="a" * 519_999)

    def test_screenshot_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="test", screenshot="a" * 521_000)

    def test_conversation_id_max_length(self):
        import uuid
        ArkyChatRequest(message="test", conversation_id=str(uuid.uuid4()))

    def test_conversation_id_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="test", conversation_id="x" * 37)

    def test_intent_hint_max_length(self):
        ArkyChatRequest(message="test", intent_hint="x" * 100)

    def test_intent_hint_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ArkyChatRequest(message="test", intent_hint="x" * 101)


class TestScreenContextSchema:
    def test_defaults(self):
        ctx = ScreenContextSchema()
        assert ctx.route == "/"
        assert ctx.path == "/"
        assert ctx.title == ""
        assert ctx.module == ""

    def test_module_max_length(self):
        ScreenContextSchema(module="x" * 50)

    def test_module_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ScreenContextSchema(module="x" * 51)


class TestUIStateSchema:
    def test_empty_state_valid(self):
        state = UIStateSchema()
        assert state.filters is None
        assert state.visible_tab is None

    def test_visible_tab_max_length(self):
        UIStateSchema(visible_tab="x" * 50)

    def test_visible_tab_too_long_rejected(self):
        with pytest.raises(ValidationError):
            UIStateSchema(visible_tab="x" * 51)

    def test_filters_accepts_dict(self):
        state = UIStateSchema(filters={"status": "all", "page": 1})
        assert state.filters == {"status": "all", "page": 1}
