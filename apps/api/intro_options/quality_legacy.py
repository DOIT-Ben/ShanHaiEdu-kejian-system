"""Preserved validator identities for projects bound to Release 1.4."""

from __future__ import annotations

from apps.api.artifact_quality.contracts import ValidatorRef

LEGACY_INTRO_OPTION_SCHEMA_REF = ValidatorRef(
    key="validator.intro.option_set_schema",
    semantic_version="1.0.0",
    implementation_digest="2049fe72e70c9c5280e011cfd131b47d7444128973c4e7163c2c51d08d18a379",
)
LEGACY_INTRO_SINGLE_ANCHOR_REF = ValidatorRef(
    key="validator.intro.single_anchor",
    semantic_version="1.1.0",
    implementation_digest="f37001db813669d7148ac43d25045472c0c4b84427df414e303f4a99e5b40220",
)
PREVIOUS_INTRO_SINGLE_ANCHOR_REF = ValidatorRef(
    key="validator.intro.single_anchor",
    semantic_version="1.2.0",
    implementation_digest="c63f73f6b74e54bf0a69ca7770f13a76e56bb6f092cf523d2eb2d612eae5ca06",
)
