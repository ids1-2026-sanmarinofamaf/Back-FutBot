from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.behavior_preview import (
    BehaviorPreviewCreate,
    BehaviorPreviewCreateResponse,
)


VALID_DATA = {
    "code": "def play():\n    return wait()",
    "behavior_teammate_1": 1,
    "behavior_teammate_2": 2,
}


def test_create_preview_with_valid_data():
    preview = BehaviorPreviewCreate(**VALID_DATA)

    assert preview.model_dump() == VALID_DATA


@pytest.mark.parametrize(
    "missing_field",
    [
        "code",
        "behavior_teammate_1",
        "behavior_teammate_2",
    ],
)
def test_create_preview_rejects_missing_fields(missing_field):
    data = VALID_DATA.copy()
    del data[missing_field]

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


@pytest.mark.parametrize("invalid_code", ["", None, 123])
def test_create_preview_rejects_invalid_code(invalid_code):
    data = {**VALID_DATA, "code": invalid_code}

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


@pytest.mark.parametrize(
    "field",
    ["behavior_teammate_1", "behavior_teammate_2"],
)
@pytest.mark.parametrize(
    "invalid_value",
    [0, -1, None, "invalid", 1.5],
)
def test_create_preview_rejects_invalid_behavior_ids(
    field,
    invalid_value,
):
    data = {**VALID_DATA, field: invalid_value}

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


def test_create_preview_response():
    preview_id = uuid4()

    response = BehaviorPreviewCreateResponse(
        preview_id=preview_id,
    )

    assert response.model_dump(mode="json") == {
        "preview_id": str(preview_id),
    }


@pytest.mark.parametrize(
    "invalid_uuid",
    ["", "invalid-uuid", None, 123],
)
def test_create_preview_response_rejects_invalid_uuid(invalid_uuid):
    with pytest.raises(ValidationError):
        BehaviorPreviewCreateResponse(preview_id=invalid_uuid)