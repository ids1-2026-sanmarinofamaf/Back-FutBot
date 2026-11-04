"""
Unit tests for the round robin fixture generation.
"""

from collections import Counter

import pytest

from app.services.fixture_service import generate_fixture


def all_matches(club_ids, seed=None):
    # flattens the fechas into a single list of matches
    return [match for fecha in generate_fixture(club_ids, seed) for match in fecha]


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_generates_n_times_n_minus_one_over_two_matches(n):
    fixture = all_matches(list(range(1, n + 1)), seed=42)

    assert len(fixture) == n * (n - 1) // 2


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_no_pair_of_clubs_is_repeated(n):
    fixture = all_matches(list(range(1, n + 1)), seed=42)

    # frozenset so that (a, b) and (b, a) count as the same pair
    pairs = [frozenset(match) for match in fixture]
    assert len(pairs) == len(set(pairs))


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_no_club_plays_against_itself(n):
    fixture = all_matches(list(range(1, n + 1)), seed=42)

    assert all(local != visitante for local, visitante in fixture)


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_each_club_plays_n_minus_one_matches(n):
    club_ids = list(range(1, n + 1))
    fixture = all_matches(club_ids, seed=42)

    appearances = Counter(club for match in fixture for club in match)
    assert appearances == {club_id: n - 1 for club_id in club_ids}


def test_only_uses_the_given_club_ids():
    club_ids = [10, 25, 7, 99]
    fixture = all_matches(club_ids, seed=42)

    clubs_in_fixture = {club for match in fixture for club in match}
    assert clubs_in_fixture == set(club_ids)


def test_same_seed_generates_identical_fixture():
    club_ids = [1, 2, 3, 4, 5, 6]

    assert generate_fixture(club_ids, seed=123) == generate_fixture(club_ids, seed=123)


def test_same_seed_ignores_the_order_of_the_club_ids():
    assert generate_fixture([1, 2, 3, 4, 5], seed=7) == generate_fixture([5, 3, 1, 4, 2], seed=7)


def test_different_seeds_can_generate_different_fixtures():
    club_ids = list(range(1, 9))

    fixtures = {tuple(all_matches(club_ids, seed=seed)) for seed in range(10)}
    assert len(fixtures) > 1


def test_draw_assigns_both_local_and_visitante_roles():
    # with 28 matches, the chance that every club pair keeps the sorted order is negligible
    club_ids = list(range(1, 9))
    fixture = all_matches(club_ids, seed=42)

    assert any(local > visitante for local, visitante in fixture)
    assert any(local < visitante for local, visitante in fixture)


def test_works_without_seed():
    club_ids = [1, 2, 3, 4]
    fixture = all_matches(club_ids)

    assert len(fixture) == 6


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_generates_n_minus_one_fechas_if_even_and_n_if_odd(n):
    fechas = generate_fixture(list(range(1, n + 1)), seed=42)

    expected = n - 1 if n % 2 == 0 else n
    assert len(fechas) == expected


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_no_club_plays_twice_in_the_same_fecha(n):
    fechas = generate_fixture(list(range(1, n + 1)), seed=42)

    for fecha in fechas:
        clubs = [club for match in fecha for club in match]
        assert len(clubs) == len(set(clubs))


@pytest.mark.parametrize("n", [3, 5, 7])
def test_with_odd_n_each_club_is_free_exactly_once(n):
    club_ids = list(range(1, n + 1))
    fechas = generate_fixture(club_ids, seed=42)

    free = Counter(
        club
        for fecha in fechas
        for club in set(club_ids) - {c for match in fecha for c in match}
    )
    assert free == {club_id: 1 for club_id in club_ids}
