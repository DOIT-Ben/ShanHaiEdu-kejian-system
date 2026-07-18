"""Tenant-scoped creation lifecycle queries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.creation.models import (
    Adoption,
    CreationBatch,
    CreationItem,
    CreationPackage,
    CreationPackageItem,
    CreationPromptVersion,
    GenerationResult,
)


@dataclass(frozen=True, slots=True)
class ItemContext:
    item: CreationItem
    batch: CreationBatch


@dataclass(frozen=True, slots=True)
class ResultContext:
    result: GenerationResult
    item: CreationItem
    batch: CreationBatch


@dataclass(frozen=True, slots=True)
class AdoptionContext:
    adoption: Adoption
    result: GenerationResult
    item: CreationItem
    batch: CreationBatch


class CreationRepository:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def get_package(
        self,
        package_id: UUID,
        *,
        for_update: bool = False,
    ) -> CreationPackage | None:
        statement = select(CreationPackage).where(
            CreationPackage.id == package_id,
            CreationPackage.organization_id == self._organization_id,
        )
        if for_update:
            statement = statement.with_for_update(of=CreationPackage)
        return self._session.scalar(statement)

    def package_items(self, package_id: UUID) -> list[CreationPackageItem]:
        return list(
            self._session.scalars(
                select(CreationPackageItem)
                .where(CreationPackageItem.creation_package_id == package_id)
                .order_by(CreationPackageItem.position, CreationPackageItem.id)
            )
        )

    def get_batch(self, batch_id: UUID, *, for_update: bool = False) -> CreationBatch | None:
        statement = select(CreationBatch).where(
            CreationBatch.id == batch_id,
            CreationBatch.organization_id == self._organization_id,
            CreationBatch.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update(of=CreationBatch)
        return self._session.scalar(statement)

    def batch_items(self, batch_id: UUID) -> list[CreationItem]:
        return list(
            self._session.scalars(
                select(CreationItem)
                .where(
                    CreationItem.creation_batch_id == batch_id,
                    CreationItem.organization_id == self._organization_id,
                    CreationItem.deleted_at.is_(None),
                )
                .order_by(CreationItem.created_at, CreationItem.id)
            )
        )

    def get_item_context(
        self,
        item_id: UUID,
        *,
        for_update: bool = False,
    ) -> ItemContext | None:
        statement = (
            select(CreationItem, CreationBatch)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .where(
                CreationItem.id == item_id,
                CreationItem.organization_id == self._organization_id,
                CreationItem.deleted_at.is_(None),
                CreationBatch.organization_id == self._organization_id,
                CreationBatch.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=(CreationItem, CreationBatch))
        row = self._session.execute(statement).one_or_none()
        return None if row is None else ItemContext(item=row[0], batch=row[1])

    def get_prompt_version(
        self,
        prompt_version_id: UUID,
    ) -> CreationPromptVersion | None:
        return self._session.scalar(
            select(CreationPromptVersion).where(
                CreationPromptVersion.id == prompt_version_id,
                CreationPromptVersion.organization_id == self._organization_id,
            )
        )

    def next_prompt_version(self, item_id: UUID) -> int:
        return (
            self._session.scalar(
                select(func.max(CreationPromptVersion.version_no)).where(
                    CreationPromptVersion.creation_item_id == item_id
                )
            )
            or 0
        ) + 1

    def get_result_context(
        self,
        result_id: UUID,
        *,
        for_update: bool = False,
    ) -> ResultContext | None:
        statement = (
            select(GenerationResult, CreationItem, CreationBatch)
            .join(CreationItem, CreationItem.id == GenerationResult.creation_item_id)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .where(
                GenerationResult.id == result_id,
                GenerationResult.organization_id == self._organization_id,
                CreationItem.organization_id == self._organization_id,
                CreationBatch.organization_id == self._organization_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(
                of=(GenerationResult, CreationItem, CreationBatch)
            )
        row = self._session.execute(statement).one_or_none()
        return None if row is None else ResultContext(result=row[0], item=row[1], batch=row[2])

    def get_adoption_context(
        self,
        adoption_id: UUID,
        *,
        for_update: bool = False,
    ) -> AdoptionContext | None:
        statement = (
            select(Adoption, GenerationResult, CreationItem, CreationBatch)
            .join(GenerationResult, GenerationResult.id == Adoption.generation_result_id)
            .join(CreationItem, CreationItem.id == Adoption.creation_item_id)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .where(
                Adoption.id == adoption_id,
                Adoption.organization_id == self._organization_id,
                GenerationResult.organization_id == self._organization_id,
                CreationItem.organization_id == self._organization_id,
                CreationBatch.organization_id == self._organization_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(
                of=(Adoption, GenerationResult, CreationItem, CreationBatch)
            )
        row = self._session.execute(statement).one_or_none()
        return (
            None
            if row is None
            else AdoptionContext(adoption=row[0], result=row[1], item=row[2], batch=row[3])
        )
