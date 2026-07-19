from __future__ import annotations

from copy import deepcopy

from scripts.check_api_surface import find_surface_errors


def contract(kind: str, operation_ids: tuple[str, ...]) -> dict:
    return {
        "openapi": "3.1.0",
        "x-shanhai-contract-kind": kind,
        "paths": {
            f"/{operation_id}": {
                "get": {
                    "operationId": operation_id,
                    **({"x-shanhai-availability": "planned"} if kind == "planned" else {}),
                }
            }
            for operation_id in operation_ids
        },
    }


def test_matching_runtime_and_current_surfaces_pass() -> None:
    runtime = contract("runtime", ("getProject",))
    current = deepcopy(runtime)
    planned = contract("planned", ("updateProject",))

    assert find_surface_errors(runtime, current, planned) == []


def test_static_only_and_runtime_only_operations_fail() -> None:
    runtime = contract("runtime", ("getProject", "runtimeOnly"))
    current = contract("runtime", ("getProject", "staticOnly"))
    planned = contract("planned", ())

    errors = find_surface_errors(runtime, current, planned)

    assert "current contract operation is not registered at runtime: staticOnly" in errors
    assert "runtime operation is missing from current contract: runtimeOnly" in errors


def test_matching_operation_id_must_keep_runtime_path_and_method() -> None:
    runtime = contract("runtime", ("getProject",))
    current = deepcopy(runtime)
    current["paths"]["/wrong-project-path"] = current["paths"].pop("/getProject")
    planned = contract("planned", ())

    errors = find_surface_errors(runtime, current, planned)

    assert (
        "current contract path/method differs from runtime: getProject "
        "(GET /wrong-project-path != GET /getProject)"
    ) in errors


def test_planned_operations_must_be_disjoint_and_marked() -> None:
    runtime = contract("runtime", ("getProject",))
    current = deepcopy(runtime)
    planned = contract("planned", ("getProject", "updateProject"))
    del planned["paths"]["/updateProject"]["get"]["x-shanhai-availability"]

    errors = find_surface_errors(runtime, current, planned)

    assert "operation appears in current and planned contracts: getProject" in errors
    assert "planned operation lacks availability marker: updateProject" in errors


def test_planned_operation_cannot_reuse_current_path_and_method() -> None:
    runtime = contract("runtime", ("getProject",))
    current = deepcopy(runtime)
    planned = contract("planned", ("futureGetProject",))
    planned["paths"]["/getProject"] = planned["paths"].pop("/futureGetProject")

    errors = find_surface_errors(runtime, current, planned)

    assert (
        "path/method appears in current and planned contracts: "
        "GET /getProject (getProject, futureGetProject)"
    ) in errors

    planned_operation = planned["paths"]["/getProject"].pop("get")
    planned["paths"]["/getProject"]["patch"] = planned_operation
    errors = find_surface_errors(runtime, current, planned)
    assert not any("path/method appears" in error for error in errors)


def test_contract_kind_markers_are_required() -> None:
    runtime = contract("runtime", ("getProject",))
    current = deepcopy(runtime)
    planned = contract("planned", ())
    del current["x-shanhai-contract-kind"]
    del planned["x-shanhai-contract-kind"]

    errors = find_surface_errors(runtime, current, planned)

    assert "current contract kind must be runtime" in errors
    assert "planned contract kind must be planned" in errors
