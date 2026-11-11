import { useState } from "react";
import {
  ExternalLink,
  Leaf,
  Loader2,
  Plane,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

interface Airport {
  code: string;
  name: string;
}
interface Segment {
  from_airport: Airport;
  to_airport: Airport;
  departure: string;
  arrival: string;
  duration_minutes: number;
  duration: string;
  plane_type: string;
}
interface Flight {
  price: number;
  airlines: string[];
  airline_names: string[];
  stops: number;
  segments: Segment[];
  carbon_emission_grams: number | null;
  carbon_typical_grams: number | null;
}
interface ApiResponse {
  query: {
    from_airport: string;
    to_airport: string;
    date: string;
    return_date: string | null;
    trip: string;
    seat: string;
    currency: string;
  };
  best_price: number | null;
  cheapest_price: number | null;
  book_url: string;
  count: number;
  flights: Flight[];
}

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "MXN", "INR"];
const SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  CAD: "C$",
  AUD: "A$",
  JPY: "¥",
  MXN: "MX$",
  INR: "₹",
};

function isoDays(n: number) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function fmtTime(iso: string) {
  const [d, t] = iso.split("T");
  const [, m, day] = d.split("-").map(Number);
  const [h, min] = t.split(":");
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return { date: `${months[m - 1]} ${day}`, time: `${h}:${min}` };
}

function fmtDuration(totalMin: number) {
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

export default function App() {
  const [trip, setTrip] = useState<"one-way" | "round-trip">("one-way");
  const [from, setFrom] = useState("DFW");
  const [to, setTo] = useState("JFK");
  const [date, setDate] = useState(isoDays(14));
  const [returnDate, setReturnDate] = useState(isoDays(21));
  const [seat, setSeat] = useState("economy");
  const [stops, setStops] = useState("");
  const [adults, setAdults] = useState("1");
  const [currency, setCurrency] = useState("USD");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<ApiResponse | null>(null);

  async function search() {
    if (!from.trim() || !to.trim() || !date) {
      setError("Fill in from, to, and departure date.");
      return;
    }
    if (from.trim().length !== 3 || to.trim().length !== 3) {
      setError("Airport codes must be 3 letters (e.g. DFW).");
      return;
    }
    if (trip === "round-trip" && !returnDate) {
      setError("Return date is required for round-trip.");
      return;
    }

    const params = new URLSearchParams({
      from_airport: from.trim().toUpperCase(),
      to_airport: to.trim().toUpperCase(),
      date,
      seat,
      adults,
      currency,
      trip,
      language: "en-US",
    });
    if (trip === "round-trip") params.set("return_date", returnDate);
    if (stops !== "") params.set("max_stops", stops);

    setLoading(true);
    setError("");
    setData(null);
    try {
      const res = await fetch("/flights?" + params.toString());
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error ${res.status}`);
      }
      setData((await res.json()) as ApiResponse);
    } catch (e) {
      setError("Search failed: " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const symbol = SYMBOLS[currency] || currency + " ";

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-2xl px-4 py-10">
        <header className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15">
            <Plane className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Flight Scraper</h1>
            <p className="text-sm text-muted-foreground">
              Live Google Flights results, free
            </p>
          </div>
        </header>

        <Card>
          <CardContent className="space-y-4 p-5">
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-muted/50 p-1">
              <Button
                type="button"
                variant={trip === "one-way" ? "default" : "ghost"}
                onClick={() => setTrip("one-way")}
              >
                One-way
              </Button>
              <Button
                type="button"
                variant={trip === "round-trip" ? "default" : "ghost"}
                onClick={() => setTrip("round-trip")}
              >
                Round-trip
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="from">From</Label>
                <Input
                  id="from"
                  value={from}
                  onChange={(e) => setFrom(e.target.value.toUpperCase())}
                  maxLength={3}
                  placeholder="DFW"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="to">To</Label>
                <Input
                  id="to"
                  value={to}
                  onChange={(e) => setTo(e.target.value.toUpperCase())}
                  maxLength={3}
                  placeholder="JFK"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="date">Departure</Label>
                <Input
                  id="date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
              {trip === "round-trip" && (
                <div className="space-y-1.5">
                  <Label htmlFor="returnDate">Return</Label>
                  <Input
                    id="returnDate"
                    type="date"
                    value={returnDate}
                    onChange={(e) => setReturnDate(e.target.value)}
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="seat">Cabin</Label>
                <Select
                  id="seat"
                  value={seat}
                  onChange={(e) => setSeat(e.target.value)}
                >
                  <option value="economy">Economy</option>
                  <option value="premium-economy">Premium economy</option>
                  <option value="business">Business</option>
                  <option value="first">First</option>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="stops">Stops</Label>
                <Select
                  id="stops"
                  value={stops}
                  onChange={(e) => setStops(e.target.value)}
                >
                  <option value="">Any</option>
                  <option value="0">Nonstop only</option>
                  <option value="1">1 stop max</option>
                  <option value="2">2 stops max</option>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="adults">Adults</Label>
                <Select
                  id="adults"
                  value={adults}
                  onChange={(e) => setAdults(e.target.value)}
                >
                  {["1", "2", "3", "4", "5", "6"].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="currency">Currency</Label>
                <Select
                  id="currency"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                >
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <Button className="w-full" size="lg" onClick={search} disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="animate-spin" /> Searching…
                </>
              ) : (
                <>
                  <Search /> Search flights
                </>
              )}
            </Button>

            {error && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}
          </CardContent>
        </Card>

        {data && (
          <div className="mt-6 space-y-3">
            <div className="flex items-baseline justify-between px-1">
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">
                  {data.count} flight{data.count === 1 ? "" : "s"}
                </span>{" "}
                · {data.query.from_airport} → {data.query.to_airport} ·{" "}
                {data.query.date}
              </p>
              {data.cheapest_price != null && (
                <p className="text-sm font-semibold text-primary">
                  from {symbol}
                  {data.cheapest_price}
                </p>
              )}
            </div>

            {data.flights.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center text-sm text-muted-foreground">
                  No flights found. Try different dates or a nonstop search.
                </CardContent>
              </Card>
            ) : (
              data.flights.map((f, i) => (
                <FlightCard
                  key={i}
                  flight={f}
                  symbol={symbol}
                  trip={trip}
                  isCheapest={f.price === data.cheapest_price}
                  bookUrl={data.book_url}
                />
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FlightCard({
  flight,
  symbol,
  trip,
  isCheapest,
  bookUrl,
}: {
  flight: Flight;
  symbol: string;
  trip: string;
  isCheapest: boolean;
  bookUrl: string;
}) {
  const first = flight.segments[0];
  const last = flight.segments[flight.segments.length - 1];
  const dep = fmtTime(first.departure);
  const arr = fmtTime(last.arrival);
  const airlines = flight.airline_names.join(", ") || "Unknown airline";
  const stopsLabel =
    flight.stops === 0 ? "Nonstop" : flight.stops === 1 ? "1 stop" : `${flight.stops} stops`;
  const totalMin = flight.segments.reduce(
    (s, x) => s + (x.duration_minutes || 0),
    0
  );

  let eco = null;
  if (
    flight.carbon_emission_grams &&
    flight.carbon_typical_grams &&
    flight.carbon_emission_grams < flight.carbon_typical_grams
  ) {
    const pct = Math.round(
      (1 - flight.carbon_emission_grams / flight.carbon_typical_grams) * 100
    );
    if (pct > 0) {
      eco = (
        <Badge variant="success">
          <Leaf className="mr-1 h-3 w-3" /> {pct}% less CO₂
        </Badge>
      );
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-[88px]">
          <div className="text-2xl font-bold tracking-tight">
            {symbol}
            {flight.price}
          </div>
          <div className="text-xs text-muted-foreground">
            {trip === "round-trip" ? "round trip" : "one-way"}
          </div>
          {isCheapest && (
            <Badge variant="success" className="mt-1.5">
              Best
            </Badge>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className="mb-3 text-sm font-medium">{airlines}</p>
          {flight.segments.map((s, i) => {
            const d = fmtTime(s.departure);
            const a = fmtTime(s.arrival);
            return (
              <div key={i} className="mb-2 flex items-center gap-2">
                <div className="w-12">
                  <div className="text-sm font-semibold">{d.time}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {s.from_airport.code}
                  </div>
                </div>
                <div className="relative h-px flex-1 bg-border">
                  <Plane className="absolute -top-2 right-0 h-3.5 w-3.5 rotate-90 text-muted-foreground" />
                </div>
                <div className="w-12 text-right">
                  <div className="text-sm font-semibold">{a.time}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {s.to_airport.code}
                  </div>
                </div>
                <div className="w-12 text-right text-[11px] text-muted-foreground">
                  {s.duration}
                </div>
              </div>
            );
          })}
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant={flight.stops === 0 ? "success" : "outline"}>
              {stopsLabel}
            </Badge>
            <span>· {fmtDuration(totalMin)}</span>
            {eco}
          </div>
        </div>

        <Button
          size="sm"
          variant="default"
          className="w-full shrink-0 sm:w-auto"
          onClick={() => window.open(bookUrl, "_blank", "noopener,noreferrer")}
        >
          Book <ExternalLink className="h-3.5 w-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}
