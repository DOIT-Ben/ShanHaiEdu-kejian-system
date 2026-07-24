from __future__ import annotations

from secrets import token_urlsafe

from sqlalchemy import select

from apps.api.database import build_session_factory
from apps.api.identity.models import Session as IdentitySession
from apps.api.main import create_app
from tests.integration.identity_session_support import (
    APP_ORIGIN,
    assert_secure_cookie,
    create_project,
    login,
    runtime_settings,
    seed_teacher,
    session_client,
)


async def test_create_session_sets_secure_cookie_and_rotates_id(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    settings = runtime_settings(
        migrated_database_url,
        access_code=access_code,
        csrf_secret=token_urlsafe(48),
    )
    app = create_app(settings=settings)
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    try:
        client, _ = session_client(app)
        async with client:
            client.cookies.set(
                "shanhai_session",
                "attacker-controlled-session",
                domain="teacher.shanhai.test",
            )
            first = await login(client, access_code)
            assert first.status_code == 201, first.text
            assert_secure_cookie(first)
            first_cookie = client.cookies.get("shanhai_session")
            first_csrf = first.json()["data"]["csrf_token"]
            assert first_cookie and first_cookie != "attacker-controlled-session"
            second = await login(client, access_code)
            assert second.status_code == 201, second.text
            second_cookie = client.cookies.get("shanhai_session")
            second_csrf = second.json()["data"]["csrf_token"]
            assert second_cookie and second_cookie != first_cookie
            assert second_csrf != first_csrf

            old_csrf = await create_project(
                client,
                csrf_token=first_csrf,
                idempotency_key="runtime-auth-rotated-csrf",
                title="旧 CSRF",
            )
            assert old_csrf.status_code == 403
            assert old_csrf.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"

        with factory() as session:
            persisted = session.scalars(
                select(IdentitySession).order_by(IdentitySession.created_at)
            ).all()
            assert len(persisted) == 2
            assert persisted[0].revoked_at is not None
            assert persisted[1].rotated_from_id == persisted[0].id
            assert persisted[0].token_hash != first_cookie
            assert persisted[1].token_hash != second_cookie

        stale_client, _ = session_client(app)
        stale_client.cookies.set("shanhai_session", first_cookie, domain="teacher.shanhai.test")
        async with stale_client:
            stale = await stale_client.get("/api/v2/auth/session")
        assert stale.status_code == 401
        assert stale.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        app.state.database_engine.dispose()


async def test_current_session_returns_public_principal_and_csrf(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    settings = runtime_settings(
        migrated_database_url,
        access_code=access_code,
        csrf_secret=token_urlsafe(48),
    )
    app = create_app(settings=settings)
    seed_teacher(app)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201, created.text
            token = client.cookies.get("shanhai_session")
            assert token
            created_data = created.json()["data"]
            current = await client.get("/api/v2/auth/session")
        assert current.status_code == 200, current.text
        assert current.json()["data"] == created_data
        assert current.headers["cache-control"] == "no-store"
        assert current.json()["data"]["principal"]["principal_id"] == str(
            settings.session_teacher_principal_id
        )

        app.state.database_engine.dispose()
        restarted = create_app(settings=settings)
        restarted_client, _ = session_client(restarted)
        restarted_client.cookies.set("shanhai_session", token, domain="teacher.shanhai.test")
        async with restarted_client:
            recovered = await restarted_client.get("/api/v2/auth/session")
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["data"] == created_data
    finally:
        engine = getattr(app.state, "database_engine", None)
        if engine is not None:
            engine.dispose()
        if "restarted" in locals():
            restarted.state.database_engine.dispose()


async def test_safe_session_reads_do_not_mutate_persisted_session(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    settings = runtime_settings(
        migrated_database_url,
        access_code=access_code,
        csrf_secret=token_urlsafe(48),
    )
    app = create_app(settings=settings)
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201, created.text
            with factory() as session:
                persisted = session.scalar(select(IdentitySession))
                assert persisted is not None
                initial_last_seen_at = persisted.last_seen_at
                assert persisted.revoked_at is None

            first = await client.get("/api/v2/auth/session")
            second = await client.get("/api/v2/auth/session")

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        with factory() as session:
            persisted = session.scalar(select(IdentitySession))
            assert persisted is not None
            assert persisted.last_seen_at == initial_last_seen_at
            assert persisted.revoked_at is None
    finally:
        app.state.database_engine.dispose()


async def test_logout_revokes_session(migrated_database_url: str) -> None:
    access_code = token_urlsafe(32)
    settings = runtime_settings(
        migrated_database_url,
        access_code=access_code,
        csrf_secret=token_urlsafe(48),
    )
    app = create_app(settings=settings)
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201, created.text
            csrf_token = created.json()["data"]["csrf_token"]
            session_token = client.cookies.get("shanhai_session")
            assert session_token
            project = await create_project(
                client,
                csrf_token=csrf_token,
                idempotency_key="runtime-auth-project-001",
                title="认识1到5",
            )
            assert project.status_code == 201, project.text
            logout = await client.delete(
                "/api/v2/auth/session",
                headers={"Origin": APP_ORIGIN, "X-CSRF-Token": csrf_token},
            )
            assert logout.status_code == 204, logout.text
            assert logout.headers["cache-control"] == "no-store"
            assert client.cookies.get("shanhai_session") is None

        with factory() as session:
            persisted = session.scalar(select(IdentitySession))
            assert persisted is not None and persisted.revoked_at is not None

        stale_client, _ = session_client(app)
        stale_client.cookies.set("shanhai_session", session_token, domain="teacher.shanhai.test")
        async with stale_client:
            current = await stale_client.get("/api/v2/auth/session")
            write = await create_project(
                stale_client,
                csrf_token=csrf_token,
                idempotency_key="runtime-auth-project-after-logout",
                title="已登出",
            )
        assert current.status_code == 401
        assert write.status_code == 401
    finally:
        app.state.database_engine.dispose()
