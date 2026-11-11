"""Shared core for the Flight-Scraper REST API and MCP server.

Everything that talks to Google Flights (via `fast-flights`) or the bundled
airport dataset lives here, so the FastAPI app and the MCP server expose the
exact same behavior.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta
from functools import lru_cache

import airportsdata
from fast_flights import (
    FlightsNotFound,
    FlightQuery,
    Passengers,
    create_query,
    get_flights,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IATA_RE = re.compile(r"^[A-Z]{3}$")

SEATS = ("economy", "premium-economy", "business", "first")
TRIPS = ("one-way", "round-trip")


@lru_cache(maxsize=1)
def _airports_db() -> dict:
    return airportsdata.load("IATA")


def search_airports(query: str, limit: int = 10) -> list[dict]:
    """Find airports by IATA code, name, city, state, or country."""
    q = (query or "").strip()
    if not q:
        return []
    ql = q.lower()
    qu = q.upper()
    scored: list[tuple[int, str, dict]] = []
    for code, a in _airports_db().items():
        name = (a.get("name") or "").lower()
        city = (a.get("city") or "").lower()
        state = (a.get("subd") or "").lower()
        country = (a.get("country") or "").lower()
        score: int | None = None
        if code == qu:
            score = 1000
        elif code.startswith(qu):
            score = 900
        elif name.startswith(ql):
            score = 800
        elif city.startswith(ql):
            score = 700
        elif ql in name:
            score = 500
        elif ql in city:
            score = 400
        elif ql in state or ql in country:
            score = 300
        if score is not None:
            scored.append((score, code, a))
    scored.sort(key=lambda t: (-t[0], t[1]))
    out = []
    for _score, code, a in scored[: max(1, min(limit, 25))]:
        out.append(
            {
                "code": code,
                "name": a.get("name"),
                "city": a.get("city"),
                "state": a.get("subd"),
                "country": a.get("country"),
                "lat": a.get("lat"),
                "lon": a.get("lon"),
            }
        )
    return out


def airport_info(code: str) -> dict | None:
    """Return details for a single IATA code, or None if unknown."""
    a = _airports_db().get((code or "").strip().upper())
    if a is None:
        return None
    return {
        "code": a.get("iata"),
        "icao": a.get("icao"),
        "name": a.get("name"),
        "city": a.get("city"),
        "state": a.get("subd"),
        "country": a.get("country"),
        "lat": a.get("lat"),
        "lon": a.get("lon"),
        "timezone": a.get("tz"),
    }


def _fmt_dt(d) -> str:
    y, m, day = d.date
    hh, mm = d.time
    return f"{y:04d}-{m:02d}-{day:02d}T{hh:02d}:{mm:02d}"


def _fmt_duration(minutes: int) -> str:
    if not minutes:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _airline_map(result) -> dict:
    meta = getattr(result, "metadata", None)
    if meta is None:
        return {}
    return {a.code: a.name for a in meta.airlines}


def _validate(
    from_airport: str,
    to_airport: str,
    date: str,
    return_date: str | None,
    trip: str,
    seat: str,
    adults: int,
    children: int,
    infants_in_seat: int,
    infants_on_lap: int,
) -> tuple[str, str]:
    if not from_airport or not to_airport:
        raise ValueError("from_airport and to_airport are required (3-letter IATA codes)")
    origin = from_airport.strip().upper()
    destination = to_airport.strip().upper()
    if not IATA_RE.match(origin) or not IATA_RE.match(destination):
        raise ValueError("airports must be 3-letter IATA codes (e.g. DFW, JFK)")
    if not DATE_RE.match(date):
        raise ValueError("date must be in YYYY-MM-DD format")
    if trip not in TRIPS:
        raise ValueError(f"trip must be one of {sorted(TRIPS)}")
    if seat not in SEATS:
        raise ValueError(f"seat must be one of {sorted(SEATS)}")
    if trip == "round-trip":
        if not return_date:
            raise ValueError("return_date is required for round-trip")
        if not DATE_RE.match(return_date):
            raise ValueError("return_date must be in YYYY-MM-DD format")
        if return_date <= date:
            raise ValueError("return_date must be after date")
    total = adults + children + infants_in_seat + infants_on_lap
    if total > 9:
        raise ValueError("total passengers cannot exceed 9")
    if infants_on_lap > adults:
        raise ValueError("infants_on_lap cannot exceed adults")
    return origin, destination


def search_flights(
    from_airport: str,
    to_airport: str,
    date: str,
    return_date: str | None = None,
    trip: str = "one-way",
    seat: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    max_stops: int | None = None,
    currency: str = "USD",
    language: str = "en-US",
    proxy: str | None = None,
) -> dict:
    """Search Google Flights and return structured results."""
    origin, destination = _validate(
        from_airport, to_airport, date, return_date, trip, seat,
        adults, children, infants_in_seat, infants_on_lap,
    )

    legs = [
        FlightQuery(date=date, from_airport=origin, to_airport=destination, max_stops=max_stops)
    ]
    if trip == "round-trip":
        legs.append(
            FlightQuery(date=return_date, from_airport=destination, to_airport=origin, max_stops=max_stops)
        )

    passengers = Passengers(
        adults=adults,
        children=children,
        infants_in_seat=infants_in_seat,
        infants_on_lap=infants_on_lap,
    )

    query = create_query(
        flights=legs,
        seat=seat,
        trip=trip,
        passengers=passengers,
        currency=currency.upper(),
        language=language,
    )

    proxy = proxy or os.environ.get("FLIGHTS_PROXY")
    try:
        result = get_flights(query, proxy=proxy)
    except FlightsNotFound:
        result = []

    names = _airline_map(result)

    flights_out = []
    for f in result:
        segments = [
            {
                "from_airport": {"code": s.from_airport.code, "name": s.from_airport.name},
                "to_airport": {"code": s.to_airport.code, "name": s.to_airport.name},
                "departure": _fmt_dt(s.departure),
                "arrival": _fmt_dt(s.arrival),
                "duration_minutes": s.duration,
                "duration": _fmt_duration(s.duration),
                "plane_type": s.plane_type,
            }
            for s in f.flights
        ]
        flights_out.append(
            {
                "price": f.price,
                "airlines": f.airlines,
                "airline_names": [names.get(c, c) for c in f.airlines],
                "stops": len(f.flights) - 1,
                "segments": segments,
                "carbon_emission_grams": getattr(f.carbon, "emission", None),
                "carbon_typical_grams": getattr(f.carbon, "typical_on_route", None),
            }
        )

    prices = [f["price"] for f in flights_out]
    return {
        "query": {
            "from_airport": origin,
            "to_airport": destination,
            "date": date,
            "return_date": return_date,
            "trip": trip,
            "seat": seat,
            "currency": currency.upper(),
            "passengers": {
                "adults": adults,
                "children": children,
                "infants_in_seat": infants_in_seat,
                "infants_on_lap": infants_on_lap,
            },
        },
        "best_price": prices[0] if prices else None,
        "cheapest_price": min(prices) if prices else None,
        "book_url": query.url(),
        "count": len(flights_out),
        "flights": flights_out,
    }


def _date_range(start_date: str, days: int) -> list[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def cheapest_days(
    from_airport: str,
    to_airport: str,
    start_date: str,
    days: int = 7,
    seat: str = "economy",
    adults: int = 1,
    max_stops: int | None = None,
    currency: str = "USD",
    proxy: str | None = None,
) -> dict:
    """Cheapest one-way price for each day over a window."""
    if not DATE_RE.match(start_date):
        raise ValueError("start_date must be in YYYY-MM-DD format")
    days = max(1, min(days, 14))
    origin, destination = _validate(
        from_airport, to_airport, start_date, None, "one-way", seat, adults, 0, 0, 0
    )
    results = []
    for d in _date_range(start_date, days):
        try:
            r = search_flights(
                origin, destination, d, trip="one-way", seat=seat,
                adults=adults, max_stops=max_stops, currency=currency, proxy=proxy,
            )
            results.append({"date": d, "cheapest_price": r["cheapest_price"], "num_flights": r["count"]})
        except Exception:
            results.append({"date": d, "cheapest_price": None, "num_flights": 0})
        time.sleep(0.3)
    return {
        "from_airport": origin,
        "to_airport": destination,
        "start_date": start_date,
        "days": days,
        "currency": currency.upper(),
        "results": results,
    }


def flight_stats(
    from_airport: str,
    to_airport: str,
    date: str,
    seat: str = "economy",
    adults: int = 1,
    max_stops: int | None = None,
    currency: str = "USD",
    proxy: str | None = None,
) -> dict:
    """Aggregate statistics over a single route+date search."""
    r = search_flights(
        from_airport, to_airport, date, trip="one-way", seat=seat,
        adults=adults, max_stops=max_stops, currency=currency, proxy=proxy,
    )
    flights = r["flights"]
    n = len(flights)
    if n == 0:
        return {"query": r["query"], "num_flights": 0, "note": "no flights found"}

    prices = sorted(f["price"] for f in flights)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) // 2
    cheapest = min(flights, key=lambda f: f["price"])
    priciest = max(flights, key=lambda f: f["price"])
    avg_stops = sum(f["stops"] for f in flights) / n

    return {
        "query": r["query"],
        "num_flights": n,
        "min_price": prices[0],
        "median_price": median,
        "max_price": prices[-1],
        "avg_stops": round(avg_stops, 2),
        "cheapest": {
            "price": cheapest["price"],
            "airlines": cheapest["airline_names"],
            "stops": cheapest["stops"],
        },
        "priciest": {
            "price": priciest["price"],
            "airlines": priciest["airline_names"],
            "stops": priciest["stops"],
        },
        "book_url": r["book_url"],
    }
