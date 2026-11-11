# ✈️ Flight Scraper

A tiny FastAPI service that searches [Google Flights](https://flights.google.com) and returns
live, structured results — no API key, no headless browser. Ships with a small web UI.

Backed by [`fast-flights`](https://github.com/AWeirdDev/flights) (pinned to `3.1.0`), which
builds a Base64-encoded Protobuf `?tfs=` query and parses Google's own JS payload with a
browser-impersonating HTTP client (`primp`). No Playwright, no Chromium.

## Quick start

### Docker (recommended)

```bash
docker build -t flight-scraper .
docker run -d --name flight-scraper -p 8000:8000 flight-scraper
```

Open http://localhost:8000 for the UI.

### Local

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

### `GET /flights`

| Param | Type | Default | Notes |
|---|---|---|---|
| `from_airport` | str | — | IATA code, e.g. `DFW` |
| `to_airport` | str | — | IATA code, e.g. `JFK` |
| `date` | str | — | `YYYY-MM-DD` |
| `return_date` | str | — | required for round-trip |
| `trip` | str | `one-way` | `one-way` \| `round-trip` |
| `seat` | str | `economy` | `economy` \| `premium-economy` \| `business` \| `first` |
| `adults` | int | `1` | 1–9 |
| `children` | int | `0` | 0–9 |
| `infants_in_seat` | int | `0` | 0–9 |
| `infants_on_lap` | int | `0` | 0–9 (≤ adults) |
| `max_stops` | int | — | `0` = nonstop only |
| `currency` | str | `USD` | ISO-4217 |
| `language` | str | `en-US` | e.g. `en-US` |

**Example**

```bash
curl "http://localhost:8000/flights?from_airport=DFW&to_airport=JFK&date=2026-12-05&trip=round-trip&return_date=2026-12-10&adults=1"
```

**Response**

```json
{
  "query": { "from_airport": "DFW", "to_airport": "JFK", "date": "2026-12-05", "trip": "round-trip", ... },
  "best_price": 277,
  "cheapest_price": 277,
  "book_url": "https://www.google.com/travel/flights/search?tfs=...",
  "count": 9,
  "flights": [
    {
      "price": 277,
      "airlines": ["American"],
      "airline_names": ["American"],
      "stops": 1,
      "segments": [
        {
          "from_airport": { "code": "DFW", "name": "Dallas Fort Worth International Airport" },
          "to_airport": { "code": "ATL", "name": "Hartsfield-Jackson Atlanta International Airport" },
          "departure": "2026-12-05T11:00",
          "arrival": "2026-12-05T14:05",
          "duration_minutes": 125,
          "duration": "2h 5m",
          "plane_type": "Boeing 737"
        }
      ],
      "carbon_emission_grams": 130000,
      "carbon_typical_grams": 145000
    }
  ]
}
```

### `GET /airports`

Search the bundled airport dataset (7,950 airports) by IATA code, name, city, state, or country.

```bash
curl "http://localhost:8000/airports?q=dallas&limit=5"
curl "http://localhost:8000/airports/DFW"
```

Returns `{"results": [{"code", "name", "city", "state", "country", "lat", "lon"}, ...]}`.

### Other endpoints

- `GET /health` → `{"status": "ok"}`
- `GET /` → the web UI

## MCP server

The same core is exposed as a **Model Context Protocol (MCP) server**, so AI agents
(Claude Desktop, Cursor, etc.) can search flights and airports as tool calls.

**Tools**

| Tool | What it does |
|---|---|
| `search_flights` | Live Google Flights search (one-way / round-trip, seat, stops, currency) |
| `search_airports` | Airport autocomplete by code / name / city |
| `airport_info` | Details for one IATA code |
| `cheapest_days` | Cheapest one-way price for each day over a window |
| `flight_stats` | min / median / max price, avg stops for a route+date |

**Run it**

```bash
# stdio (local — point Claude Desktop / Cursor at this command)
python mcp_server.py

# streamable HTTP (remote — connect a client to http://host:8020/mcp)
python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8020
```

**Claude Desktop / Cursor config (stdio)**

```json
{
  "mcpServers": {
    "flight-scraper": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/Flight-Scraper"
    }
  }
}
```

## Notes

- **It's a scraper.** Google can throttle or block datacenter IPs. For heavy or production
  use, route traffic through a residential proxy by setting the `FLIGHTS_PROXY` env var, or
  swap in one of `fast-flights`'s official integrations (SearchApi / Bright Data).
- Results are Google's "best flights" ordering; `best_price` is the top result,
  `cheapest_price` is the minimum across the whole list.
