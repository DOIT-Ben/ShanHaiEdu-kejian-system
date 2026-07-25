#!/usr/bin/env python3
"""Seed two projects and a controlled PDF for the R1 real upload browser gate."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from uuid import UUID

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import AuthenticatedIdentity
from apps.api.identity.models import Principal
from apps.api.identity.repository import IdentityRepository
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest

PRIMARY_PROJECT_TITLE = "教材范围与课时划分验收"
ISOLATION_PROJECT_TITLE = "教材范围隔离验收"
E2E_TEXTBOOK_NAME = "shanhai-r1-e2e-textbook.pdf"
PDF_PAGE_TEXTS = ("R1 evidence page 1", "R1 evidence page 2", "R1 evidence page 3")
ROOT = Path(__file__).resolve().parents[1]


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _write_controlled_textbook() -> Path:
    output = io.BytesIO()
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)  # pyright: ignore[reportPrivateUsage]
    for text in PDF_PAGE_TEXTS:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(  # pyright: ignore[reportPrivateUsage]
            content
        )
    writer.write(output)
    destination = Path(tempfile.gettempdir()) / E2E_TEXTBOOK_NAME
    destination.write_bytes(output.getvalue())
    return destination


def main() -> int:
    engine = build_engine(_required("SHANHAI_DATABASE_URL"))
    factory = build_session_factory(engine)
    try:
        with factory() as session, session.begin():
            principal = session.get(
                Principal,
                UUID(_required("SHANHAI_SESSION_TEACHER_PRINCIPAL_ID")),
            )
            if principal is None or principal.user_id is None:
                raise RuntimeError("the controlled E2E teacher principal is unavailable")
            actor = IdentityRepository(session).resolve_actor(
                AuthenticatedIdentity(
                    user_id=principal.user_id,
                    organization_id=principal.organization_id,
                )
            )
            ContentReleasePublisher(session).publish(
                load_builtin_courseware_release(ROOT),
                published_by=actor.principal_id,
            )
            for title in (PRIMARY_PROJECT_TITLE, ISOLATION_PROJECT_TITLE):
                ProjectRepository(session, actor).create(
                    CreateProjectRequest(
                        grade="一年级",
                        knowledge_point="1-5的认识",
                        textbook_edition="人教版",
                        title=title,
                    )
                )
        textbook = _write_controlled_textbook()
        print(f"r1 material scope projects and controlled PDF seeded: {textbook}", flush=True)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
