from typing import Literal, Optional

import os
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fast_flights import (
    FlightsNotFound,
    FlightQuery,
    Passengers,
    create_query,
    get_flights,
)

app = FastAPI(title="Flight Scraper API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fmt_dt(d) -> str:
    """Format a fast_flights SimpleDatetime into ISO-8601-ish local time."""
    y, m, day = d.date
    hh, mm = d.time
    return f"{y:04d}-{m:02d}-{day:02d}T{hh:02d}:{mm:02d}"


def _fmt_duration(minutes: int) -> str:
    if not minutes:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _airline_map(result) -> dict:
    """Build {code: name} from result metadata. Metadata is absent when empty."""
    meta = getattr(result, "metadata", None)
    if meta is None:
        return {}
    return {a.code: a.name for a in meta.airlines}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/flights")
def search_flights(
    from_airport: str = Query(..., description="IATA departure airport code (e.g. LAX)"),
    to_airport: str = Query(..., description="IATA arrival airport code (e.g. JFK)"),
    date: str = Query(..., description="Departure date in YYYY-MM-DD format"),
    return_date: Optional[str] = Query(
        None, description="Return date in YYYY-MM-DD format (required for round-trip)"
    ),
    trip: Literal["one-way", "round-trip"] = Query("one-way"),
    seat: Literal["economy", "premium-economy", "business", "first"] = Query("economy"),
    adults: int = Query(1, ge=1, le=9),
    children: int = Query(0, ge=0, le=9),
    infants_in_seat: int = Query(0, ge=0, le=9),
    infants_on_lap: int = Query(0, ge=0, le=9),
    max_stops: Optional[int] = Query(None, ge=0, le=3, description="Max stops (0 = nonstop)"),
    currency: str = Query("USD", description="ISO-4217 currency code (e.g. USD, EUR)"),
    language: str = Query("en-US", description="Language code (e.g. en-US)"),
):
    if not DATE_RE.match(date):
        raise HTTPException(status_code=422, detail="date must be in YYYY-MM-DD format")

    if trip == "round-trip":
        if not return_date:
            raise HTTPException(status_code=422, detail="return_date is required for round-trip")
        if not DATE_RE.match(return_date):
            raise HTTPException(status_code=422, detail="return_date must be in YYYY-MM-DD format")
        if return_date <= date:
            raise HTTPException(status_code=422, detail="return_date must be after date")

    total_passengers = adults + children + infants_in_seat + infants_on_lap
    if total_passengers > 9:
        raise HTTPException(status_code=422, detail="Total passengers cannot exceed 9")
    if infants_on_lap > adults:
        raise HTTPException(status_code=422, detail="infants_on_lap cannot exceed number of adults")

    origin = from_airport.upper()
    destination = to_airport.upper()

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

    proxy = os.environ.get("FLIGHTS_PROXY")

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


# Serve the built React frontend. In Docker it lands in ./static; locally, ./fe/dist.
_BASE = os.path.dirname(os.path.abspath(__file__))
for _static_dir in (
    os.path.join(_BASE, "static"),
    os.path.join(_BASE, "fe", "dist"),
):
    if os.path.isdir(_static_dir):
        app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
        break
