"""Mocked sample calls for the MovieGlu showtimes skill."""

import asyncio
from typing import Any

import pytest

from app.config import get_settings
from app.skills.movie_showtimes import (
    _GeoPoint,
    _minutes_delta,
    _MovieGluApiError,
    _MovieGluClient,
    _parse_time,
    search_movie_showtimes,
)


@pytest.fixture(autouse=True)
def movieglu_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOVIEGLU_CLIENT", "test-client")
    monkeypatch.setenv("MOVIEGLU_API_KEY", "test-key")
    monkeypatch.setenv("MOVIEGLU_AUTHORIZATION", "Basic test-auth")
    monkeypatch.setenv("MOVIEGLU_TERRITORY", "US")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_movie_at_theater_returns_normalized_booking_link(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self: Any, resource: str, params: dict[str, Any] | None = None, geolocation: Any = None) -> dict[str, Any]:
        if resource == "cinemaLiveSearch/":
            return {
                "cinemas": [
                    {
                        "cinema_id": 100,
                        "cinema_name": "AMC Highland Village 12",
                        "address": "4090 Barton Creek",
                        "city": "Highland Village",
                        "postcode": "75077",
                        "distance": 2.1,
                    }
                ]
            }
        if resource == "filmLiveSearch/":
            return {"films": [{"film_id": 200, "film_name": "Spider-Man: Into the Spider-Verse", "timescount": 40}]}
        if resource == "cinemaShowTimes/":
            return {
                "cinema": {"cinema_id": 100, "cinema_name": "AMC Highland Village 12"},
                "films": [
                    {
                        "film_id": 200,
                        "film_name": "Spider-Man: Into the Spider-Verse",
                        "showings": {
                            "Standard": {
                                "film_id": 200,
                                "film_name": "Spider-Man: Into the Spider-Verse",
                                "times": [{"start_time": "19:05", "end_time": "21:05"}],
                            }
                        },
                    }
                ],
            }
        if resource == "filmDetails/":
            return {"film_id": params["film_id"], "genres": [{"genre_name": "Animation"}, {"genre_name": "Action"}]}
        if resource == "purchaseConfirmation/":
            return {"url": "https://tickets.example/spider-verse"}
        raise AssertionError(resource)

    monkeypatch.setattr("app.skills.movie_showtimes._MovieGluClient.get", fake_get)
    result = asyncio.run(
        search_movie_showtimes(
            theater_name="AMC Highland Village",
            movie_title="Into the Spider-Verse",
            target_time="7pm",
            date="2026-05-06",
        )
    )

    assert result["errors"] == []
    assert result["metadata"]["result_count"] == 1
    assert result["results"][0] == {
        "movie_title": "Spider-Man: Into the Spider-Verse",
        "movie_id": "200",
        "genre": "Animation, Action",
        "theater_name": "AMC Highland Village 12",
        "theater_id": "100",
        "theater_address": "4090 Barton Creek, Highland Village, 75077",
        "start_time": "2026-05-06T19:05:00",
        "display_time": "7:05 PM",
        "distance_miles": 2.1,
        "format": "Standard",
        "booking_url": "https://tickets.example/spider-verse",
        "confidence": "high",
    }


def test_genre_location_time_discovery_filters_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_geocode(location: str | None, warnings: list[dict[str, Any]]) -> _GeoPoint:
        return _GeoPoint(lat=33.0146, lng=-97.0969, label=location)

    async def fake_get(self: Any, resource: str, params: dict[str, Any] | None = None, geolocation: Any = None) -> dict[str, Any]:
        if resource == "cinemasNearby/":
            return {
                "cinemas": [
                    {
                        "cinema_id": 101,
                        "cinema_name": "Moviehouse Flower Mound",
                        "address": "951 Long Prairie Rd",
                        "city": "Flower Mound",
                        "postcode": "75022",
                        "distance": 4.2,
                    },
                    {
                        "cinema_id": 102,
                        "cinema_name": "Far Away Theater",
                        "distance": 18.0,
                    },
                ]
            }
        if resource == "cinemaShowTimes/":
            return {
                "cinema": {"cinema_id": 101, "cinema_name": "Moviehouse Flower Mound"},
                "films": [
                    {
                        "film_id": 301,
                        "film_name": "Laugh Track",
                        "showings": {"Standard": {"times": [{"start_time": "20:10"}], "film_id": 301, "film_name": "Laugh Track"}},
                    },
                    {
                        "film_id": 302,
                        "film_name": "Sad Planet",
                        "showings": {"Standard": {"times": [{"start_time": "20:00"}], "film_id": 302, "film_name": "Sad Planet"}},
                    },
                ],
            }
        if resource == "filmDetails/":
            genres = {"301": "Comedy", "302": "Drama"}
            return {"film_id": params["film_id"], "genres": [{"genre_name": genres[str(params["film_id"])]}]}
        raise AssertionError(resource)

    monkeypatch.setattr("app.skills.movie_showtimes._geocode_location", fake_geocode)
    monkeypatch.setattr("app.skills.movie_showtimes._MovieGluClient.get", fake_get)

    result = asyncio.run(
        search_movie_showtimes(
            location="Flower Mound, TX",
            genre="comedies",
            target_time="8pm",
            date="2026-05-06",
            radius_miles=10,
            include_booking_links=False,
        )
    )

    assert result["errors"] == []
    assert result["metadata"]["result_count"] == 1
    assert result["results"][0]["movie_title"] == "Laugh Track"
    assert result["results"][0]["genre"] == "Comedy"
    assert result["results"][0]["distance_miles"] == 4.2


def test_movie_without_location_returns_needs_location() -> None:
    result = asyncio.run(search_movie_showtimes(movie_title="Dune", date="2026-05-06"))

    assert result["metadata"]["result_count"] == 0
    assert result["errors"][0]["code"] == "needs_location"
    assert result["results"] == []


def test_unresolved_movie_returns_closest_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_geocode(location: str | None, warnings: list[dict[str, Any]]) -> _GeoPoint:
        return _GeoPoint(lat=33.0146, lng=-97.0969, label=location)

    async def fake_get(self: Any, resource: str, params: dict[str, Any] | None = None, geolocation: Any = None) -> dict[str, Any]:
        if resource == "filmLiveSearch/":
            return {"films": [{"film_id": 99, "film_name": "Completely Different", "timescount": 5}]}
        raise AssertionError(resource)

    monkeypatch.setattr("app.skills.movie_showtimes._geocode_location", fake_geocode)
    monkeypatch.setattr("app.skills.movie_showtimes._MovieGluClient.get", fake_get)

    result = asyncio.run(search_movie_showtimes(location="Flower Mound, TX", movie_title="Dune", date="2026-05-06"))

    assert result["errors"][0]["code"] == "movie_not_resolved"
    assert result["errors"][0]["matches"][0]["movie_title"] == "Completely Different"


def test_genre_metadata_failure_is_structured_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_geocode(location: str | None, warnings: list[dict[str, Any]]) -> _GeoPoint:
        return _GeoPoint(lat=33.0146, lng=-97.0969, label=location)

    async def fake_get(self: Any, resource: str, params: dict[str, Any] | None = None, geolocation: Any = None) -> dict[str, Any]:
        if resource == "cinemasNearby/":
            return {"cinemas": [{"cinema_id": 101, "cinema_name": "Moviehouse Flower Mound", "distance": 4.2}]}
        if resource == "cinemaShowTimes/":
            return {
                "cinema": {"cinema_id": 101, "cinema_name": "Moviehouse Flower Mound"},
                "films": [
                    {
                        "film_id": 301,
                        "film_name": "Laugh Track",
                        "showings": {
                            "Standard": {
                                "film_id": 301,
                                "film_name": "Laugh Track",
                                "times": [{"start_time": "20:10"}],
                            }
                        },
                    }
                ],
            }
        if resource == "filmDetails/":
            raise _MovieGluApiError("details unavailable")
        raise AssertionError(resource)

    monkeypatch.setattr("app.skills.movie_showtimes._geocode_location", fake_geocode)
    monkeypatch.setattr("app.skills.movie_showtimes._MovieGluClient.get", fake_get)

    result = asyncio.run(
        search_movie_showtimes(
            location="Flower Mound, TX",
            genre="comedy",
            target_time="8pm",
            date="2026-05-06",
            include_booking_links=False,
        )
    )

    assert result["errors"][0]["code"] == "no_results"
    assert {reason["code"] for reason in result["errors"][0]["reasons"]} >= {"genre_metadata_unavailable"}
    assert {warning["code"] for warning in result["warnings"]} >= {
        "film_details_unavailable",
        "genre_metadata_unavailable",
    }


def test_target_time_delta_wraps_around_midnight() -> None:
    assert _minutes_delta(_parse_time("23:50"), _parse_time("12:30am")) == 40


def test_movieglu_invalid_json_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadJsonResponse:
        status_code = 200
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            raise ValueError("not json")

    class FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, *args: Any, **kwargs: Any) -> BadJsonResponse:
            return BadJsonResponse()

    monkeypatch.setattr("app.skills.movie_showtimes.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(_MovieGluApiError, match="invalid JSON"):
        asyncio.run(_MovieGluClient().get("filmLiveSearch/", params={"query": "Dune"}))
