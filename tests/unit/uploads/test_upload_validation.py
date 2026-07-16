from __future__ import annotations

import pytest

from apps.api.errors import ApiError
from apps.api.uploads.confirmation_service import normalized_etag
from apps.api.uploads.session_service import normalized_media_type, safe_filename


@pytest.mark.parametrize("filename", ["../lesson.pdf", "folder/lesson.pdf", "folder\\lesson.pdf"])
def test_upload_filename_rejects_path_components(filename: str) -> None:
    with pytest.raises(ApiError, match="UPLOAD_REJECTED"):
        safe_filename(filename)


def test_upload_metadata_normalization_is_stable() -> None:
    assert safe_filename("lesson.pdf") == "lesson.pdf"
    assert normalized_media_type("Application/PDF; charset=binary") == "application/pdf"
    assert normalized_etag('"etag-value"') == "etag-value"
