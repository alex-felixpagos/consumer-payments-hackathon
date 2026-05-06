from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class KapsoMessageMeta(BaseModel):
    direction: str = Field(description="inbound or outbound")
    status: str = Field(description="Message status")
    processing_status: str = Field(description="Kapso processing status")
    has_media: bool = Field(default=False)
    origin: str = Field(default="cloud_api")
    content: str = Field(default="")

    model_config = ConfigDict(extra="allow")


class KapsoTextContent(BaseModel):
    body: str = Field(description="Text body")

    model_config = ConfigDict(extra="allow")


class KapsoMessage(BaseModel):
    id: str
    type: str
    timestamp: str
    from_number: str = Field(alias="from")
    context: dict[str, Any] | None = None
    kapso: KapsoMessageMeta
    text: KapsoTextContent | None = None
    image: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    contacts: list[dict[str, Any]] | None = None
    interactive: dict[str, Any] | None = None
    button: dict[str, Any] | None = None
    reaction: dict[str, Any] | None = None
    sticker: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @property
    def phone_number(self) -> str:
        return self.from_number

    @property
    def direction(self) -> str:
        return self.kapso.direction
