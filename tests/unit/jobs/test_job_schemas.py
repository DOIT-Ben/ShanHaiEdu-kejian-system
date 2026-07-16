from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.ids import new_uuid7
from apps.api.jobs.schemas import AcceptedJobData


def test_accepted_job_rejects_terminal_status() -> None:
    with pytest.raises(ValidationError):
        AcceptedJobData(job_id=new_uuid7(), status="succeeded", events_url="/events")
