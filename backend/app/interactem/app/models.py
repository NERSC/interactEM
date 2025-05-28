import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel
from sqlmodel import (
    JSON,
    Column,
    Field,
    Relationship,
    SQLModel,
)

from interactem.core.models.base import PipelineDeploymentState
from interactem.core.models.canonical import (
    CanonicalPipelineData,
    CanonicalPipelineRevisionID,
)
from interactem.core.models.spec import OperatorSpec


# Shared properties
class UserBase(SQLModel):
    username: str = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    is_external: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    username: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    username: str | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    pipelines: list["Pipeline"] = Relationship(
        back_populates="owner", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    nats_jwt: str


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class ExternalTokenPayload(SQLModel):
    username: str
    exp: int


class PipelineBase(SQLModel):
    name: str | None = Field(
        index=True, max_length=128, default="New Pipeline", nullable=True
    )
    # we store as JSON, but validate as CanonicalPipelineData before
    data: dict[str, Any] = Field(sa_column=Column(JSON))


class Pipeline(PipelineBase, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        index=True,
        nullable=False,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )

    owner: User | None = Relationship(back_populates="pipelines")
    revisions: list["PipelineRevision"] = Relationship(
        back_populates="pipeline",
        cascade_delete=True,
        sa_relationship_kwargs={"order_by": "PipelineRevision.revision_id"},
    )
    current_revision_id: CanonicalPipelineRevisionID = Field(
        default=0,
        index=True,
        nullable=False,
    )


class PipelineRevision(SQLModel, table=True):
    pipeline_id: uuid.UUID = Field(
        foreign_key="pipeline.id", primary_key=True, index=True, ondelete="CASCADE"
    )
    revision_id: CanonicalPipelineRevisionID = Field(primary_key=True, index=True)
    data: dict[str, Any] = Field(sa_column=Column(JSON))
    tag: str | None = Field(default=None, max_length=128)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )
    pipeline: "Pipeline" = Relationship(back_populates="revisions")
    deployments: list["PipelineDeployment"] = Relationship(
        back_populates="revision", cascade_delete=True
    )


class PipelineCreate(SQLModel):
    data: dict[str, Any]


class PipelineUpdate(SQLModel):
    name: str | None = Field(..., max_length=128)


class PipelineRevisionCreate(SQLModel):
    data: dict[str, Any]


class PipelineRevisionUpdate(SQLModel):
    tag: str | None = Field(default=None, max_length=128)


class PipelinePublic(PipelineBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    updated_at: datetime
    created_at: datetime
    current_revision_id: CanonicalPipelineRevisionID
    data: CanonicalPipelineData


class PipelinesPublic(SQLModel):
    data: list[PipelinePublic]
    count: int


class PipelineRevisionPublic(SQLModel):
    pipeline_id: uuid.UUID
    revision_id: CanonicalPipelineRevisionID
    data: CanonicalPipelineData
    tag: str | None
    created_at: datetime


class PipelineDeployment(SQLModel, table=True):
    """Represents a single deployment of a pipeline, related to a specific revision."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    pipeline_id: uuid.UUID = Field(index=True)
    revision_id: CanonicalPipelineRevisionID = Field(index=True)
    state: PipelineDeploymentState = Field(
        default=PipelineDeploymentState.PENDING, index=True
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
        sa_type=sa.DateTime(timezone=True),  # type: ignore
    )

    # Foreign key to PipelineRevision (needed for composite key)
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["pipeline_id", "revision_id"],
            ["pipelinerevision.pipeline_id", "pipelinerevision.revision_id"],
            ondelete="CASCADE",
        ),
    )

    revision: "PipelineRevision" = Relationship(back_populates="deployments")


class PipelineDeploymentCreate(SQLModel):
    pipeline_id: uuid.UUID
    revision_id: CanonicalPipelineRevisionID


class PipelineDeploymentUpdate(SQLModel):
    state: PipelineDeploymentState


class PipelineDeploymentPublic(SQLModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    revision_id: CanonicalPipelineRevisionID
    state: PipelineDeploymentState
    created_at: datetime
    updated_at: datetime


class PipelineDeploymentsPublic(SQLModel):
    data: list[PipelineDeploymentPublic]
    count: int


class OperatorSpecs(BaseModel):
    data: list[OperatorSpec]
