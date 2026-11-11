from typing import Literal, Optional

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import flight_core

app = FastAPI(title="Flight Scraper API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/airports")
def airports(
    q: str = Query(..., min_length=1, description="Airport code, name, city, or country"),
    limit: int = Query(10, ge=1, le=25),
):
    return {"results": flight_core.search_airports(q, limit)}


@app.get("/airports/{code}")
def airport_info(code: str):
    info = flight_core.airport_info(code)
    if info is None:
        raise HTTPException(status_code=404, detail=f"unknown airport code: {code}")
    return info


@app.get("/flights")
def search_flights(
    from_airport: str = Query(..., description="IATA departure airport code (e.g. DFW)"),
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
    try:
        return flight_core.search_flights(
            from_airport,
            to_airport,
            date,
            return_date=return_date,
            trip=trip,
            seat=seat,
            adults=adults,
            children=children,
            infants_in_seat=infants_in_seat,
            infants_on_lap=infants_on_lap,
            max_stops=max_stops,
            currency=currency,
            language=language,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# Serve the built React frontend. In Docker it lands in ./static; locally, ./fe/dist.
_BASE = os.path.dirname(os.path.abspath(__file__))
for _static_dir in (
    os.path.join(_BASE, "static"),
    os.path.join(_BASE, "fe", "dist"),
):
    if os.path.isdir(_static_dir):
        app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
        break
