"""Provider-neutral application ports for video preproduction."""

from __future__ import annotations

from typing import Protocol

from apps.api.video_preproduction.models import IntroSelectionSnapshot, MasterScript


class VideoPreproductionTextGenerator(Protocol):
    """Produces a structured master script from an immutable intro snapshot."""

    def generate_master_script(self, snapshot: IntroSelectionSnapshot) -> MasterScript: ...
