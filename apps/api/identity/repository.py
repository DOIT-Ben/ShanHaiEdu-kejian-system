"""Persistence boundary for resolving verified identities into active actors."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.models import Organization, OrganizationMember, Principal, User


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_actor(self, identity: AuthenticatedIdentity) -> ActorContext:
        statement = (
            select(User, Organization, OrganizationMember, Principal)
            .join(
                OrganizationMember,
                OrganizationMember.user_id == User.id,
            )
            .join(
                Organization,
                Organization.id == OrganizationMember.organization_id,
            )
            .join(
                Principal,
                (Principal.user_id == User.id)
                & (Principal.organization_id == Organization.id)
                & (Principal.principal_type == "user"),
            )
            .where(
                User.id == identity.user_id,
                Organization.id == identity.organization_id,
            )
        )
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise self._permission_denied()
        user, organization, membership, principal = row
        if any(
            status != "active"
            for status in (
                user.status,
                organization.status,
                membership.status,
                principal.status,
            )
        ):
            raise self._permission_denied()
        return ActorContext(
            organization_id=organization.id,
            principal_id=principal.id,
            user_id=user.id,
            actor_type="user",
            organization_role=membership.role,
        )

    @staticmethod
    def _permission_denied() -> ApiError:
        return ApiError(
            status_code=403,
            code="PERMISSION_DENIED",
            message="The authenticated identity is not allowed to access this organization.",
        )
