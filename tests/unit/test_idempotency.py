from __future__ import annotations

from apps.api.reliability.idempotency import canonical_request_hash


def test_request_hash_is_stable_across_mapping_order() -> None:
    first = canonical_request_hash({"project_id": "p1", "payload": {"b": 2, "a": 1}})
    second = canonical_request_hash({"payload": {"a": 1, "b": 2}, "project_id": "p1"})

    assert first == second


def test_request_hash_changes_when_command_semantics_change() -> None:
    first = canonical_request_hash({"title": "Fractions", "mode": "assisted"})
    second = canonical_request_hash({"title": "Fractions", "mode": "automatic"})

    assert first != second
