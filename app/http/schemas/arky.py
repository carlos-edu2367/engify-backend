from typing import Any
from pydantic import BaseModel, Field, field_validator


class ScreenContextSchema(BaseModel):
    route: str = Field(default="/", max_length=200)
    path: str = Field(default="/", max_length=200)
    title: str = Field(default="", max_length=100)
    module: str = Field(default="", max_length=50)


class SelectionContextSchema(BaseModel):
    entity_type: str = Field(default="", max_length=50)
    entity_id: str | None = Field(default=None, max_length=36)


class UIStateSchema(BaseModel):
    filters: dict[str, Any] | None = None
    visible_tab: str | None = Field(default=None, max_length=50)


class ArkyChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    screen: ScreenContextSchema | None = None
    selection: SelectionContextSchema | None = None
    ui_state: UIStateSchema | None = None
    conversation_id: str | None = Field(default=None, max_length=36)
    intent_hint: str | None = Field(default=None, max_length=100)
    # Base64-encoded JPEG screenshot (max ~500KB after base64 ≈ 375KB raw)
    screenshot: str | None = Field(default=None, max_length=520_000)

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        # Strip before min_length is checked so whitespace-only is rejected
        return v.strip() if isinstance(v, str) else v


class ArkyCardResponse(BaseModel):
    type: str
    title: str
    summary: str
    risk: str = "leitura"
    requires_confirmation: bool = False
    action_preview_id: str | None = None


class ArkyActionResponse(BaseModel):
    type: str
    label: str
    action_preview_id: str | None = None
    to: str | None = None


class ArkyChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    message: str
    intent: str = "general"
    cards: list[ArkyCardResponse] = []
    actions: list[ArkyActionResponse] = []
    citations: list[dict] = []


class ArkyConfirmRequest(BaseModel):
    pass  # preview_id comes from path param


class ArkyConfirmResponse(BaseModel):
    action_preview_id: str
    status: str
    message: str
