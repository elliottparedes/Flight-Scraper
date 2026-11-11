"""Flight-Scraper as a Model Context Protocol (MCP) server.

Exposes live Google Flights search + airport lookup to AI agents (Claude,
Cursor, etc.) over stdio or streamable HTTP.

Usage:
    python mcp_server.py                                     # stdio (local: Claude Desktop / Cursor)
    python mcp_server.py --transport streamable-http --port 8020   # remote HTTP endpoint at /mcp
"""
from __future__ import annotations

import argparse
import os

from mcp.server.mcpserver import MCPServer

import flight_core

server = MCPServer(
    name="flight-scraper",
    title="Flight Scraper",
    description="Live Google Flights search and airport lookup — free, self-hosted, no API key.",
    version="2.1.0",
)


def _proxy() -> str | None:
    return os.environ.get("FLIGHTS_PROXY")


@server.tool()
def search_airports(query: str, limit: int = 8) -> list[dict]:
    """Find airports by IATA code, name, city, state, or country.

    e.g. "dallas" returns DFW and DAL; "heathrow" returns LHR.
    Returns a list of {code, name, city, state, country}.
    """
    return flight_core.search_airports(query, limit)


@server.tool()
def airport_info(code: str) -> dict:
    """Get details (name, city, country, coordinates, timezone) for one IATA code like "DFW"."""
    info = flight_core.airport_info(code)
    if info is None:
        return {"error": f"unknown airport code: {code}"}
    return info


@server.tool()
def search_flights(
    from_airport: str,
    to_airport: str,
    date: str,
    return_date: str | None = None,
    trip: str = "one-way",
    seat: str = "economy",
    adults: int = 1,
    max_stops: int | None = None,
    currency: str = "USD",
) -> dict:
    """Search Google Flights for flights between two IATA airports.

    `date` and `return_date` are YYYY-MM-DD. `trip` is "one-way" or
    "round-trip" (round-trip requires return_date). `seat` is economy,
    premium-economy, business, or first. `max_stops` 0 = nonstop only.
    Returns best/cheapest price, a book URL, and a list of flights with
    segments (times, duration, plane type, stops, carbon).
    """
    try:
        return flight_core.search_flights(
            from_airport, to_airport, date, return_date=return_date, trip=trip,
            seat=seat, adults=adults, max_stops=max_stops, currency=currency, proxy=_proxy(),
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"search failed: {e}"}


@server.tool()
def cheapest_days(
    from_airport: str,
    to_airport: str,
    start_date: str,
    days: int = 7,
    seat: str = "economy",
    adults: int = 1,
    currency: str = "USD",
) -> dict:
    """Cheapest one-way price for each day over a window (e.g. next 7 days).

    start_date is YYYY-MM-DD; days is 1-14. Useful for "when is the cheapest
    day to fly". Returns a list of {date, cheapest_price, num_flights}.
    """
    try:
        return flight_core.cheapest_days(
            from_airport, to_airport, start_date, days=days, seat=seat,
            adults=adults, currency=currency, proxy=_proxy(),
        )
    except ValueError as e:
        return {"error": str(e)}


@server.tool()
def flight_stats(
    from_airport: str,
    to_airport: str,
    date: str,
    seat: str = "economy",
    adults: int = 1,
    currency: str = "USD",
) -> dict:
    """Aggregate stats for a route+date: min/median/max price, avg stops, cheapest & priciest flight."""
    try:
        return flight_core.flight_stats(
            from_airport, to_airport, date, seat=seat, adults=adults, currency=currency, proxy=_proxy(),
        )
    except ValueError as e:
        return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Flight-Scraper MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
