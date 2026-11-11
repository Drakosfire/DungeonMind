import pytest
from pydantic import ValidationError

from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1


@pytest.fixture
def region():
    return {
        "source_revision_id": "rev:pdf",
        "content_sha256": "a" * 64,
        "page": 1,
        "left": 0,
        "top": 0.2,
        "right": 1,
        "bottom": 0.8,
    }


def test_native_pdf_region_json_round_trip(region):
    locator = NativePdfRegionV1.model_validate(region)
    assert NativePdfRegionV1.model_validate_json(locator.model_dump_json()) == locator


@pytest.mark.parametrize(
    "invalid",
    [
        {"page": 0},
        {"page": "1"},
        {"right": 0},
        {"bottom": 0.1},
        {"left": float("nan")},
        {"top": -1},
        {"bottom": 1.01},
        {"content_sha256": "wrong"},
    ],
)
def test_native_pdf_region_rejects_invalid_locator(region, invalid):
    with pytest.raises(ValidationError):
        NativePdfRegionV1.model_validate(region | invalid)
