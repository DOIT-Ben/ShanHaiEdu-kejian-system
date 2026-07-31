"""Idempotent bootstrap for the first production access-code identity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.models import Organization, OrganizationMember, Principal, User


@dataclass(frozen=True, slots=True)
class ProductionIdentityBootstrap:
    created: bool
    organization_id: UUID
    user_id: UUID
    principal_id: UUID


def bootstrap_production_identity(
    session: Session,
    *,
    principal_id: UUID,
) -> ProductionIdentityBootstrap:
    organization_id = _derived_id(principal_id, "organization")
    user_id = _derived_id(principal_id, "user")
    membership_id = _derived_id(principal_id, "membership")
    existing = session.get(Principal, principal_id)
    if existing is not None:
        _verify_existing_identity(
            session,
            principal=existing,
            organization_id=organization_id,
            user_id=user_id,
        )
        return ProductionIdentityBootstrap(
            created=False,
            organization_id=organization_id,
            user_id=user_id,
            principal_id=principal_id,
        )

    _create_identity(
        session,
        principal_id=principal_id,
        organization_id=organization_id,
        user_id=user_id,
        membership_id=membership_id,
    )
    return ProductionIdentityBootstrap(
        created=True,
        organization_id=organization_id,
        user_id=user_id,
        principal_id=principal_id,
    )


def _create_identity(
    session: Session,
    *,
    principal_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    membership_id: UUID,
) -> None:
    now = utc_now()
    session.add_all(
        (
            Organization(
                id=organization_id,
                slug=f"production-{principal_id.hex[:12]}",
                name="ShanHaiEdu Production",
                status="active",
                created_at=now,
            ),
            User(
                id=user_id,
                email=f"teacher-{principal_id.hex[:12]}@shanhaiedu.invalid",
                display_name="ShanHai Teacher",
                status="active",
                created_at=now,
            ),
        )
    )
    session.flush()
    session.add_all(
        (
            OrganizationMember(
                id=membership_id,
                organization_id=organization_id,
                user_id=user_id,
                role="owner",
                status="active",
                created_at=now,
            ),
            Principal(
                id=principal_id,
                organization_id=organization_id,
                user_id=user_id,
                principal_type="user",
                display_name="ShanHai Teacher",
                status="active",
                created_at=now,
            ),
        )
    )
    session.flush()


def _verify_existing_identity(
    session: Session,
    *,
    principal: Principal,
    organization_id: UUID,
    user_id: UUID,
) -> None:
    membership = session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    organization = session.get(Organization, organization_id)
    user = session.get(User, user_id)
    if (
        principal.organization_id != organization_id
        or principal.user_id != user_id
        or principal.principal_type != "user"
        or principal.status != "active"
        or organization is None
        or organization.status != "active"
        or user is None
        or user.status != "active"
        or membership is None
        or membership.status != "active"
        or membership.role != "owner"
    ):
        raise RuntimeError("production identity exists with incompatible lineage")


def _derived_id(principal_id: UUID, kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"shanhaiedu-production:{principal_id}:{kind}")
