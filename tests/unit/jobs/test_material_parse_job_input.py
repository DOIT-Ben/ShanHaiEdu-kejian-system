from __future__ import annotations

import pytest

from apps.api.assets.material_parser import MaterialParserError
from workers.material_parse_job_input import exact_file_version_id


@pytest.mark.parametrize("creation_request", [1, "malformed", ["not-an-object"]])
def test_exact_file_version_id_rejects_non_object_creation_request(
    creation_request: object,
) -> None:
    class Job:
        creation_request_json = creation_request

    with pytest.raises(MaterialParserError) as raised:
        exact_file_version_id(Job())

    assert raised.value.code == "PDF_SOURCE_UNAVAILABLE"
