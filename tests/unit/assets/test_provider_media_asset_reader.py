from __future__ import annotations

from unittest.mock import ANY, Mock, call
from uuid import uuid4

from apps.api.assets.provider_media import SqlAlchemyProviderMediaAssetReader


def test_asset_reader_flushes_before_checking_provider_eligibility() -> None:
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    result = SqlAlchemyProviderMediaAssetReader(session).get_clean_image_version(
        organization_id=uuid4(),
        file_version_id=uuid4(),
    )

    assert result is None
    assert session.method_calls[:2] == [call.flush(), call.execute(ANY)]
