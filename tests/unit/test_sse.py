from __future__ import annotations

import pytest

from apps.api.errors import ApiError
from apps.api.reliability.sse import encode_heartbeat, parse_last_event_id


def test_sse_heartbeat_is_a_comment_frame() -> None:
    assert encode_heartbeat() == ": heartbeat\n\n"


def test_last_event_id_requires_nonnegative_sequence() -> None:
    assert parse_last_event_id(None) == 0
    assert parse_last_event_id("42") == 42
    with pytest.raises(ApiError, match="VALIDATION_FAILED"):
        parse_last_event_id("not-a-sequence")
    with pytest.raises(ApiError, match="VALIDATION_FAILED"):
        parse_last_event_id("-1")
