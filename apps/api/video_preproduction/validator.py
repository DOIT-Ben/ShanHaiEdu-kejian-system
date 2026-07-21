"""Pure validation and canonical hashing for video preproduction facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise
from typing import Any

from pydantic import BaseModel

from apps.api.video_preproduction.asset_planning import validate_assets_and_plan
from apps.api.video_preproduction.models import (
    ApprovalFact,
    DurationRecommendation,
    IntroSelectionSnapshot,
    MasterScript,
    ReviewableVideoPreproductionPackage,
    RoughStoryboard,
    TeacherConfirmation,
    ValidationReport,
)


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_fact_hash(value: object) -> str:
    if not isinstance(value, BaseModel):
        raise TypeError("canonical facts must be Pydantic models")
    return hashlib.sha256(_canonical_bytes(value.model_dump(mode="json"))).hexdigest()


def canonical_package_bytes(package: ReviewableVideoPreproductionPackage) -> bytes:
    payload = package.model_dump(mode="json", exclude={"canonical_hash", "validation_report"})
    return _canonical_bytes(payload)


def canonical_package_hash(package: ReviewableVideoPreproductionPackage) -> str:
    return hashlib.sha256(canonical_package_bytes(package)).hexdigest()


def validate_approval(
    approval: ApprovalFact,
    *,
    kind: str,
    key: str,
    value: object,
    confirmation: TeacherConfirmation | None = None,
    not_before: datetime | None = None,
) -> tuple[str, ...]:
    errors: list[str] = []
    if approval.subject_kind != kind or approval.subject_key != key:
        errors.append("approval subject does not match")
    if approval.subject_hash != canonical_fact_hash(value):
        errors.append("approval hash does not match")
    if kind == "master_script" and (
        confirmation is None
        or approval.confirmation_hash != canonical_fact_hash(confirmation)
        or approval.approved_at < confirmation.confirmed_at
    ):
        errors.append("master approval does not match teacher confirmation")
    if not_before is not None and approval.approved_at < not_before:
        errors.append("approval time precedes the reviewable subject")
    return tuple(errors)


def validate_master_script(
    snapshot: IntroSelectionSnapshot,
    master: MasterScript,
) -> tuple[str, ...]:
    errors: list[str] = []
    if (
        master.selected_intro_snapshot_id != snapshot.snapshot_id
        or master.selected_intro_snapshot_version != snapshot.version
        or master.selected_intro_option_key != snapshot.option_key
    ):
        errors.append("master script snapshot identity does not match")
    if master.creative_concept != snapshot.creative_concept:
        errors.append("master script creative concept does not match")
    if master.course_anchor != snapshot.course_anchor:
        errors.append("master script course anchor does not match")
    _validate_master_structure(snapshot, master, errors)
    return tuple(errors)


def validate_rough_storyboard(
    snapshot: IntroSelectionSnapshot,
    master: MasterScript,
    rough: RoughStoryboard,
    recommendation: DurationRecommendation,
) -> tuple[str, ...]:
    errors: list[str] = []
    if rough.source_master_script_key != master.master_script_key:
        errors.append("rough storyboard master script identity does not match")
    _validate_positions(
        tuple(beat.position for beat in rough.beats),
        "rough beat positions must be unique and contiguous",
        errors,
    )
    if len({beat.beat_key for beat in rough.beats}) != len(rough.beats):
        errors.append("rough beat keys must be unique")
    expected = [
        (scene.scene_key, position, event)
        for scene in master.scenes
        for position, event in enumerate(scene.visible_beats, start=1)
    ]
    actual = [(beat.scene_key, beat.scene_beat_position, beat.main_event) for beat in rough.beats]
    if actual != expected:
        errors.append("rough beats must completely map master visible beats")
    _validate_scene_beat_states(master, rough, errors)
    beat_duration = sum(beat.duration_seconds for beat in rough.beats)
    if rough.total_duration_seconds != beat_duration:
        errors.append("rough storyboard declared duration must equal beat durations")
    if beat_duration != recommendation.recommended_duration_seconds:
        errors.append("rough storyboard duration must equal the confirmed duration")
    _validate_no_preteach(
        snapshot,
        (
            text
            for beat in rough.beats
            for text in (beat.main_event, beat.start_state, beat.end_state)
        ),
        "rough storyboard",
        errors,
    )
    return tuple(errors)


def validate_package(package: ReviewableVideoPreproductionPackage) -> ValidationReport:
    errors = list(validate_master_script(package.source_snapshot, package.master_script))
    errors.extend(
        validate_rough_storyboard(
            package.source_snapshot,
            package.master_script,
            package.rough_storyboard,
            package.duration_recommendation,
        )
    )
    errors.extend(_approval_errors(package))
    _validate_confirmation(package, errors)
    _validate_handoff(package, errors)
    validate_assets_and_plan(package, errors)
    if canonical_package_hash(package) != package.canonical_hash:
        errors.append("canonical hash does not match package content")
    return ValidationReport(valid=not errors, errors=tuple(dict.fromkeys(errors)))


def _approval_errors(package: ReviewableVideoPreproductionPackage) -> tuple[str, ...]:
    errors = list(
        validate_approval(
            package.master_script_approval,
            kind="master_script",
            key=package.master_script.master_script_key,
            value=package.master_script,
            confirmation=package.teacher_confirmation,
        )
    )
    errors.extend(
        validate_approval(
            package.rough_storyboard_approval,
            kind="rough_storyboard",
            key=package.rough_storyboard.rough_storyboard_key,
            value=package.rough_storyboard,
            not_before=max(
                package.teacher_confirmation.confirmed_at,
                package.master_script_approval.approved_at,
                package.rough_storyboard.generated_at,
            ),
        )
    )
    return tuple(errors)


def _validate_confirmation(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    confirmation = package.teacher_confirmation
    recommendation = package.duration_recommendation
    if (
        confirmation.pricing_version != recommendation.pricing_version
        or confirmation.currency != recommendation.currency
        or confirmation.confirmed_duration_seconds != recommendation.recommended_duration_seconds
        or confirmation.confirmed_estimated_cost != recommendation.estimated_cost
    ):
        errors.append("teacher confirmation does not match the recommendation")


def _validate_master_structure(
    snapshot: IntroSelectionSnapshot,
    master: MasterScript,
    errors: list[str],
) -> None:
    _validate_positions(
        tuple(scene.position for scene in master.scenes),
        "master scene positions must be unique and contiguous",
        errors,
    )
    if len({scene.scene_key for scene in master.scenes}) != len(master.scenes):
        errors.append("master scene keys must be unique")
    _validate_continuity(
        tuple((scene.start_state, scene.end_state) for scene in master.scenes),
        "master scene states must be continuous",
        errors,
    )
    if master.scenes[-1].end_state != snapshot.handoff_moment or not master.ends_at_handoff:
        errors.append("master script must end at the selected handoff moment")
    if snapshot.course_anchor not in master.complete_story:
        errors.append("master story must contain the selected course anchor")
    scene_texts = tuple(
        text
        for scene in master.scenes
        for text in (
            scene.purpose,
            scene.location,
            scene.action,
            scene.visible_change,
            *scene.visible_beats,
            scene.narration,
            scene.dialogue,
            scene.sound_intent,
            scene.start_state,
            scene.end_state,
            *(item.purpose for item in scene.asset_requirements),
            *(item.visual_description for item in scene.asset_requirements),
        )
    )
    master_texts = (master.narrative_purpose, master.complete_story, *scene_texts)
    _validate_no_preteach(
        snapshot,
        master_texts,
        "master script",
        errors,
    )
    if any(snapshot.classroom_first_question in text for text in master_texts):
        errors.append("master script must reserve the classroom first question for after handoff")
    _validate_scene_asset_requirements(master, errors)


def _validate_scene_beat_states(
    master: MasterScript,
    rough: RoughStoryboard,
    errors: list[str],
) -> None:
    for scene in master.scenes:
        beats = tuple(beat for beat in rough.beats if beat.scene_key == scene.scene_key)
        if not beats:
            continue
        if beats[0].start_state != scene.start_state or beats[-1].end_state != scene.end_state:
            errors.append("rough beat states must cover the source scene")
        _validate_continuity(
            tuple((beat.start_state, beat.end_state) for beat in beats),
            "rough beat states must be continuous",
            errors,
        )


def _validate_handoff(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    if package.rough_storyboard.beats[-1].end_state != package.source_snapshot.handoff_moment:
        errors.append("rough storyboard must end at the selected handoff moment")


def _validate_positions(
    positions: tuple[int, ...],
    message: str,
    errors: list[str],
) -> None:
    if sorted(positions) != list(range(1, len(positions) + 1)):
        errors.append(message)


def _validate_continuity(
    states: tuple[tuple[str, str], ...],
    message: str,
    errors: list[str],
) -> None:
    if any(previous[1] != current[0] for previous, current in pairwise(states)):
        errors.append(message)


def _validate_no_preteach(
    snapshot: IntroSelectionSnapshot,
    texts: Iterable[str],
    scope: str,
    errors: list[str],
    *,
    additional: tuple[str, ...] = (),
) -> None:
    content = tuple(additional) + tuple(texts)
    for forbidden in snapshot.must_not_preteach:
        if any(forbidden in text for text in content):
            errors.append(f"{scope} must not preteach: {forbidden}")


def _validate_scene_asset_requirements(master: MasterScript, errors: list[str]) -> None:
    facts: dict[str, tuple[str, str, str, str]] = {}
    identity_to_key: dict[str, str] = {}
    for scene in master.scenes:
        keys = tuple(item.asset_key for item in scene.asset_requirements)
        if len(keys) != len(set(keys)):
            errors.append("scene asset requirement keys must be unique")
        for item in scene.asset_requirements:
            fact = (item.asset_type, item.identity_key, item.purpose, item.visual_description)
            previous = facts.setdefault(item.asset_key, fact)
            if previous != fact:
                errors.append("reused scene assets must keep identical semantics")
            previous_key = identity_to_key.setdefault(item.identity_key, item.asset_key)
            if previous_key != item.asset_key:
                errors.append("one asset identity must use exactly one asset key")
    types = {fact[0] for fact in facts.values()}
    if not {"character", "scene", "prop"} <= types:
        errors.append("master script must declare character, scene and prop asset classes")
    if not 5 <= len(identity_to_key) <= 8:
        errors.append("master script must declare between five and eight unique assets")
