"""Single registry for provider-neutral logical model capabilities."""

from __future__ import annotations

from enum import StrEnum


class ModelCapability(StrEnum):
    TEXT_SMOKE = "text.smoke"
    TEXT_STRUCTURED_AUDIO_PLAN = "text.structured.audio_plan"
    TEXT_STRUCTURED_CREATIVE_EDUCATION = "text.structured.creative_education"
    TEXT_STRUCTURED_CREATIVE_VIDEO = "text.structured.creative_video"
    TEXT_STRUCTURED_IMAGE_PROMPT = "text.structured.image_prompt"
    TEXT_STRUCTURED_PPT_CONTENT = "text.structured.ppt_content"
    TEXT_STRUCTURED_PPT_DESIGN = "text.structured.ppt_design"
    TEXT_STRUCTURED_PPT_PAGE_DESIGN = "text.structured.ppt_page_design"
    TEXT_STRUCTURED_ZH_PRIMARY_MATH = "text.structured.zh_primary_math"
    IMAGE_GENERATE_EDUCATION_16X9 = "image.generate.education_16x9"
    VIDEO_IMAGE_TO_VIDEO_6S_30S = "video.image_to_video.6s_30s"
    AUDIO_TTS_CHILD_FRIENDLY_ZH = "audio.tts.child_friendly_zh"
    VISION_EVALUATE_CLASSROOM_VIDEO = "vision.evaluate.classroom_video"


WORKFLOW_MODEL_CAPABILITIES = frozenset(
    capability.value for capability in ModelCapability if capability != ModelCapability.TEXT_SMOKE
)
