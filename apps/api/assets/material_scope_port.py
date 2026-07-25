"""Asset-owned exact material facts for material-scope authoring."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.repository import FileAssetRepository
from apps.api.identity.context import ActorContext


@dataclass(frozen=True, slots=True)
class MaterialScopeSourceFact:
    material_id: UUID
    project_id: UUID
    original_filename: str
    parse_version_id: UUID
    parse_status: str
    page_count: int | None
    parse_content: object


class MaterialScopeSourceReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._repository = FileAssetRepository(session, actor)

    def get(
        self,
        *,
        project_id: UUID,
        material_id: UUID,
        parse_version_id: UUID,
    ) -> MaterialScopeSourceFact | None:
        material = self._repository.get_material(material_id)
        parsed = self._repository.get_parse(parse_version_id)
        if (
            material is None
            or material.project_id != project_id
            or parsed is None
            or parsed.source_material_id != material_id
        ):
            return None
        return MaterialScopeSourceFact(
            material_id=material.id,
            project_id=material.project_id,
            original_filename=material.original_filename,
            parse_version_id=parsed.id,
            parse_status=parsed.status,
            page_count=parsed.page_count,
            parse_content=parsed.content_json,
        )
