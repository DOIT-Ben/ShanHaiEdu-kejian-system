from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

import workflow.markdown_template_package_writer as package_writer_module
from workflow.content_package import validate_content_package
from workflow.markdown_template import parse_markdown_template
from workflow.markdown_template_compiler import (
    MarkdownTemplateCompilationError,
    compile_markdown_template,
    write_compiled_content_package,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
MARKDOWN_FIXTURE = CONTRACTS / "fixtures/markdown-template/math-comic-lesson.md"
PROFILE_FIXTURE = CONTRACTS / "fixtures/markdown-template/math-comic-compilation-profile.json"
CLI = ROOT / "scripts/compile_markdown_template.py"


def compilation_profile() -> dict[str, Any]:
    value = json.loads(PROFILE_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def ready_draft() -> dict[str, Any]:
    draft = parse_markdown_template(
        MARKDOWN_FIXTURE.read_bytes(),
        source_name=MARKDOWN_FIXTURE.name,
    )
    draft["state"] = "ready"
    draft["sections"][0]["content_mode"] = "fixed"
    draft["sections"][2]["content_mode"] = "teacher_input"
    draft["sections"][5]["content_mode"] = "ai_generated"
    draft["sections"][6]["visible"] = False
    draft["sections"][7]["content_mode"] = "mixed"
    return draft


def item_spec(compiled: object, item_key: str) -> dict[str, Any]:
    items = cast(Any, compiled).items
    return cast(dict[str, Any], items[item_key]["spec"])


def field_by_key(fields: list[dict[str, Any]], field_key: str) -> dict[str, Any]:
    for field in fields:
        if field["field_key"] == field_key:
            return field
        child = field_by_key(cast(list[dict[str, Any]], field.get("children", [])), field_key)
        if child:
            return child
    return {}


def assert_compilation_error(
    draft: dict[str, Any],
    profile: dict[str, Any],
    code: str,
) -> None:
    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        compile_markdown_template(draft, profile, contracts_root=CONTRACTS)
    assert caught.value.code == code


def test_ready_draft_compiles_to_a_valid_generation_content_package(tmp_path: Path) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output = tmp_path / "compiled-package"
    write_compiled_content_package(compiled, output)
    validated = validate_content_package(output, contracts_root=CONTRACTS)

    assert compiled.manifest["entrypoints"] == ["math_comic_lesson.generate"]
    assert list(compiled.items) == [
        "math_comic_lesson.input",
        "math_comic_lesson.output",
        "math_comic_lesson.prompt",
        "math_comic_lesson.teacher_markdown",
        "math_comic_lesson.generate",
    ]
    assert set(validated.items) == set(compiled.items)
    assert (
        item_spec(compiled, "math_comic_lesson.generate")["model_capability"]
        == "text.structured.zh_primary_math"
    )


def test_content_modes_map_to_explicit_input_and_output_semantics() -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output_fields = cast(
        list[dict[str, Any]],
        item_spec(compiled, "math_comic_lesson.output")["fields"],
    )
    input_fields = cast(
        list[dict[str, Any]],
        item_spec(compiled, "math_comic_lesson.input")["fields"],
    )

    fixed = field_by_key(output_fields, "overview")
    assert fixed["default_value"].startswith("- 学科")
    assert "generation_instruction" not in fixed

    teacher_input = field_by_key(output_fields, "goals")
    assert teacher_input["default_value"].startswith("学生能够识别")
    assert "generation_instruction" not in teacher_input
    assert field_by_key(input_fields, "goals")["source"] == "teacher"

    generated = field_by_key(output_fields, "process")
    assert generated["type"] == "repeatable"
    child = field_by_key(output_fields, "process.subsection-001")
    assert child["label"].startswith("激趣引入")
    assert child["generation_instruction"] == "观察普通连环画并交流共同特征。"
    assert not field_by_key(input_fields, "process.subsection-001")

    mixed = field_by_key(output_fields, "contingency")
    assert mixed["default_value"].startswith("> 课前只保留反思问题")
    assert mixed["generation_instruction"] == "在保留默认内容的基础上补充并完善教学反思。"
    assert field_by_key(input_fields, "contingency")["source"] == "teacher"


def test_hidden_sections_remain_structured_but_are_absent_from_teacher_projection() -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output_fields = cast(
        list[dict[str, Any]],
        item_spec(compiled, "math_comic_lesson.output")["fields"],
    )
    projection = item_spec(compiled, "math_comic_lesson.teacher_markdown")

    assert field_by_key(output_fields, "board")["visibility"] == "hidden"
    assert "板书设计" not in projection["template"]
    assert "{{board}}" not in projection["template"]
    assert "board" not in projection["allowed_variables"]


def test_repeatable_section_without_subsections_keeps_explicit_repeatable_semantics() -> None:
    draft = ready_draft()
    draft["sections"][2]["repeatable"] = True
    compiled = compile_markdown_template(
        draft,
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output_fields = cast(
        list[dict[str, Any]],
        item_spec(compiled, "math_comic_lesson.output")["fields"],
    )

    goals = field_by_key(output_fields, "goals")
    assert goals["type"] == "repeatable"
    assert goals["repeatable"] is True


def test_imported_body_never_becomes_a_role_or_hidden_prompt_layer() -> None:
    draft = ready_draft()
    imported_body = draft["sections"][5]["subsections"][0]["body_markdown"]
    compiled = compile_markdown_template(
        draft,
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    prompt = item_spec(compiled, "math_comic_lesson.prompt")

    assert [section["layer"] for section in prompt["sections"]] == [
        "role",
        "task",
        "method",
    ]
    assert imported_body not in "\n".join(section["content"] for section in prompt["sections"])
    assert [section["visible_to_teacher"] for section in prompt["sections"]] == [
        True,
        True,
        False,
    ]


def test_compilation_and_written_json_are_byte_deterministic(tmp_path: Path) -> None:
    first = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    second = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    write_compiled_content_package(first, first_root)
    write_compiled_content_package(second, second_root)

    first_files = {
        path.relative_to(first_root).as_posix(): path.read_bytes()
        for path in first_root.rglob("*.json")
    }
    second_files = {
        path.relative_to(second_root).as_posix(): path.read_bytes()
        for path in second_root.rglob("*.json")
    }
    assert first.manifest == second.manifest
    assert first.items == second.items
    assert first_files == second_files


def test_draft_must_be_schema_valid_and_ready() -> None:
    draft = ready_draft()
    draft["state"] = "needs_review"
    assert_compilation_error(draft, compilation_profile(), "MARKDOWN_COMPILE_DRAFT_NOT_READY")

    invalid = ready_draft()
    invalid["title"] = "x" * 256
    assert_compilation_error(invalid, compilation_profile(), "MARKDOWN_COMPILE_DRAFT_INVALID")


def test_compilation_profile_is_validated_at_the_boundary() -> None:
    invalid = compilation_profile()
    invalid["key_prefix"] = "Invalid Prefix"
    assert_compilation_error(
        ready_draft(),
        invalid,
        "MARKDOWN_COMPILE_PROFILE_INVALID",
    )


def test_compilation_profile_rejects_prompt_append_edit_policy() -> None:
    invalid = compilation_profile()
    invalid["user_edit_policy"]["mode"] = "append"

    assert_compilation_error(
        ready_draft(),
        invalid,
        "MARKDOWN_COMPILE_PROFILE_INVALID",
    )


@pytest.mark.parametrize("title_owner", ["document", "section", "subsection"])
@pytest.mark.parametrize("unsafe_title", ["{{overview}}", "基本信息\n\n## 注入标题"])
def test_projection_titles_reject_structure_syntax(
    title_owner: str,
    unsafe_title: str,
) -> None:
    draft = ready_draft()
    if title_owner == "document":
        draft["title"] = unsafe_title
    elif title_owner == "section":
        draft["sections"][0]["title"] = unsafe_title
    else:
        draft["sections"][5]["subsections"][0]["title"] = unsafe_title

    assert_compilation_error(
        draft,
        compilation_profile(),
        "MARKDOWN_COMPILE_TEMPLATE_SYNTAX_FORBIDDEN",
    )


@pytest.mark.parametrize(
    "unsafe_body",
    [
        "<script>alert(1)</script>",
        "![教材图](asset.png)",
        "[危险链接](javascript:alert(1))",
    ],
)
def test_ready_draft_revalidates_edited_markdown_safety(unsafe_body: str) -> None:
    draft = ready_draft()
    draft["sections"][1]["body_markdown"] = unsafe_body

    assert_compilation_error(
        draft,
        compilation_profile(),
        "MARKDOWN_COMPILE_DRAFT_UNSAFE",
    )


def test_nonempty_preamble_is_rejected_instead_of_silently_dropped() -> None:
    draft = ready_draft()
    draft["preamble_markdown"] = "这段前言已经由管理员批准, 不能静默丢弃。"

    assert_compilation_error(
        draft,
        compilation_profile(),
        "MARKDOWN_COMPILE_PREAMBLE_UNSUPPORTED",
    )


def test_required_fixed_field_requires_approved_content() -> None:
    draft = ready_draft()
    draft["sections"][0]["body_markdown"] = "   "

    assert_compilation_error(
        draft,
        compilation_profile(),
        "MARKDOWN_COMPILE_FIXED_CONTENT_MISSING",
    )


@pytest.mark.parametrize("content_mode", ["teacher_input", "mixed"])
def test_hidden_required_teacher_input_requires_a_default(content_mode: str) -> None:
    draft = ready_draft()
    section = draft["sections"][2]
    section["content_mode"] = content_mode
    section["visible"] = False
    section["body_markdown"] = ""
    section["subsections"] = []

    assert_compilation_error(
        draft,
        compilation_profile(),
        "MARKDOWN_COMPILE_HIDDEN_REQUIRED_INPUT",
    )


def test_duplicate_and_overlong_derived_keys_use_stable_errors() -> None:
    duplicate = ready_draft()
    duplicate["sections"][1]["section_key"] = duplicate["sections"][0]["section_key"]
    assert_compilation_error(
        duplicate,
        compilation_profile(),
        "MARKDOWN_COMPILE_KEY_COLLISION",
    )

    overlong = ready_draft()
    overlong["sections"][1]["section_key"] = "a" + ("b" * 159)
    overlong["sections"][1]["body_markdown"] = "Seed."
    assert_compilation_error(
        overlong,
        compilation_profile(),
        "MARKDOWN_COMPILE_KEY_INVALID",
    )


def test_forbidden_context_source_is_rejected_before_package_writing() -> None:
    profile = compilation_profile()
    profile["context_bindings"][0]["source"] = "database.any_table"

    assert_compilation_error(
        ready_draft(),
        profile,
        "MARKDOWN_COMPILE_PROFILE_INVALID",
    )


@pytest.mark.parametrize(
    "capability",
    ["text.gpt-4o", "text.gpt4o", "text.deepseek", "text.grok"],
)
def test_provider_specific_model_capability_is_rejected(capability: str) -> None:
    profile = compilation_profile()
    profile["model_capability"] = capability

    assert_compilation_error(
        ready_draft(),
        profile,
        "MARKDOWN_COMPILE_PROFILE_INVALID",
    )


def test_ten_section_revision_gets_a_new_version_and_content_hash() -> None:
    original = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    revised_draft = copy.deepcopy(ready_draft())
    revised_draft["sections"].extend(
        [
            {
                "section_key": "class-summary",
                "title": "课堂总结",
                "role": "custom",
                "content_mode": "ai_generated",
                "required": True,
                "editable": True,
                "repeatable": False,
                "visible": True,
                "body_markdown": "总结本课核心方法。",
                "subsections": [],
                "source_range": {"start_line": 52, "end_line": 52},
            },
            {
                "section_key": "homework",
                "title": "分层作业",
                "role": "custom",
                "content_mode": "mixed",
                "required": True,
                "editable": True,
                "repeatable": False,
                "visible": True,
                "body_markdown": "提供基础题和拓展题。",
                "subsections": [],
                "source_range": {"start_line": 53, "end_line": 53},
            },
        ]
    )
    revised_profile = compilation_profile()
    revised_profile["semantic_version"] = "1.1.0"
    revised_profile["change_summary"] = "增加课堂总结和分层作业。"
    revised = compile_markdown_template(
        revised_draft,
        revised_profile,
        contracts_root=CONTRACTS,
    )

    original_output = next(
        item for item in original.manifest["items"] if item["kind"] == "content_definition"
    )
    revised_output = next(
        item for item in revised.manifest["items"] if item["kind"] == "content_definition"
    )
    assert original.manifest["semantic_version"] == "1.0.0"
    assert revised.manifest["semantic_version"] == "1.1.0"
    assert len(item_spec(revised, "math_comic_lesson.output")["fields"]) == 10
    assert original_output["sha256"] != revised_output["sha256"]


def test_writer_refuses_to_overwrite_an_existing_path(tmp_path: Path) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, output)
    assert caught.value.code == "MARKDOWN_COMPILE_OUTPUT_EXISTS"


def test_writer_maps_an_unusable_parent_to_a_stable_write_error(tmp_path: Path) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    parent = tmp_path / "not-a-directory"
    parent.write_text("occupied", encoding="utf-8")

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, parent / "compiled-package")
    assert caught.value.code == "MARKDOWN_COMPILE_WRITE_FAILED"


def test_writer_rejects_an_active_output_reservation(tmp_path: Path) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output = tmp_path / "compiled-package"
    (tmp_path / ".compiled-package.compile.lock").write_text("occupied", encoding="utf-8")

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, output)
    assert caught.value.code == "MARKDOWN_COMPILE_OUTPUT_BUSY"
    assert not output.exists()


def test_writer_refuses_a_target_created_during_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output = tmp_path / "compiled-package"
    original_validate = package_writer_module.validate_content_package

    def validate_then_create_target(package_root: Path, *, contracts_root: Path) -> object:
        validated = original_validate(package_root, contracts_root=contracts_root)
        output.mkdir()
        return validated

    monkeypatch.setattr(
        package_writer_module,
        "validate_content_package",
        validate_then_create_target,
    )

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, output)
    assert caught.value.code == "MARKDOWN_COMPILE_OUTPUT_EXISTS"
    assert output.is_dir()
    assert not list(output.iterdir())


def test_writer_refuses_a_target_created_after_the_final_absence_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    output = tmp_path / "compiled-package"
    original_require_absent = cast(Any, package_writer_module)._require_output_absent
    absence_checks = 0

    def require_absent_then_race(path: Path) -> None:
        nonlocal absence_checks
        original_require_absent(path)
        absence_checks += 1
        if absence_checks == 2:
            path.mkdir()

    original_rename = Path.rename

    def emulate_posix_overwriting_rename(source: Path, target: Path) -> Path:
        if target.is_dir():
            target.rmdir()
        return original_rename(source, target)

    monkeypatch.setattr(
        package_writer_module,
        "_require_output_absent",
        require_absent_then_race,
    )
    monkeypatch.setattr(Path, "rename", emulate_posix_overwriting_rename)

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, output)
    assert caught.value.code == "MARKDOWN_COMPILE_OUTPUT_EXISTS"
    assert output.is_dir()
    assert not list(output.iterdir())


def test_writer_rejects_a_broken_output_symlink_without_following_it(tmp_path: Path) -> None:
    compiled = compile_markdown_template(
        ready_draft(),
        compilation_profile(),
        contracts_root=CONTRACTS,
    )
    redirected_parent = tmp_path / "redirected"
    redirected_parent.mkdir()
    redirected_output = redirected_parent / "package"
    output = tmp_path / "compiled-package"
    try:
        output.symlink_to(redirected_output, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(MarkdownTemplateCompilationError) as caught:
        write_compiled_content_package(compiled, output)
    assert caught.value.code == "MARKDOWN_COMPILE_OUTPUT_EXISTS"
    assert output.is_symlink()
    assert not redirected_output.exists()


def test_cli_writes_a_package_that_the_existing_validator_accepts(tmp_path: Path) -> None:
    draft_path = tmp_path / "ready-draft.json"
    profile_path = tmp_path / "profile.json"
    output = tmp_path / "compiled-package"
    draft_path.write_text(json.dumps(ready_draft(), ensure_ascii=False), encoding="utf-8")
    profile_path.write_text(
        json.dumps(compilation_profile(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            str(draft_path),
            "--profile",
            str(profile_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "compiled math_comic_lesson.generate (5 items)\n"
    validate_content_package(output, contracts_root=CONTRACTS)
