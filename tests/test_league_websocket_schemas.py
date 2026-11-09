from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.league import LeagueDetail, MatchScore
from app.schemas.league_websocket import (
    LeagueRoundStartedEvent,
    LeagueRoundFinishedEvent,
    LeagueStateEvent,
)


@pytest.fixture
def finished_round_payload():
    return {
        "league_id": 10,
        "round": 1,
        "results": [
            {
                "match_id": 101,
                "state": "FINALIZADO",
                "score": {"local": 0, "visitante": 0},
            }
        ],
        "standings": [],
        "break_ends_at": None,
    }


@pytest.mark.parametrize(
    "local, visitante",
    [(-1, 0), (0, -1)],
)
def test_match_score_rejects_negative_goals(local, visitante):
    with pytest.raises(ValidationError):
        MatchScore(local=local, visitante=visitante)


@pytest.mark.parametrize(
    "payload",
    [
        {"league_id": 10, "round": 1},
        {"league_id": 10, "round": 1, "match_ids": []},
    ],
    ids=["missing_matches", "empty_matches"],
)
def test_round_started_requires_matches(payload):
    with pytest.raises(ValidationError):
        LeagueRoundStartedEvent.model_validate(payload)


@pytest.mark.parametrize("missing_field", ["results", "break_ends_at"])
def test_round_finished_requires_results_and_break(
    finished_round_payload,
    missing_field,
):
    del finished_round_payload[missing_field]

    with pytest.raises(ValidationError) as error:
        LeagueRoundFinishedEvent.model_validate(finished_round_payload)

    assert any(
        item["loc"] == (missing_field,) and item["type"] == "missing"
        for item in error.value.errors()
    )


@pytest.mark.parametrize(
    "break_ends_at",
    [None, datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)],
    ids=["last_round", "pending_break"],
)
def test_round_finished_serializes_score_and_break(
    finished_round_payload,
    break_ends_at,
):
    finished_round_payload["break_ends_at"] = break_ends_at

    event = LeagueRoundFinishedEvent.model_validate(finished_round_payload)
    payload = event.model_dump(mode="json")

    assert payload["type"] == "league_round_finished"
    assert payload["results"] == [
        {
            "match_id": 101,
            "state": "FINALIZADO",
            "score": {"local": 0, "visitante": 0},
            "winner_club_id": None,
        }
    ]

    if break_ends_at is None:
        assert payload["break_ends_at"] is None
    else:
        assert datetime.fromisoformat(payload["break_ends_at"]) == break_ends_at


def test_round_finished_rejects_break_without_timezone(finished_round_payload):
    finished_round_payload["break_ends_at"] = datetime(2026, 11, 4, 12, 0)

    with pytest.raises(ValidationError) as error:
        LeagueRoundFinishedEvent.model_validate(finished_round_payload)

    assert any(
        item["loc"] == ("break_ends_at",)
        and item["type"] == "timezone_aware"
        for item in error.value.errors()
    )


def test_league_state_nests_detail_inside_data():
    detail = LeagueDetail(
        league_id=10,
        name="Liga de prueba",
        state="INICIADA",
        privacy="PUBLICA",
        current_participants=4,
        capacity=4,
        fixture=[],
        standings=[],
        last_completed_round=1,
        active_round=2,
        active_match_ids=[103, 104],
    )

    event = LeagueStateEvent(data=detail)
    payload = event.model_dump(mode="json")

    assert set(payload) == {"type", "data"}
    assert payload["type"] == "league_state"
    assert payload["data"] == detail.model_dump(mode="json")
    assert payload["data"]["active_match_ids"] == [103, 104]
