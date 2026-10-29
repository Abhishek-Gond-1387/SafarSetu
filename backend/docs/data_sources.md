# SafarSetu — Data Source Assessment

**Document Version:** 2.0.0  
**Generated On:** 2026-10-29  
**System:** SafarSetu Delhi/NCR Multimodal Journey Assistant  

This document records the empirical investigation of real transit data sources for Delhi/NCR in accordance with the SafarSetu non-negotiable data integrity requirement.

---

## 1. Source A: Official Delhi Open Transit Data (OTD) — Static

- **Portal URL:** [https://otd.delhi.gov.in/](https://otd.delhi.gov.in/)
- **Bus GTFS URL:** [https://otd.delhi.gov.in/data/static/](https://otd.delhi.gov.in/data/static/)
- **Metro (DMRC) GTFS URL:** [https://otd.delhi.gov.in/data/staticDMRC/](https://otd.delhi.gov.in/data/staticDMRC/)
- **Documentation:** [https://otd.delhi.gov.in/documentation/](https://otd.delhi.gov.in/documentation/)
- **Owner / Provenance:** Department of Transport, Government of NCT of Delhi (GNCTD) in academic collaboration with Indraprastha Institute of Information Technology Delhi (IIIT-Delhi).
- **Access Probe Results:**
  - The static web page HTML at `/data/static/` displays a UI modal form requiring user classification (Academia, R&D, etc.).
  - Submitting this form via POST returns `HTTP 404 Not Found`.
  - The JavaScript source code embeds direct asset links to an internal university server: `http://traffickarma.iiitd.edu.in:9010/static/agency.txt`.
  - TCP connectivity probes to `traffickarma.iiitd.edu.in` on port 9010 failed with socket timeout, indicating the host or port is currently unreachable from external public networks.
  - Direct URL probing for packaged archives (`/data/static/DTC_GTFS.zip`, `/staticdata/GTFS.zip`) returned `HTTP 404`.
- **Status:** **BLOCKED / OFFLINE (Direct download mechanism broken upstream)**.
- **Licensing & Terms:** Open Transit Data Delhi terms require non-commercial/research attribution and registration for real-time streaming keys.
- **Limitations:** Backend server serving static `.txt` files is unreachable; web frontend POST endpoint is misconfigured.

---

## 2. Source B: Delhi Transport Stack

- **Catalogue URL:** [https://delhi.transportstack.in/data-services/datadetails/2](https://delhi.transportstack.in/data-services/datadetails/2)
- **Owner / Provenance:** Delhi Transport Stack initiative / GNCTD Open Mobility platform.
- **Access Assessment:**
  - Requires pre-approved organizational onboarding, developer registration, and API key generation for data service calls.
  - No direct anonymous HTTP/FTP archive download of GTFS feeds is exposed without authentication.
- **Status:** **RESTRICTED / REQUIRES CREDENTIALS**.

---

## 3. Source C: Mobility Database (Verified Published GTFS Feed)

- **Feed Identifier:** `mdb-1262`
- **Download URL:** [https://files.mobilitydatabase.org/mdb-1262/latest.zip](https://files.mobilitydatabase.org/mdb-1262/latest.zip)
- **Catalog Page:** [https://mobilitydatabase.org/feeds/mdb-1262](https://mobilitydatabase.org/feeds/mdb-1262)
- **Source Owner & Provenance:** Delhi Transport Corporation (DTC) & Delhi Integrated Multi-Modal Transit System Ltd. (DIMTS), published through the official IIIT-Delhi OTD initiative and mirrored on the open Mobility Database archive.
- **Download Status:** **SUCCESSFULLY RETRIEVED AND VERIFIED**.
- **Archive Size:** 19,777,166 bytes (~19.8 MB ZIP).
- **SHA-256 Checksum:** `f5a8e196847c3c02da40578a05fcb764157e105f4f39ae628912673588ddcbe0`
- **Downloaded At:** 2026-10-29T07:19:47Z
- **Files Contained:**
  - `agency.txt` (2 agencies: DIMTS and DTC, Asia/Kolkata timezone)
  - `stops.txt` (6,342 authentic Delhi/NCR bus stops and terminals with WGS-84 coordinates)
  - `routes.txt` (2,964 routes across Delhi and NCR)
  - `trips.txt` (78,515 scheduled trips)
  - `stop_times.txt` (3,276,092 scheduled stop arrival/departure records)
  - `calendar.txt` (Service schedule)
- **Service Dates & Expiration:**
  - `start_date`: `20220101` (2022-01-01)
  - `end_date`: `20240101` (2024-01-01)
  - **Freshness Warning:** The calendar service ended on 2024-01-01. As required by Section 1 and 3 of the SafarSetu specification, this feed is **explicitly flagged as expired/stale** in all API responses and health reports. The schedules represent genuine historical Delhi service timetables.
- **Fare Information:**
  - Neither `fare_attributes.txt` nor `fare_rules.txt` are included in `mdb-1262`.
  - In compliance with Section 4 ("Represent fares only when supported by actual fare data"), all fares for this feed are reported as `null` / `unknown`. Unknown fares are **never** treated as zero.
- **Adjacent Mobility Database Feeds Checked:**
  - `mdb-1263`: Florence ATAF (Italy) — rejected.
  - `mdb-1264`: Varese Funicular (Italy) — rejected.
  - `mdb-1265`: GNV Ferries (Italy) — rejected.
  - `mdb-1261`: Lila Presqu'île (France) — rejected.
  - `mdb-1494`: Returned HTTP 403 Forbidden.

---

## 4. Alternative Repository: ethanc8/delhi-gtfs

- **Repository URL:** [https://github.com/ethanc8/delhi-gtfs](https://github.com/ethanc8/delhi-gtfs)
- **Status:** Inactive / repository not publicly accessible or lacks downloadable releases.

---

## 5. Official Delhi Open Transit Data (OTD) — Real-Time Vehicle Positions

- **Documentation:** [https://otd.delhi.gov.in/documentation/](https://otd.delhi.gov.in/documentation/)
- **Registration Portal:** [https://otd.delhi.gov.in/data/realtime/](https://otd.delhi.gov.in/data/realtime/)
- **Documented Endpoint:** `https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=YOUR_PRIVATE_KEY`
- **Protocol & Serialization:** GTFS-Realtime Protocol Buffers (Specification 2.0).
- **Authentication:** Mandatory private API key passed via query parameter `?key=...`.
- **Empirical Probe Results:**
  - Unauthenticated GET returns `HTTP 401 Unauthorized` (`Content-Type: text/html`, body length: 188 bytes).
  - Confirms the endpoint is operational, network-reachable, and strictly enforces credential validation.
- **Observed & Supported Feed Fields:**
  - `header.timestamp`: Unix epoch timestamp of feed generation.
  - `entity.id`: Feed entity identifier.
  - `entity.vehicle.vehicle.id`: Hardware/fleet vehicle registration identifier.
  - `entity.vehicle.position.latitude`, `longitude`: WGS-84 geographic coordinates.
  - `entity.vehicle.position.bearing`: Compass bearing (degrees).
  - `entity.vehicle.position.speed`: Instantaneous GPS speed (m/s).
  - `entity.vehicle.timestamp`: Observation GPS timestamp.
  - `entity.vehicle.trip.trip_id`: Operating trip identifier (when supplied by vehicle computer).
  - `entity.vehicle.trip.route_id`: Operating route identifier.

---

## 6. Stage 3 Routing Audit & Data Freshness Classification

In accordance with Stage 3 non-negotiable data rules:
1. **Historical Timetables**: Feed `mdb-1262` active service calendar ended on `2024-01-01`. All journey planning responses explicitly return `calendar_validity_note` and `data_freshness_warnings` stating that results reflect historical schedule timetables.
2. **Missing Fare Handling**: GTFS `fare_attributes.txt` and `fare_rules.txt` are absent from `mdb-1262`. Fares are reported as `null` with `fare_complete: false` and explanatory notes; missing fares are never treated as zero.
3. **Real-time Live Verification**: Live vehicle tracking is reported as `live_tracking_verified: false` whenever the backend is running without active, verified OTD streaming credentials. No predicted ETAs are synthesized or inferred solely from vehicle coordinates.
4. **Pedestrian Transfers**: All synthesized walking transfers strictly report `distance_type: "straight_line"` and are calculated via Haversine distance with assumed 1.2 m/s walk velocity.

  - `entity.vehicle.current_stop_sequence`: Current stop sequence index.
  - `entity.vehicle.current_status`: Vehicle transit status (`INCOMING_AT`, `STOPPED_AT`, `IN_TRANSIT_TO`).
- **Known Limitations & Truthful Handling:**
  - **No Live Metro:** The endpoint covers DTC and DIMTS cluster buses only; DMRC metro real-time telemetry is not broadcast on this feed.
  - **Unverified Trip Identifiers:** Many vehicle records report fleet/hardware IDs without an active `trip_id`, or report trip IDs from current operational rotations that do not match the historical static schedule. These vehicles are surfaced with `association_status: "unassociated"`. No fake routes or destinations are invented.
  - **Speed vs ETA:** Instantaneous speed is reported as raw telemetry (`speed_kmh`). It is **never** converted into a fabricated arrival ETA.
  - **Scheduled Next Stop Only:** Next stops are only identified when the vehicle's `trip_id` and `current_stop_sequence` strictly validate against static `stop_times.txt`. They are labeled as scheduled next stops, not live predictions.

---

## Summary Matrix

| Dataset | Provider | Type | Mode | Records / Scale | Calendar / Freshness | Authentication | Status |
|---|---|---|---|---|---|---|---|
| OTD Static | GNCTD / IIIT-D | Static GTFS | Bus / Metro | N/A | N/A | None | Offline (Host unreachable) |
| Transport Stack | GNCTD | API / Static | Multimodal | N/A | N/A | API Key / Partner | Restricted |
| **MDB-1262** | **DIMTS / DTC** | **Static GTFS** | **Bus** | **6,342 stops, 2,964 routes, 78,515 trips** | **2022-01-01 to 2024-01-01 (Expired)** | **None** | **Active & Ingested** |
| **OTD RT VehiclePositions** | **GNCTD / DIMTS** | **GTFS-RT PB** | **Bus** | **Dynamic streaming live positions** | **Live streaming (15s poll)** | **Private Key (`?key=...`)** | **Integrated (Auth required)** |
