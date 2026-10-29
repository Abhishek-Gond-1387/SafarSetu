# SafarSetu Architecture — Multimodal Public Transport Engine

## 1. System Overview

SafarSetu is a multimodal journey assistant for Delhi/NCR commuters and tourists.
- **Stage 1**: Implemented timetable-aware public transit routing, multi-objective ranking, and graph construction using genuine Delhi DTC/DIMTS GTFS data (`mdb-1262`).
- **Stage 2A**: Integrates official Delhi Open Transit Data (OTD) GTFS-Realtime live vehicle positions (`VehiclePositions.pb`) via lifecycle-managed asynchronous background polling.

```
                              ┌───────────────────────────────────┐
                              │    FastAPI Application Layer       │
                              │  /health, /stops, /routes/plan    │
                              │  /realtime/status, /vehicles      │
                              └─────────────────┬─────────────────┘
                                                │
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         │                                      │                                      │
┌────────▼────────────────────┐   ┌─────────────▼───────────────┐        ┌─────────────▼─────────────┐
│   Transit Repository        │   │   Multimodal Graph Engine   │        │ Realtime Vehicle Repo     │
│  - In-memory Stop Index     │   │  - Scheduled Trip Edges     │        │  - Thread-Safe Bounded    │
│  - Haversine Spatial Grid   │   │  - Timetable Index          │        │    In-Memory Cache        │
│  - Route & Trip Metadata    │   │  - Walking Transfer Links   │        │  - Dynamic Staleness      │
└────────▲────────────────────┘   └─────────────▲───────────────┘        └─────────────▲─────────────┘
         │                                      │                                      │
┌────────┴────────────────────┐   ┌─────────────┴───────────────┐        ┌─────────────┴─────────────┐
│   GTFS Ingestion Pipeline   │   │   Time-Dependent Router     │        │ OTD Realtime Poller       │
│  - CSV parsing & validation │   │  - Earliest Arrival         │        │  - Background Lifespan    │
│  - 24:00+ time normalization│   │  - Transfer Minimization    │        │  - httpx Async Client     │
│  - Calendar date matching   │   │  - Multi-objective Ranker   │        │  - Backoff & Key Masking  │
└────────▲────────────────────┘   └─────────────────────────────┘        └─────────────▲─────────────┘
         │                                                                             │
┌────────┴────────────────────┐                                          ┌─────────────┴─────────────┐
│ Genuine GTFS Archive        │                                          │ Delhi OTD Realtime API    │
│ (e.g. mdb-1262 / DTC Delhi) │                                          │ (/VehiclePositions.pb)    │
└─────────────────────────────┘                                          └───────────────────────────┘
```

---

## 2. Real-Time Engine Architecture (Stage 2A)

### 2.1 Poller Lifecycle & Resilience
- **Lifespan-Managed**: `OTDRealtimePoller` starts on FastAPI application startup if `OTD_REALTIME_ENABLED=true` and credentials are configured. Shuts down cleanly on application termination by cancelling the asyncio task and closing HTTP connections.
- **Credential Protection**: The API key is stored exclusively on the backend in `OTD_REALTIME_API_KEY`. It is never returned in HTTP responses, logged to console/files, or exposed in exceptions. Query strings are stripped using `sanitize_url()`.
- **Bounded Exponential Backoff**: When network errors, timeouts, or HTTP 429/5xx errors occur, the polling interval backs off progressively (15s → 22.5s → 33.7s → 50s → max 120s) to avoid hammering the upstream server.
- **Worker Scaling Note**: In multi-process production deployments (e.g. multiple Uvicorn workers), each worker would spawn its own poller loop. For production clustering, polling should be isolated into a single dedicated scheduler worker or backed by Redis.

### 2.2 Protobuf Parsing & Validation
- **Field Presence Semantics**: Respects protobuf `HasField()` semantics. Optional telemetry fields (speed, bearing, timestamp) remain `None` if unpopulated.
- **Coordinate Bounds Checking**: Validates latitude $[-90.0, 90.0]$ and longitude $[-180.0, 180.0]$. Automatically rejects null island coordinates $(0, 0)$ resulting from GPS hardware initialization errors.
- **Deduplication**: If a vehicle entity appears multiple times within a single payload, the record with the newer observation timestamp is retained.

### 2.3 Truthful Static GTFS Association
- **Trip Matching**: If reported `trip_id` exists in static `dataset.trips`:
  - `is_trip_matched = True`
  - Route details (`route_short_name`, `route_long_name`) are cross-referenced from `dataset.routes`.
  - Next stop identification: if `current_stop_sequence` is reported, SafarSetu looks up the scheduled stop in `dataset.stop_times` and labels it as **scheduled next stop**.
- **Unassociated Fallback**: If reported `trip_id` or `route_id` does not match the static feed (e.g., due to operational dispatch rotations or historical feed drift):
  - The vehicle is preserved and exposed with `association_status: "unassociated"`.
  - Coordinates, speed, and bearing are displayed truthfully.
  - **No fake routes, destinations, or ETAs are invented**.

### 2.4 In-Memory Vehicle Cache
- **Thread Safety**: Protected via `threading.Lock` to support concurrent asynchronous readers and poller writers.
- **Bounded Eviction**: Limited to `OTD_REALTIME_MAX_CACHE_SIZE` (default 10,000 vehicles). Oldest observations are evicted first if capacity is exceeded.
- **Dynamic Staleness**: Observations older than `OTD_REALTIME_STALE_THRESHOLD_SECONDS` (default 300s) are dynamically flagged with `is_stale: true`.

---

## 3. Ingestion & Validation Pipeline (Stage 1)

1. **Archive Checksum Verification**: Validates SHA-256 integrity against metadata records.
2. **Schema & Header Conformance**: Ensures required GTFS files are present with standard column names.
3. **Foreign Key Integrity**: Rejects orphan records (`stop_times` referencing nonexistent `trip_id` or `stop_id`).
4. **Sequence Monotonicity**: Verifies that `stop_sequence` values within every trip are strictly increasing.
5. **Time Beyond 24:00 Normalization**: Correctly parses GTFS overnight timestamps (e.g. `24:15:00` = 87,300 seconds from midnight).
6. **Geographic Coordinate Validation**: Flags stops with latitude/longitude outside the Delhi/NCR bounding box (`[27.8, 29.0]` N, `[76.5, 77.9]` E).
7. **Service Calendar & Freshness Warning**: Computes whether the active date range has elapsed and surfaces data freshness warnings.

---

## 4. Graph Model & Timetable Routing

- **Nodes**: Physical stops and stations (`stop_id`, WGS-84 coordinates, stop name).
- **Scheduled Transit Edges**: Directed connections between consecutive stops of a validated trip.
- **Walking Transfer Links**: Straight-line Haversine estimates (`distance_type: "straight_line"`). Estimated walking speed: `1.2 m/s` (~4.3 km/h).
- **Time-Dependent Forward Search**: Evaluates candidate departures starting from requested `departure_time` (in seconds from midnight), enforcing calendar service filters and transfer buffers.

---

## 5. AI Agent Structured Tool Interface

The backend exposes clean structured tools for the future AI agent reasoning layer:

| Tool Name | Endpoint / Function | Description |
|---|---|---|
| `get_realtime_status` | `GET /api/v1/realtime/status` | Verifies whether live bus telemetry is currently active and fresh. |
| `get_nearby_vehicles` | `GET /api/v1/realtime/vehicles` | Finds live vehicles operating within geographic bounds or route filters. |
| `plan_journey` | `POST /api/v1/routes/plan` | Returns scheduled feasible multimodal itineraries with transfer counts. |
| `compare_routes` | `POST /api/v1/routes/compare` | Compares journey alternatives on duration, walking, and transfers. |

---

## 6. Stage 3 Routing Engine Audit & Correctness Hardening

### 6.1 Audit Findings & Architectural Defects Resolved
1. **Disabled Walking Transfers in Delhi**:
   - *Previous defect*: `len(dataset.stops) <= 5000` disabled all pedestrian walking transfers because Delhi has 6,342 stops.
   - *Solution*: Implemented an $O(N)$ spatial grid hash partition (0.005° cells ~ 500m). Synthesizes 19,158 authentic walking links across Delhi bus stops in 1.1 seconds.
2. **Priority Queue Tuple Comparison Crash Risk**:
   - *Previous defect*: `(curr_time, num_transfers, curr_stop, curr_trip_id, legs)` crashed if the first four keys tied, because `JourneyLeg` lacks `<` ordering.
   - *Solution*: Added an integer sequence counter (`itertools.count()`) as a deterministic tiebreaker.
3. **Suboptimal Pruning & Branch Mutation Bug**:
   - *Previous defect*: In-place mutation of `last_leg` during path expansion corrupted sibling search branches sharing parent legs.
   - *Solution*: Full immutability in leg aggregation (`JourneyLeg` replacement without in-place mutation).
4. **Fastest Ranking Metric Flaw**:
   - *Previous defect*: Ranked fastest routes by transit leg duration alone, ignoring initial wait time between user request and departure.
   - *Solution*: Aligned fastest ranking with total elapsed travel time (`total_duration_seconds + initial_wait_seconds`).
5. **Freshness & Service Expiration Distinctions**:
   - API endpoints explicitly differentiate:
     - Source service-calendar validity (`calendar_validity_note`)
     - Historical feed expiration vs current operating date
     - Real-time polling status vs verified live tracking (`live_tracking_verified`)

### 6.2 Performance Benchmarks on Genuine Delhi Dataset (mdb-1262)
- **Stops Ingested**: 6,342 authentic stops
- **Routes Ingested**: 2,964 routes
- **Trips Ingested**: 10,000 trips (benchmark slice) / 78,515 trips total
- **Graph Construction**: 1.105 seconds (380,142 transit edges + 19,158 spatial walking edges)
- **Direct Journey Latency**: 13.49 ms
- **Cross-Network Transfer Latency**: 5.39 ms
- **Off-Peak Journey Latency**: 7.92 ms
- **Process Memory**: 232.0 MB

| `search_stops` | `GET /api/v1/stops` | Searches authentic bus stops by name or terminal code. |
| `get_nearby_stops` | `GET /api/v1/stops/nearby` | Finds stops near coordinates with explicit straight-line distance notes. |

---

## 7. Stage 4 — Supabase User Database & Authentication Architecture

### 7.1 Architecture & Separation of Concerns
SafarSetu maintains a clean, strict separation between **public transit data** and **personal user data**:
- **Transit Data**: Static Delhi GTFS schedules, in-memory timetable graphs, and real-time vehicle positions remain stateless, high-performance in-memory structures.
- **User Data**: Personal data (profiles, commuter preferences, bookmarked journeys, search history, and feedback) persists securely in **Supabase PostgreSQL** protected by **Row Level Security (RLS)**.

```
                      ┌───────────────────────────────────────┐
                      │    Client (Web / Mobile Frontend)     │
                      │  - Supabase Auth (Sign-in / Sign-up)  │
                      │  - Holds JWT access_token             │
                      └──────────────────┬────────────────────┘
                                         │ Bearer <token>
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    FastAPI Application Layer          │
                      │  - get_current_user (JWT verification)│
                      │  - Validates stop IDs against GTFS    │
                      └──────────┬─────────────────┬──────────┘
                                 │                 │
                ┌────────────────▼┐               ┌▼────────────────────────┐
                │ Transit Engine  │               │ Supabase PostgreSQL DB  │
                │ (In-memory)     │               │ (Row Level Security)    │
                │ - Stops, Trips  │               │ - profiles              │
                │ - Graph Router  │               │ - user_preferences     │
                │ - Realtime Repo │               │ - saved_journeys        │
                └─────────────────┘               │ - recent_searches       │
                                                  │ - user_feedback         │
                                                  └─────────────────────────┘
```

### 7.2 Cryptographic Token Verification
- Handled in [`backend/app/core/auth.py`](file:///d:/SafarSetu/backend/app/core/auth.py).
- Verifies JWT signatures using the project's `SUPABASE_JWT_SECRET` (`HS256`).
- Validates expiration (`exp`), audience (`authenticated`), and extracts the verified subject claim (`sub`) as `AuthenticatedUser.id` (UUID).
- **Security Rule**: The application *never* trusts client-supplied `user_id` parameters. All database queries strictly bind to the verified `auth.uid` extracted from the token.

### 7.3 Row Level Security (RLS) Policies
- All user tables have RLS enabled.
- Default policies mandate `auth.uid() = user_id` (or `auth.uid() = id` for `profiles`) across `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.
- Prevents cross-user data leakage and tampering (verified in automated tests).
- Automated database triggers handle:
  - `handle_updated_at`: Automatically sets `updated_at` timestamps on row updates.
  - `handle_new_user`: Auto-creates default profile and preferences on `auth.users` insert.
  - `enforce_recent_searches_retention`: Enforces 20-item rolling retention cap on recent searches.

