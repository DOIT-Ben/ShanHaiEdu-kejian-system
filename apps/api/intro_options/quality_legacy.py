"""Preserved validator identities for published Intro releases."""

from __future__ import annotations

from apps.api.artifact_quality.contracts import ValidatorRef

LEGACY_INTRO_OPTION_SCHEMA_REF = ValidatorRef(
    key="validator.intro.option_set_schema",
    semantic_version="1.0.0",
    implementation_digest="2049fe72e70c9c5280e011cfd131b47d7444128973c4e7163c2c51d08d18a379",
)
PREVIOUS_INTRO_OPTION_SCHEMA_REF = ValidatorRef(
    key="validator.intro.option_set_schema",
    semantic_version="1.1.0",
    implementation_digest="d60f89477c8db4c3f116fa7e524b8b8688e4f5403cc8cb137b0f1d56a170e6e4",
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
INTRO_UNIQUE_RECOMMENDATION_REF = ValidatorRef(
    key="validator.intro.unique_recommendation",
    semantic_version="1.0.0",
    implementation_digest="60469c797f3e35e6089fed2530bac6a3fc4a71dc17377e2325e7b3fd77468c12",
)
