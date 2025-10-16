from datetime import datetime

from pydantic import BaseModel

from interactem.core.models.spec import OperatorSpec


class PipelineData(BaseModel):
    operators: list[dict] = []
    ports: list[dict] = []
    edges: list[dict] = []


class PipelinePayload(BaseModel):
    data: PipelineData


class PipelineResponse(BaseModel):
    id: str
    name: str
    data: PipelineData
    owner_id: str
    created_at: datetime
    updated_at: datetime
    current_revision_id: int


class PipelinesListResponse(BaseModel):
    data: list[PipelineResponse]
    count: int


class TemplateContext(BaseModel):
    """Context data for Jinja2 templates."""

    spec: OperatorSpec
    name: str
    function_name: str
    base_image: str
    additional_packages: list[str] | None = None
