"""Movie showtime data-access skill backed by MovieGlu.

Public skill:
    search_movie_showtimes(...)

The skill returns structured JSON-compatible dictionaries only. It does not
generate conversational text, recommendations, reply suggestions, or follow-up
questions. The calling LLM owns all conversation behavior.

Setup:
    Add MovieGlu credentials to the environment. Required for live API calls:
    MOVIEGLU_CLIENT, MOVIEGLU_API_KEY, MOVIEGLU_AUTHORIZATION,
    MOVIEGLU_TERRITORY. Optional: MOVIEGLU_API_URL, MOVIEGLU_API_VERSION.

Example:
    result = await search_movie_showtimes(
        location="Flower Mound, TX",
        genre="horror",
        target_time="6pm",
    )
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings

logger = logging.getLogger(__name__)

MOVIEGLU_SOURCE = "MovieGlu"
DEFAULT_RADIUS_MILES = 10.0
TIME_WINDOW_MINUTES = 90
MAX_MOVIEGLU_PAGE_SIZE = 25


class TimeWindow(BaseModel):
    from_: str | None = Field(default=None, serialization_alias="from")
    to: str | None = None


class QueryInterpretation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    location: str | None = None
    theater_name: str | None = None
    movie_title: str | None = None
    genre: str | None = None
    date: str
    time_window: TimeWindow


class ShowtimeResult(BaseModel):
    movie_title: str | None = None
    movie_id: str | None = None
    genre: str | None = None
    theater_name: str | None = None
    theater_id: str | None = None
    theater_address: str | None = None
    start_time: str | None = None
    display_time: str | None = None
    distance_miles: float | None = None
    format: str = "Unknown"
    booking_url: str | None = None
    confidence: str = "medium"


class SkillMetadata(BaseModel):
    result_count: int
    source: str = MOVIEGLU_SOURCE
    generated_at: str


class SkillResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query_interpretation: QueryInterpretation
    results: list[ShowtimeResult]
    metadata: SkillMetadata
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


@dataclass(slots=True)
class _ResolvedEntity:
    entity_id: str | None
    name: str | None
    confidence: str
    score: float
    raw: dict[str, Any] | None = None
    matches: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class _GeoPoint:
    lat: float
    lng: float
    label: str | None = None


class _MovieGluConfigurationError(Exception):
    pass


class _MovieGluApiError(Exception):
    pass


class _MovieGluClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.movieglu_api_url.rstrip("/")
        self.client_name = settings.movieglu_client
        self.api_key = settings.movieglu_api_key
        self.authorization = settings.movieglu_authorization
        self.territory = settings.movieglu_territory
        self.api_version = settings.movieglu_api_version
        self.timeout = settings.movieglu_timeout_seconds

        missing = [
            name
            for name, value in {
                "MOVIEGLU_CLIENT": self.client_name,
                "MOVIEGLU_API_KEY": self.api_key,
                "MOVIEGLU_AUTHORIZATION": self.authorization,
                "MOVIEGLU_TERRITORY": self.territory,
                "MOVIEGLU_API_VERSION": self.api_version,
            }.items()
            if not str(value or "").strip()
        ]
        if missing:
            raise _MovieGluConfigurationError(
                "Missing MovieGlu configuration: " + ", ".join(missing)
            )

    def _headers(self, geolocation: _GeoPoint | None = None) -> dict[str, str]:
        headers = {
            "client": self.client_name,
            "x-api-key": self.api_key,
            "authorization": self.authorization,
            "territory": self.territory,
            "api-version": self.api_version,
            "device-datetime": datetime.now().isoformat(timespec="milliseconds"),
        }
        if geolocation:
            headers["geolocation"] = f"{geolocation.lat:.6f};{geolocation.lng:.6f}"
        return headers

    async def get(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        geolocation: _GeoPoint | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{resource.lstrip('/')}"
        attempts = 2
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        headers=self._headers(geolocation),
                        params=params or {},
                    )
                if response.status_code == 204:
                    return {
                        "status": {
                            "state": "Warning",
                            "message": response.headers.get("MG-message") or "No content available",
                        }
                    }
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise _MovieGluApiError("MovieGlu returned invalid JSON") from exc
                return data if isinstance(data, dict) else {}
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
                if isinstance(exc, httpx.HTTPStatusError):
                    retryable = exc.response.status_code >= 500
                if not retryable or attempt == attempts - 1:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))

        raise _MovieGluApiError(str(last_error or "MovieGlu request failed"))


async def search_movie_showtimes(
    location: str | None = None,
    theater_name: str | None = None,
    movie_title: str | None = None,
    genre: str | None = None,
    date: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    target_time: str | None = None,
    radius_miles: float | None = DEFAULT_RADIUS_MILES,
    max_results: int = 5,
    include_booking_links: bool = True,
) -> dict[str, Any]:
    """Search normalized movie showtimes with one high-level call.

    Returns JSON-compatible structured data only. This function is intentionally
    a data-access and normalization layer for an LLM/agent; it never produces
    natural-language responses or conversation guidance.
    """
    generated_at = datetime.now().isoformat(timespec="seconds")
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    max_results = max(1, min(max_results, 25))
    radius_miles = DEFAULT_RADIUS_MILES if radius_miles is None else radius_miles
    resolved_date = _resolve_date(date, warnings)
    start_window, end_window = _resolve_time_window(time_from, time_to, target_time, warnings)

    response_shell = _response_shell(
        location=location,
        theater_name=theater_name,
        movie_title=movie_title,
        genre=genre,
        resolved_date=resolved_date,
        start_window=start_window,
        end_window=end_window,
        generated_at=generated_at,
        warnings=warnings,
    )
    warnings = response_shell.warnings

    needs_location = not location and not theater_name
    if needs_location:
        response_shell.errors.append(
            {
                "code": "needs_location",
                "message": "Location is required unless a theater_name is provided.",
                "required_fields": ["location"],
            }
        )
        return _dump_response(response_shell)

    try:
        client = _MovieGluClient()
    except _MovieGluConfigurationError as exc:
        response_shell.errors.append({"code": "configuration_error", "message": str(exc)})
        return _dump_response(response_shell)

    try:
        geo = await _geocode_location(location, warnings) if location else None
        if location and not geo:
            response_shell.errors.append(
                {
                    "code": "geocode_failed",
                    "message": "Location could not be resolved to latitude/longitude.",
                    "location": location,
                }
            )
            return _dump_response(response_shell)

        cinema = await _resolve_cinema(client, theater_name, geo, warnings) if theater_name else None
        if theater_name and (not cinema or not cinema.entity_id):
            response_shell.errors.append(
                {
                    "code": "cinema_not_resolved",
                    "message": "Theater could not be resolved confidently.",
                    "matches": cinema.matches if cinema else [],
                }
            )
            return _dump_response(response_shell)

        movie = await _resolve_movie(client, movie_title, warnings) if movie_title else None
        if movie_title and (not movie or not movie.entity_id):
            response_shell.errors.append(
                {
                    "code": "movie_not_resolved",
                    "message": "Movie could not be resolved confidently.",
                    "matches": movie.matches if movie else [],
                }
            )
            return _dump_response(response_shell)

        raw_payloads: list[dict[str, Any]] = []
        cinemas_by_id: dict[str, dict[str, Any]] = {}

        if cinema and cinema.entity_id:
            raw = await _get_cinema_showtimes(client, cinema.entity_id, resolved_date, movie.entity_id if movie else None)
            raw_payloads.append(raw)
            if cinema.raw:
                cinemas_by_id[str(cinema.entity_id)] = cinema.raw
        elif movie and movie.entity_id and geo:
            raw_payloads.append(
                await _get_movie_showtimes(client, movie.entity_id, geo, resolved_date, max_results=max_results)
            )
        elif geo:
            nearby = await _get_nearby_cinemas(client, geo, radius_miles, max_results=max_results)
            cinemas_by_id.update({str(c.get("cinema_id")): c for c in nearby if c.get("cinema_id") is not None})
            showtime_tasks = [
                _get_cinema_showtimes(client, str(c["cinema_id"]), resolved_date, None)
                for c in nearby[: max(1, min(len(nearby), max_results * 2))]
                if c.get("cinema_id") is not None
            ]
            raw_payloads.extend(await asyncio.gather(*showtime_tasks))

        normalized = _normalize_showtime_response(raw_payloads, resolved_date, cinemas_by_id)
        had_source_showtimes = bool(normalized)
        if location:
            normalized = _filter_by_distance(normalized, radius_miles)
        normalized = _filter_by_time(normalized, start_window, end_window)

        details_by_id = await _get_film_details_for_results(client, normalized, warnings)
        _attach_genres(normalized, details_by_id)
        genre_metadata_unavailable = bool(genre and normalized and not any(s.get("genres") for s in normalized))
        if genre_metadata_unavailable:
            warnings.append(
                {
                    "code": "genre_metadata_unavailable",
                    "message": "Genre filtering could not be verified because film genre metadata was unavailable.",
                }
            )
        normalized = _filter_by_genre(normalized, genre)

        ranked = _rank_results(
            normalized,
            target_time=_parse_time(target_time) if target_time else None,
            movie_title=movie_title,
            theater_name=theater_name,
            genre=genre,
        )
        limited = ranked[:max_results]

        if include_booking_links and limited:
            await _attach_booking_links(client, limited, warnings)

        response_shell.results = [_to_result(item) for item in limited]
        if not response_shell.results:
            response_shell.errors.append(
                {
                    "code": "no_results",
                    "message": "No matching showtimes found for the structured query.",
                    "reasons": _no_result_reasons(
                        had_raw_results=had_source_showtimes,
                        genre=genre,
                        time_from=start_window,
                        time_to=end_window,
                        radius_miles=radius_miles,
                        genre_metadata_unavailable=genre_metadata_unavailable,
                    ),
                }
            )
        response_shell.metadata.result_count = len(response_shell.results)
        return _dump_response(response_shell)
    except _MovieGluApiError as exc:
        logger.warning("MovieGlu skill API error: %s", exc)
        response_shell.errors.append({"code": "api_error", "message": str(exc)})
        return _dump_response(response_shell)


async def _geocode_location(location: str | None, warnings: list[dict[str, Any]]) -> _GeoPoint | None:
    if not location:
        return None
    parsed = _parse_lat_lng(location)
    if parsed:
        return parsed

    data: Any = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": location, "format": "json", "limit": 1},
                    headers={"User-Agent": "movieglue-hackathon-showtime-skill/1.0"},
                )
            response.raise_for_status()
            data = response.json()
            break
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == 1:
                warnings.append({"code": "geocoder_error", "message": str(exc)})
                return None
            await asyncio.sleep(0.2 * (attempt + 1))
        except (httpx.HTTPStatusError, ValueError) as exc:
            warnings.append({"code": "geocoder_error", "message": str(exc)})
            return None

    if not data:
        return None
    first = data[0]
    try:
        return _GeoPoint(lat=float(first["lat"]), lng=float(first["lon"]), label=first.get("display_name"))
    except (KeyError, TypeError, ValueError):
        return None


async def _resolve_cinema(
    client: _MovieGluClient,
    theater_name: str | None,
    location: _GeoPoint | None,
    warnings: list[dict[str, Any]],
) -> _ResolvedEntity:
    if not theater_name:
        return _ResolvedEntity(None, None, "low", 0.0)
    raw = await client.get(
        "cinemaLiveSearch/",
        params={"query": theater_name, "n": 5},
        geolocation=location,
    )
    cinemas = raw.get("cinemas") or []
    if not cinemas:
        return _ResolvedEntity(None, None, "low", 0.0, matches=[])
    ranked = sorted(
        cinemas,
        key=lambda c: (
            -_match_score(theater_name, str(c.get("cinema_name") or "")),
            _safe_float(c.get("distance"), default=9999),
        ),
    )
    best = ranked[0]
    score = _match_score(theater_name, str(best.get("cinema_name") or ""))
    confidence = _confidence(score)
    matches = [_cinema_match(c, theater_name) for c in ranked[:5]]
    if confidence == "low":
        warnings.append({"code": "low_confidence_cinema", "matches": matches})
        return _ResolvedEntity(None, None, "low", score, matches=matches)
    return _ResolvedEntity(
        entity_id=str(best.get("cinema_id")),
        name=best.get("cinema_name"),
        confidence=confidence,
        score=score,
        raw=best,
        matches=matches,
    )


async def _resolve_movie(
    client: _MovieGluClient,
    movie_title: str | None,
    warnings: list[dict[str, Any]],
) -> _ResolvedEntity:
    if not movie_title:
        return _ResolvedEntity(None, None, "low", 0.0)
    raw = await client.get("filmLiveSearch/", params={"query": movie_title, "n": 5})
    films = raw.get("films") or []
    if not films:
        return _ResolvedEntity(None, None, "low", 0.0, matches=[])
    ranked = sorted(
        films,
        key=lambda f: (
            -_match_score(movie_title, str(f.get("film_name") or "")),
            -int(f.get("timescount") or 0),
        ),
    )
    best = ranked[0]
    score = _match_score(movie_title, str(best.get("film_name") or ""))
    confidence = _confidence(score)
    matches = [_film_match(f, movie_title) for f in ranked[:5]]
    if confidence == "low":
        warnings.append({"code": "low_confidence_movie", "matches": matches})
        return _ResolvedEntity(None, None, "low", score, matches=matches)
    return _ResolvedEntity(
        entity_id=str(best.get("film_id")),
        name=best.get("film_name"),
        confidence=confidence,
        score=score,
        raw=best,
        matches=matches,
    )


async def _get_nearby_cinemas(
    client: _MovieGluClient,
    location: _GeoPoint,
    radius_miles: float,
    max_results: int,
) -> list[dict[str, Any]]:
    raw = await client.get(
        "cinemasNearby/",
        params={"n": min(MAX_MOVIEGLU_PAGE_SIZE, max(10, max_results * 3))},
        geolocation=location,
    )
    cinemas = raw.get("cinemas") or []
    return [
        c
        for c in cinemas
        if _safe_float(c.get("distance"), default=9999) <= radius_miles
    ]


async def _get_cinema_showtimes(
    client: _MovieGluClient,
    cinema_id: str,
    date: str,
    movie_id: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"cinema_id": cinema_id, "date": date, "sort": "popularity"}
    if movie_id:
        params["film_id"] = movie_id
    return await client.get("cinemaShowTimes/", params=params)


async def _get_movie_showtimes(
    client: _MovieGluClient,
    movie_id: str,
    location: _GeoPoint,
    date: str,
    max_results: int,
) -> dict[str, Any]:
    return await client.get(
        "filmShowTimes/",
        params={"film_id": movie_id, "date": date, "n": min(MAX_MOVIEGLU_PAGE_SIZE, max(10, max_results * 3))},
        geolocation=location,
    )


def _normalize_showtime_response(
    raw_payloads: list[dict[str, Any]],
    date: str,
    cinemas_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_payloads:
        if not isinstance(raw, dict):
            continue
        if raw.get("films") is not None:
            normalized.extend(_normalize_cinema_showtimes(raw, date, cinemas_by_id))
        if raw.get("cinemas") is not None and raw.get("film") is not None:
            normalized.extend(_normalize_film_showtimes(raw, date, cinemas_by_id))
    return normalized


def _normalize_cinema_showtimes(
    raw: dict[str, Any],
    date: str,
    cinemas_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    cinema = raw.get("cinema") or {}
    cinema_id = str(cinema.get("cinema_id")) if cinema.get("cinema_id") is not None else None
    cinema_meta = cinemas_by_id.get(str(cinema_id)) or {}
    rows: list[dict[str, Any]] = []
    for film in raw.get("films") or []:
        rows.extend(
            _rows_from_showings(
                film=film,
                showings=film.get("showings") or {},
                cinema_id=cinema_id,
                cinema_name=cinema.get("cinema_name") or cinema_meta.get("cinema_name"),
                cinema_meta=cinema_meta,
                date=date,
            )
        )
    return rows


def _normalize_film_showtimes(
    raw: dict[str, Any],
    date: str,
    cinemas_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    film = raw.get("film") or {}
    rows: list[dict[str, Any]] = []
    for cinema in raw.get("cinemas") or []:
        cinema_id = str(cinema.get("cinema_id")) if cinema.get("cinema_id") is not None else None
        cinema_meta = {**(cinemas_by_id.get(str(cinema_id)) or {}), **cinema}
        rows.extend(
            _rows_from_showings(
                film=film,
                showings=cinema.get("showings") or {},
                cinema_id=cinema_id,
                cinema_name=cinema.get("cinema_name") or cinema_meta.get("cinema_name"),
                cinema_meta=cinema_meta,
                date=date,
            )
        )
    return rows


def _rows_from_showings(
    film: dict[str, Any],
    showings: dict[str, Any],
    cinema_id: str | None,
    cinema_name: str | None,
    cinema_meta: dict[str, Any],
    date: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for format_name, showing in showings.items():
        for showtime in (showing or {}).get("times") or []:
            raw_time = showtime.get("start_time")
            parsed_time = _parse_time(raw_time)
            if not parsed_time:
                continue
            film_id = showing.get("film_id") or film.get("film_id")
            film_name = showing.get("film_name") or film.get("film_name")
            rows.append(
                {
                    "movie_title": film_name,
                    "movie_id": str(film_id) if film_id is not None else None,
                    "genre": None,
                    "genres": [],
                    "theater_name": cinema_name,
                    "theater_id": cinema_id,
                    "theater_address": _format_address(cinema_meta),
                    "start_date": date,
                    "start_time_raw": raw_time,
                    "start_time_obj": parsed_time,
                    "start_time": _showtime_iso(date, parsed_time),
                    "display_time": _display_time(parsed_time),
                    "distance_miles": _safe_float(cinema_meta.get("distance"), default=None),
                    "format": _normalize_format(str(format_name or film.get("version_type") or "Unknown")),
                    "booking_url": None,
                }
            )
    return rows


def _filter_by_distance(
    showtimes: list[dict[str, Any]],
    radius_miles: float,
) -> list[dict[str, Any]]:
    return [
        s
        for s in showtimes
        if s.get("distance_miles") is None or s["distance_miles"] <= radius_miles
    ]


def _filter_by_time(
    showtimes: list[dict[str, Any]],
    time_from: time | None,
    time_to: time | None,
) -> list[dict[str, Any]]:
    if not time_from and not time_to:
        return showtimes
    return [
        s
        for s in showtimes
        if _time_in_window(s.get("start_time_obj"), time_from, time_to)
    ]


def _filter_by_genre(showtimes: list[dict[str, Any]], genre: str | None) -> list[dict[str, Any]]:
    if not genre:
        return showtimes
    return [
        s
        for s in showtimes
        if any(_genre_matches(genre, g) for g in s.get("genres") or [])
    ]


def _rank_results(
    showtimes: list[dict[str, Any]],
    target_time: time | None,
    movie_title: str | None,
    theater_name: str | None,
    genre: str | None,
) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[Any, ...]:
        theater_score = _match_score(theater_name, item.get("theater_name")) if theater_name else 0.0
        title_score = _match_score(movie_title, item.get("movie_title")) if movie_title else 0.0
        genre_score = max(
            [_match_score(genre, g) for g in item.get("genres") or []],
            default=0.0,
        ) if genre else 0.0
        target_delta = _minutes_delta(item.get("start_time_obj"), target_time) if target_time else 0
        distance = item.get("distance_miles") if item.get("distance_miles") is not None else 9999
        minutes = _minutes_since_midnight(item.get("start_time_obj"))
        return (
            -(1 if theater_score >= 0.92 else 0),
            -(1 if title_score >= 0.92 else 0),
            target_delta,
            distance,
            -genre_score,
            minutes,
        )

    ranked = sorted(showtimes, key=key)
    for item in ranked:
        score_parts = [
            _match_score(movie_title, item.get("movie_title")) if movie_title else 1.0,
            _match_score(theater_name, item.get("theater_name")) if theater_name else 1.0,
        ]
        item["confidence"] = _confidence(min(score_parts))
    return ranked


async def _get_film_details_for_results(
    client: _MovieGluClient,
    showtimes: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    film_ids: list[str] = []
    for item in showtimes:
        film_id = item.get("movie_id")
        if film_id and film_id not in film_ids:
            film_ids.append(film_id)
    film_ids = film_ids[:30]
    tasks = [client.get("filmDetails/", params={"film_id": film_id}) for film_id in film_ids]
    details = await asyncio.gather(*tasks, return_exceptions=True)
    results: dict[str, dict[str, Any]] = {}
    for film_id, detail in zip(film_ids, details, strict=False):
        if isinstance(detail, dict):
            results[film_id] = detail
        elif isinstance(detail, Exception):
            warnings.append(
                {
                    "code": "film_details_unavailable",
                    "movie_id": film_id,
                    "message": str(detail),
                }
            )
    return results


def _attach_genres(showtimes: list[dict[str, Any]], details_by_id: dict[str, dict[str, Any]]) -> None:
    for item in showtimes:
        detail = details_by_id.get(str(item.get("movie_id"))) or {}
        genres = [g.get("genre_name") for g in detail.get("genres") or [] if g.get("genre_name")]
        item["genres"] = genres
        item["genre"] = ", ".join(genres) if genres else None


async def _attach_booking_links(
    client: _MovieGluClient,
    showtimes: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    async def fetch_link(item: dict[str, Any]) -> str | None:
        if not item.get("movie_id") or not item.get("theater_id") or not item.get("start_time_raw"):
            return None
        raw = await client.get(
            "purchaseConfirmation/",
            params={
                "cinema_id": item["theater_id"],
                "film_id": item["movie_id"],
                "date": item["start_date"],
                "time": item["start_time_raw"],
            },
        )
        return raw.get("url")

    tasks = [fetch_link(s) for s in showtimes]
    links = await asyncio.gather(*tasks, return_exceptions=True)
    for item, link in zip(showtimes, links, strict=False):
        if isinstance(link, str):
            item["booking_url"] = link
        elif isinstance(link, Exception):
            warnings.append({"code": "booking_link_unavailable", "message": str(link)})


def _response_shell(
    location: str | None,
    theater_name: str | None,
    movie_title: str | None,
    genre: str | None,
    resolved_date: str,
    start_window: time | None,
    end_window: time | None,
    generated_at: str,
    warnings: list[dict[str, Any]],
) -> SkillResponse:
    return SkillResponse(
        query_interpretation=QueryInterpretation(
            location=location,
            theater_name=theater_name,
            movie_title=movie_title,
            genre=genre,
            date=resolved_date,
            time_window=TimeWindow(
                from_=_time_to_str(start_window),
                to=_time_to_str(end_window),
            ),
        ),
        results=[],
        metadata=SkillMetadata(result_count=0, generated_at=generated_at),
        errors=[],
        warnings=warnings,
    )


def _dump_response(response: SkillResponse) -> dict[str, Any]:
    return response.model_dump(mode="json", by_alias=True)


def _to_result(item: dict[str, Any]) -> ShowtimeResult:
    return ShowtimeResult(
        movie_title=item.get("movie_title"),
        movie_id=item.get("movie_id"),
        genre=item.get("genre"),
        theater_name=item.get("theater_name"),
        theater_id=item.get("theater_id"),
        theater_address=item.get("theater_address"),
        start_time=item.get("start_time"),
        display_time=item.get("display_time"),
        distance_miles=item.get("distance_miles"),
        format=item.get("format") or "Unknown",
        booking_url=item.get("booking_url"),
        confidence=item.get("confidence") or "medium",
    )


def _resolve_date(value: str | None, warnings: list[dict[str, Any]]) -> str:
    if not value:
        return date_type.today().isoformat()
    try:
        return date_type.fromisoformat(value).isoformat()
    except ValueError:
        normalized = _normalize_text(value)
        if normalized in {"today", "tonight"}:
            return date_type.today().isoformat()
        if normalized == "tomorrow":
            return (date_type.today() + timedelta(days=1)).isoformat()
        warnings.append(
            {"code": "date_parse_failed", "input": value, "fallback": date_type.today().isoformat()}
        )
        return date_type.today().isoformat()


def _resolve_time_window(
    time_from: str | None,
    time_to: str | None,
    target_time: str | None,
    warnings: list[dict[str, Any]],
) -> tuple[time | None, time | None]:
    explicit_from = _parse_time(time_from)
    explicit_to = _parse_time(time_to)
    if time_from and not explicit_from:
        warnings.append({"code": "time_parse_failed", "field": "time_from", "input": time_from})
    if time_to and not explicit_to:
        warnings.append({"code": "time_parse_failed", "field": "time_to", "input": time_to})
    if explicit_from or explicit_to:
        return explicit_from, explicit_to

    target = _parse_time(target_time)
    if target_time and not target:
        warnings.append({"code": "time_parse_failed", "field": "target_time", "input": target_time})
        return None, None
    if not target:
        return None, None
    anchor = datetime.combine(date_type.today(), target)
    return (anchor - timedelta(minutes=TIME_WINDOW_MINUTES)).time(), (
        anchor + timedelta(minutes=TIME_WINDOW_MINUTES)
    ).time()


def _parse_time(value: Any) -> time | None:
    if not value:
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip().lower().replace(".", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    suffix = match.group(3)
    if minute > 59:
        return None
    if suffix == "pm" and hour != 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if hour > 23:
        return None
    return time(hour=hour, minute=minute)


def _time_to_str(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _display_time(value: time) -> str:
    return datetime.combine(date_type.today(), value).strftime("%-I:%M %p")


def _showtime_iso(show_date: str, start: time) -> str:
    parsed_date = date_type.fromisoformat(show_date)
    if start < time(hour=3):
        parsed_date = parsed_date + timedelta(days=1)
    return datetime.combine(parsed_date, start).isoformat(timespec="seconds")


def _time_in_window(value: time | None, start: time | None, end: time | None) -> bool:
    if not value:
        return False
    value_minutes = _minutes_since_midnight(value)
    if start and end and start > end:
        return value >= start or value <= end
    if start and value_minutes < _minutes_since_midnight(start):
        return False
    if end and value_minutes > _minutes_since_midnight(end):
        return False
    return True


def _minutes_since_midnight(value: time | None) -> int:
    if not value:
        return 9999
    return value.hour * 60 + value.minute


def _minutes_delta(value: time | None, target: time | None) -> int:
    if not value or not target:
        return 0
    direct = abs(_minutes_since_midnight(value) - _minutes_since_midnight(target))
    return min(direct, 1440 - direct)


def _parse_lat_lng(value: str) -> _GeoPoint | None:
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*", value)
    if not match:
        return None
    lat = float(match.group(1))
    lng = float(match.group(2))
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return _GeoPoint(lat=lat, lng=lng, label=value)
    return None


def _format_address(cinema: dict[str, Any]) -> str | None:
    parts = [
        cinema.get("address"),
        cinema.get("address2"),
        cinema.get("city"),
        cinema.get("postcode"),
    ]
    text = ", ".join(str(p) for p in parts if p)
    return text or None


def _normalize_format(value: str) -> str:
    normalized = value.replace("3DIMAX", "IMAX 3D").replace("IMAX3D", "IMAX 3D")
    known = ["Dolby", "IMAX", "3D", "Standard"]
    for item in known:
        if item.lower() in normalized.lower():
            return normalized
    return normalized if normalized and normalized != "None" else "Unknown"


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _genre_matches(query: str, candidate: str) -> bool:
    query_terms = {_singularize(term) for term in _normalize_text(query).split()}
    candidate_terms = {_singularize(term) for term in _normalize_text(candidate).split()}
    return bool(query_terms & candidate_terms) or _normalize_text(candidate) in _normalize_text(query)


def _singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value


def _match_score(query: Any, candidate: Any) -> float:
    q = _normalize_text(query)
    c = _normalize_text(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        return 0.95
    return SequenceMatcher(None, q, c).ratio()


def _confidence(score: float) -> str:
    if score >= 0.88:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def _safe_float(value: Any, default: float | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cinema_match(cinema: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "theater_id": str(cinema.get("cinema_id")) if cinema.get("cinema_id") is not None else None,
        "theater_name": cinema.get("cinema_name"),
        "address": _format_address(cinema),
        "distance_miles": _safe_float(cinema.get("distance"), default=None),
        "score": round(_match_score(query, cinema.get("cinema_name")), 3),
    }


def _film_match(film: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "movie_id": str(film.get("film_id")) if film.get("film_id") is not None else None,
        "movie_title": film.get("film_name"),
        "score": round(_match_score(query, film.get("film_name")), 3),
    }


def _no_result_reasons(
    had_raw_results: bool,
    genre: str | None,
    time_from: time | None,
    time_to: time | None,
    radius_miles: float,
    genre_metadata_unavailable: bool = False,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if not had_raw_results:
        reasons.append({"code": "no_showtimes_from_source"})
    if genre:
        reasons.append({"code": "genre_filter_may_be_too_restrictive", "genre": genre})
    if genre_metadata_unavailable:
        reasons.append({"code": "genre_metadata_unavailable"})
    if time_from or time_to:
        reasons.append(
            {
                "code": "time_window_filter_may_be_too_restrictive",
                "from": _time_to_str(time_from),
                "to": _time_to_str(time_to),
            }
        )
    reasons.append({"code": "radius_limit", "radius_miles": radius_miles})
    return reasons
