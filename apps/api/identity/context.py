"""Authenticated actor facts shared by HTTP services and workers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from apps.api.identity.models import SYSTEM_PRINCIPAL_ID


class ProjectRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ProjectAction(StrEnum):
    VIEW = "view"
    EDIT = "edit"
    GENERATE = "generate"
    REVIEW = "review"
    MANAGE_MEMBERS = "manage_members"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """Verified identity returned by an authentication adapter."""

    user_id: UUID
    organization_id: UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    organization_id: UUID
    principal_id: UUID
    user_id: UUID | None
    actor_type: Literal["user", "system"]
    organization_role: str | None = None

    @property
    def is_system(self) -> bool:
        return self.actor_type == "system"


def system_actor(organization_id: UUID) -> ActorContext:
    """Build a tenant-scoped worker actor backed by the global system principal."""

    return ActorContext(
        organization_id=organization_id,
        principal_id=SYSTEM_PRINCIPAL_ID,
        user_id=None,
        actor_type="system",
    )
