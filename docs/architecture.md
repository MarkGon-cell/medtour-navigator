# MedTour — Redesign Specification

**Status:** proposal, awaiting sign-off
**Scope of this document:** the target identity, architecture and boundaries of MedTour after the redesign.
**Companion docs:** [`api_endpoints.md`](./api_endpoints.md) (as-is → target endpoint matrix), [`database_schema.md`](./database_schema.md) (tables kept / changed / retired), [`project_progress.md`](./project_progress.md) (phased build plan).

---

## 1. Positioning

> **MedTour is the Emergency Medical Passport & Urgent Triage Gateway for foreigners and travellers in India.**
>
> It is a **patient-side bridge** between a panicked, non-native speaker and the local healthcare ecosystem. It points the patient to the right door. It does not run the hospital, and it does not dispatch ambulances.

### What this means

| MedTour **is** | MedTour **is not** |
| --- | --- |
| An instant emergency toolkit that works as a guest in one tap | A booking website with a signup wall |
| A `tel:112` trigger + readable GPS address + ride-hail deep link | A backend row with `status: PENDING` that implies help is coming |
| A translator that speaks to the driver / reception desk | A full UI-string localisation platform |
| A pointer to the nearest emergency-capable door | A hospital information system |
| A walk-in appointment log + insurance paperwork | An elective medical-tourism marketplace |
| Fed by OpenStreetMap / Overpass + a verified national directory | A system that requires hospitals to adopt our dashboard |

### Why the current architecture fails this

The identity crisis has concrete, verifiable symptoms in the code today:

1. **The SOS lies to the user.** `src/routes/index.tsx:91-120` POSTs `/emergency/sos` and toasts
   *"🚨 Emergency SOS Sent! Ambulance dispatch logged in backend."*; `src/routes/dashboard.tsx` toasts *"Help is on the way!"*.
   The backend (`backend/app/api/emergency.py:49-150`) inserts a `sos_alerts` row with `status="PENDING"`, writes a JSON file to
   `backend/sos_logs/`, and returns `"simulated": true, "eta_minutes": 8`. **No call is placed, no dispatcher is paged.**
   A tourist in anaphylaxis reading "help is on the way" is worse off than one who never pressed the button.
2. **Nothing is reachable in a crisis without ceremony.** The landing page's primary CTAs are `Get Started → /register` and `View Dashboard`.
   `src/components/site/Navbar.tsx` shows *Sign in / Get Started* unconditionally.
3. **There is no route-level auth guard anywhere** (no `beforeLoad`, no `redirect`) — auth is currently pure friction: it gates
   nothing except `/appointments` (which reacts to `401` by bouncing to `/login`, `src/routes/appointments.tsx:96-99`).
   So login buys the user almost nothing while costing them the golden 60 seconds.
4. **Scope is spread across five products:** medical tourism, elective scheduling, hospital ERP-ish dashboards, emergency SOS, and admin telematics.

---

## 2. Design principles

1. **The Golden 60 Seconds.** Every emergency affordance is reachable from `/` in zero taps, requires no identity, and never waits on the network before showing the user something actionable.
2. **Never fake dispatch.** If we did not place a call or reach a gateway, the UI says so. Copy is written by someone who assumes the reader is dying.
3. **Guest-first, account-after-care.** Local storage is the default store. An account is offered *after* care is located, and only to sync appointments across devices.
4. **Point, don't manage.** We reference external systems (phone, OSM, Uber/Ola, the hospital's own switchboard). We do not build parallel ones.
5. **Honest paper.** Anything we call a "receipt" is clearly a *patient copy*, never a forged hospital bill.
6. **Offline-tolerant.** Degraded network must degrade features, not block the emergency path.

---

## 3. Target information architecture

| Route | Role after redesign | Auth |
| --- | --- | --- |
| `/` | **Emergency toolkit home.** GPS card, big SOS action, nearest-3 emergency rooms, flashcards, then (below the fold) urgent-care entry. | guest |
| `/emergency` | Full-screen SOS sheet (also openable as a modal from `/`). `tel:112`, readable address, top-3, ride-hail, contact SMS. | guest |
| `/flashcards` | "Show the Driver / Desk" full-screen cards, language picker, symptom + allergy cards. | guest |
| `/hospitals` | Nearby directory (Overpass + directory merge), search, radius, emergency-only. | guest |
| `/hospital-details/$id` | Facility profile: phones, hours, bed/accreditation data, navigate, call. | guest |
| `/appointments` | Three tabs: **Upcoming / Completed / Cancelled**. Local records + optional sync. | guest, optional sync |
| `/dashboard` | Retitled **"Symptom triage"** — AI first-aid guidance, no SOS duplication. | guest |
| `/results` | Triage output (unchanged in role). | guest |
| `/login`, `/register` | **Optional post-care signup.** Zero inbound links from nav or critical flows; reachable by direct URL and by a single "sync across devices" prompt *after* a booking. | public |
| `/admin` | **Deprecated.** Replaced by nothing in Phase 1; see §7. | — |

**Nav after redesign:** Home · Emergency · Hospitals · Flashcards · Appointments. No "Sign in" button in the primary nav.

---

## 4. Pillar 1 — Zero-friction emergency flow

### 4.1 The SOS sheet (`/emergency`, also modal from `/`)

Opens on tap of a single persistent red button. Contents, in order of priority:

**A. Call 112 — the primary action, always first, never disabled**

```html
<a href="tel:112" class="...giant...">Call 112 — All-India Emergency</a>
<a href="tel:108" class="...">Call 108 — Ambulance</a>
```

`tel:` requires no network beyond the carrier, no geolocation, no permission, and no backend. It must render and be tappable **before** any async work resolves. Secondary: `tel:108` (state ambulance service).

**B. Read-aloud location — large typography, must never block**

- Primary: `navigator.geolocation.getCurrentPosition` → coordinates in **very large monospace text**.
- Then, non-blocking, a reverse geocode via Nominatim
  (`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=..&lon=..&zoom=18`) fills in a street address.
- **If the geocode fails or times out (8 s), coordinates stay on screen.** The address line is a bonus; the numbers are the product.
- One tap copies the whole block to clipboard; a second shows the raw Google Maps pin URL for pasting into WhatsApp.
- If permission is denied: show `Location unavailable — say the name of your hotel/landmark` plus the current city from `sessionStorage`.

**C. Top 3 emergency-capable centres within ~10 km** — see §5.

Each card: name, distance, `emergency_phone` (`tel:` link), 24/7 badge, and ride-hail buttons (§4.3).

**D. Show-the-Driver flashcard** — see §4.4.

**E. Notify my emergency contact** — *optional*, only if the traveller saved one; see §4.5.

### 4.2 Copy rules for the SOS surface

- Never: *"SOS sent"*, *"Help is on the way"*, *"Ambulance dispatched"*, *"ETA 8 minutes"*.
- Do: *"Opening your phone dialler for 112"*, *"Read this address aloud"*, *"Show this to a taxi driver"*.
- If we ever gain a real gateway integration, the wording changes *then* — with the provider named on screen.

### 4.3 Ride-hail deep links

Per-destination buttons on each top-3 card. Targets to implement and **verify on a real device in Phase 1** (URL schemes drift and differ per platform; each needs a fallback):

| Provider | Candidate target | Fallback if it does not open |
| --- | --- | --- |
| Uber | `https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff_latitude={lat}&dropoff_longitude={lng}&dropoff_name={name}` | Google Maps directions |
| Ola | `https://book.olacabs.com/?lat={plat}&lng={plon}&drop_lat={dlat}&drop_lng={dlon}&category=auto` | Google Maps directions |
| Google Maps (always works) | `https://www.google.com/maps/dir/?api=1&destination={lat},{lng}` | — |

Both pickup coordinates come from the GPS fix we already hold — no second permission prompt.
Treat the Uber/Ola formats as **hypotheses to confirm**, not settled fact; if either fails on-device in Phase 1, ship Google Maps + `tel:` to the hospital and note it here.

### 4.4 "Show the Driver / Desk" flashcards

A full-screen, high-contrast modal with oversized text, a language picker, and next/prev paging.

Default card text (English + local language side by side):

> **PLEASE TAKE ME TO THE NEAREST EMERGENCY ROOM IMMEDIATELY.**
> **I AM A TOURIST AND DO NOT SPEAK THE LOCAL LANGUAGE.**

Languages for Phase 1: **Hindi, Marathi, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Punjabi, English.**
The current i18n module (`src/lib/i18n.tsx`, `src/i18n/{en,hi}.json`) covers only `en`/`hi` and — importantly — **`I18nProvider` is never mounted**, so it is dead code today. Flashcards should ship as their own small content module (`src/lib/flashcards/*.ts`) rather than extending that dormant provider; revisit unification later.

Card deck beyond the driver card: *I have food poisoning / severe pain / fever / a cut*, *I am allergic to …*, *I need my prescription refilled*, *Here is my passport and insurance*.

### 4.5 Emergency-contact dispatch (optional, honest)

If the traveller saved a companion/embassy number, one tap produces a pre-composed message they send themselves:

- Preferred: `https://wa.me/?text={urlencoded}` — **the user presses send**; no Twilio, no cost, no backend.
- Secondary: `sms:{number}?&body={urlencoded}`.
- Content: Google Maps pin, coordinates, timestamp, chosen hospital name.

This is deliberately *assisted manual send*, not silent server-side dispatch: it works offline-ish, needs no credentials, and cannot silently fail while implying success.

---

## 5. Pillar 2 — Hospital discovery: Overpass + verified directory

### 5.0 Data reality (measured — read this first)

The spec originally assumed the local directory was a rich, verified facility
record that Overpass would merely supplement. **Measurement disproved that.**

Probed on 2026-10-09 against the live `medtour_db`
(`backend/scripts/probe_hospital_data.py`):

| Metric | Value |
| --- | --- |
| Rows in CSV source (`hospital_directory.csv`) | 30,273 |
| Rows in the live `hospitals` table | **10,607** (35% — the import is partial) |
| States in CSV | 36 |
| States in DB | **19** — missing Uttar Pradesh (3,158 rows), Tamil Nadu (2,399), Rajasthan, Punjab, West Bengal, Odisha, Telangana |
| Delhi / NCT | **0 rows in the CSV itself** |
| `emergency_available = true` | **1 facility, nationwide** |
| `emergency_phone` usable | 94 rows (0.9%) |
| `ambulance_phone` usable | 13 rows |
| `accreditation` usable | **0 rows** |
| `registration_number` usable | **0 rows** |
| `total_beds > 0` | 24 rows |
| `telephone` usable | 674 rows (6.4%) |
| `Foreign_pcare` (CSV) | junk — 30,271 rows are `'0'`; the other 2 hold a phone number |

Consequences, all reflected in the implementation:

1. **`emergency=true` ranks, it does not filter.** Hard-filtering on
   `emergency_available` returns a single facility for all of India. The
   endpoint now sorts emergency-capable and reachable facilities first and
   keeps the remainder, so the list is never empty; every row still carries a
   truthful `emergency_available` so the UI never badges an ER without
   evidence. Verified: `sort=emergency&limit=3` returns 3 rows in Mumbai,
   `sort=distance` and `sort=emergency` return the same 635 rows for a 10 km
   radius — nothing is lost by ranking instead of filtering.
2. **The directory cannot answer "is this an emergency room", "what is the
   ER number", or "are they accredited".** Those must come from **Overpass/
   OSM tags** (`emergency=yes`, `opening_hours=24/7`, `contact:phone`).
   Overpass is therefore the primary source for *capability and contact*, not
   merely geography.
3. **The directory's real value is coverage** — 10,607 named points with
   address and coordinates across 19 states, dense in Maharashtra/Gujarat/
   Karnataka and absent across a third of the country. It is a *findability*
   index, not a *verification* record. Marketing copy must stop claiming
   "500+ verified hospitals" and credential-checking until that is true.
4. **Re-importing the full CSV is a P0 gap** (see `project_progress.md`).
   `scripts/import_hospitals.py` issues `DROP TABLE ... CASCADE` on
   `appointments` first, so it is destructive and must be run deliberately.
5. **Badge policy — show only what Overpass can prove** (decided
   2026-10-09). Never render a capability claim the data cannot back:

   | Claim | Allowed source | Verdict |
   | --- | --- | --- |
   | `24/7` / `Open Now` | OSM `opening_hours`, compared against IST | ✅ show when present, omit when absent |
   | `Emergency` / `trauma` | OSM `emergency=yes`, `level` tags | ✅ show when present |
   | Phone / call button | OSM `phone` or `contact:phone`, else directory phone | ✅ show only if it passes the 6-digit dialable test |
   | `English Speaking Staff` | *no source exists* | ❌ **never render** |
   | `Cashless Travel Insurance Desk` | *no source exists* | ❌ **never render** |
   | `GSTIN` / `ICD-10` on receipts | *no source exists* (`registration_number` = 0 rows) | ❌ **omit the row**, never print `'0'` |
   | `500+ verified hospitals` | *not verified* | ❌ soften the copy to what it is: a directory index |

   An absent badge must render as *absence*, not as an unverified yes — the
   emergency flow's whole premise is that it never overstates.

### 5.1 Data sources

**As built** — both providers run server-side in
`backend/app/services/discovery.py`, merged by `GET /hospitals/discover`:

| Source | Role | Key |
| --- | --- | --- |
| **Overpass API** (4 global mirrors, tried in turn) | Emergency capability, `opening_hours`, `contact` tags, plus `emergency_ward_entrance` used to *flag* ER-capable facilities | none |
| **Geoapify Places** (`/v2/places`) | Second source of the same search; steadier, and its terms allow caching/storing results without limit | **API key** (free tier, 3,000/day) |
| **Local `hospitals` table** (from `hospital_directory.csv`) | Named coverage, address, city/state, directions target; always authoritative for *dedupe* | backend |
| Nominatim | Reverse geocode for the read-aloud address | none |

**Both providers are OSM-backed, so pairing them buys availability
redundancy, not coverage diversity.** That is worth stating plainly: if a
place isn't in OpenStreetMap, neither provider will find it. The local table
is what fills that gap today — and why the destructive re-import
(10,607 → 30,273 rows) stays a P0.

**Merge strategy.** The local table is loaded first and wins dedupe; a
provider result is inserted only when it is genuinely new — within 60 m
(same building), within 300 m *and* name-matched, or sharing an
`external_id` all mean "already held". Existing rows are never overwritten.
If every provider fails the endpoint still returns local results with
`degraded: true`, because an emergency flow must not break when a mirror is
down. During the 2026-10-09 probes **all four Overpass mirrors returned
500/504 or timed out**, which is precisely why no single provider is a
single point of failure here.

`GET /hospitals/nearby` deliberately stays local-only: it touches no external
service, so it remains fast (7 ms) and works with no network at all.

### 5.2 Corrected Overpass query

The query in the proposal (`node["amenity"="hospital"](around:...)`) **misses most hospitals**, because OSM maps them as building *ways* and *relations*, not points. Use `nwr` plus `out center`:

```
[out:json][timeout:25];
(
  nwr["amenity"="hospital"](around:{r},{lat},{lon});
  nwr["healthcare"~"hospital|clinic|doctor"](around:{r},{lat},{lon});
  nwr["emergency"="ambulance_station"](around:{r},{lat},{lon});
);
out body center tags;
```

Client rules:

- Send as **POST** with `data=` (GET URLs blow past length limits on large radii).
- `AbortController` with a 20 s cap; cache results in `sessionStorage` keyed by geohash+radius so repeat presses are instant.
- Respect Overpass rate limits: debounce per session, never fire on every pan/zoom.
- **CORS:** Overpass permits cross-origin calls, so this runs entirely in the browser — no key, no proxy, works for guests.

### 5.3 Ranking for "nearest emergency room"

**Overpass candidates:** score = distance, then `amenity=hospital` >
`healthcare=clinic` > `healthcare=doctor`; bonus for `emergency=yes`,
`opening_hours=24/7`, and presence of `phone`/`contact:phone`.
Top 3 shown in the SOS sheet; more on `/hospitals`.

**Local directory candidates** (`GET /hospitals/nearby?sort=emergency`): rank by
1) `emergency_available`, 2) at least one dialable phone, 3) distance. The
directory carries no usable emergency metadata (§5.0), so this ranking is a
weak prior — never a substitute for the Overpass tags.

### 5.4 Performance — fixed and measured

**Was:** `db.query(Hospital).all()` pulled the entire table into Python and ran
the haversine over every row on each request.

**Now:** `backend/app/api/hospitals.py` applies a SQL bounding-box predicate on
the indexed `latitude`/`longitude` columns, then runs the exact haversine only
over candidates.

Measured on 10,607 rows, 10 km radius around Mumbai
(`backend/scripts/benchmark_nearby.py`):

```
full scan + haversine (old)        100.2 ms   scanned=10607  hits=635
bounding box + haversine (new)       7.0 ms   scanned=  685  hits=635
speedup: 14.3x
```

Both paths return **identical** results (635), and the box was verified to be a
true superset of the circle — 0 facilities leaked — by
`backend/tests_api/test_geo_helpers.py`. The old path's cost grows linearly
with table size, so the gap widens toward ~300 ms once the full CSV is
imported; the boxed path stays flat.

A dedicated geo index (or PostGIS) remains optional later work.

### 5.5 Columns that do NOT exist (corrected)

~~Add `hospitals.foreign_pcare`.~~ **Cancelled.** `Foreign_pcare` is not a
flag: 30,271 of 30,273 CSV rows contain the literal string `'0'` and the
remaining 2 contain a phone number (`0091 4043441066`). Building an
"international desk" badge on it would have shipped a field that is wrong or
empty for every facility on earth.

Same verdict for the rest of the "unused but available" enrichment columns:
`Accreditation` (0 usable rows), `Hospital_Regis_Number` (0),
`Total_Num_Beds` (24), `Ambulance_Phone_No` (13), `Emergency_Num` (94).
**Do not build UI that depends on them.** An international-desk signal must
come from Overpass/OSM tags or from facilities volunteering the information.

---

## 6. Pillar 3 — Urgent ambulatory care & appointments

Strictly scoped to **non-life-threatening walk-ins**: travellers' diarrhoea, viral fever, minor cuts, prescription refills, basic doctor visits.

### 6.1 Storage: guest-local with optional sync

- Store: `localStorage["medtour:appointments:v1"]`, an array of records shaped like the backend `Appointment` minus `user_id`.
- No 401, no `/login` redirect. The page never prompts for identity to *read* or *create* a record.
- Optional sync: after a booking succeeds, offer once — *"Sign in to see this on other devices"* — linking to `/login`. If a token exists, mirror the record to `POST /appointments` best-effort and keep the local copy as source of truth if the call fails.
- Existing backend endpoints keep requiring JWT (they are unchanged for signed-in users).

### 6.2 The three tabs

`Upcoming` · `Completed` · `Cancelled` — this is already implemented in `src/routes/appointments.tsx` (upcoming/completed/cancelled + an "All" tab). Changes:

- Drop the **All** tab (three tabs, per spec).
- Remove the **Check In / Mark Completed** controls that push status to the server — those are *hospital-side* actions. A patient does not check themselves in through a travel app; the hospital desk does. Keep **Cancel** (freeing a slot the user booked) and **Book again**.
- Keep search + refresh; refresh only matters when synced.

### 6.3 Receipts for travel insurance

On each `Completed` record:

1. **`.ics` calendar export** (already the plan for Upcoming; add a "Add to calendar" action) — Blob download, no server.
2. **"Download visit record (patient copy)"** — client-generated printable page → `window.print()` / *Save as PDF*.

Honesty constraint: this document is generated from data the user entered. It is **not** a hospital-issued tax invoice and must not claim to be. Label it:

> *Patient-generated visit record. For insurance reimbursement, request the hospital's official billed invoice from the facility's billing counter.*

Include on it: patient name, travel insurance / passport reference (optional,
user-entered), facility name + address + city/state, department, date/time,
symptoms note, and the user-entered amount if any.

**Do not print `registration_number`, `accreditation`, or an ER number from
the directory — those columns are empty for ~100% of rows (§5.0).** Pull the
facility's phone from Overpass/OSM when available, and otherwise omit the row
rather than printing a blank or a `'0'`.

Offer alongside it a `tel:` shortcut: *"Call the hospital to request the
official bill"*.

---

## 7. Backend: what changes

Full matrix in [`api_endpoints.md`](./api_endpoints.md). Status as of 2026-10-10:

| Area | Action | Status |
| --- | --- | --- |
| `POST /emergency/sos` | Retained as a **deprecated, side-effect-free acknowledgement** for older clients. Response now says `dispatched: false`, `deprecated: true`, *"MedTour does not contact emergency services…"*, and returns the 112/108 numbers. No DB row, no JSON file, no `eta_minutes`, no `DISPATCH_INITIATED`. | ✅ done |
| `sos_alerts` table | No longer written by anything. Table and model left in place, unused; drop during cleanup. | ✅ done (write path removed) |
| `/admin` | **Unmounted** from `app/main.py`. The module stays on disk with a deprecation header because it is untracked in git (see `project_progress.md` Phase 0). Also removes an unauthenticated API surface. | ✅ done (server side) |
| `sos_backend.py` (simulated dispatch) | **No longer imported by anything.** Same deprecation header, same untracked-file caveat. | ✅ done (server side) |
| `GET /hospitals/nearby` | Bounding-box pre-filter (§5.4, measured 14.3×), `sort=distance\|emergency`, optional `limit` for the SOS sheet, full contact block per row, `has_emergency_phone` hint. **Stays local-only** by design. | ✅ done |
| 🆕 `GET /hospitals/discover` | Merges Overpass + Geoapify + local table (§5.1), dedupes, and inserts **only genuinely new** facilities (≤100/call, India-bounded). Returns `{results, sources, stats, degraded}`. | ✅ done |
| 🆕 `hospitals.id` | Was a bare `bigint NOT NULL` with no default (pandas-built), so **every insert raised `NotNullViolation`** — including `POST /hospitals/`. Now sequence-backed via `_ensure_discovery_columns()`. | ✅ done |
| `emergency=true` | Ranks instead of filtering (§5.0). | ✅ done |
| `GET /hospitals/` | Was an unpaginated full-table dump; now `limit`/`offset` (default 20, max 100) with `total`. | ✅ done |
| `POST /hospitals/` | Was anonymous write into the "verified" directory. Now requires JWT **and** an `X-Hospital-Write-Key` matching `HOSPITAL_WRITE_KEY`; 403 when unset. | ✅ done |
| `POST /hospitals/{id}/queue` | Was an anonymous write feeding the waiting-time predictor. Same write-key gate. `GET` stays public. | ✅ done |
| `foreign_pcare` column | **Cancelled** — the source column is junk (§5.5). | ❌ cancelled |
| `/appointments` | Unchanged (JWT). The hospital-side routes stay mounted and dormant per `api_endpoints.md` §2.4; frontend no longer calls them for guests. | ✅ unchanged by design |
| `/ai/analyze`, `/waiting-time/predict` | Unchanged — they serve triage and walk-in expectations, both in scope. | ✅ unchanged |

### Audit defects — resolution

1. **`logger` undefined in `emergency.py`** (3 sites, all inside `except`
   blocks, so the error handlers themselves raised `NameError`) —
   ✅ fixed: module now uses `logging.getLogger(__name__)`.
2. **Double-scheduled background work** (`asyncio.create_task(...)` then
   `background_tasks.add_task(task)` on the already-running task) —
   ✅ gone: the whole simulated-dispatch path was removed.
3. **`/admin/*` had no auth dependency** (`_verify_admin` existed but was
   never wired in) — ✅ resolved by unmounting the router.
4. **`/hospitals/nearby` full-table scan** — ✅ fixed, measured (§5.4).
5. **`admin.tsx` client-side password gate with `admin123` in source** —
   ⏳ still present; remove with the frontend `/admin` route (Phase 4).
6. **`hospitals.id` had no default**, so every insert into the table failed —
   ✅ fixed at startup. Found while building `/discover`; had been latent since
   the CSV import, and `POST /hospitals/` would have failed on first real use.
7. **`backend/requirements.txt` was UTF-16 with a BOM** and did not list
   `requests`, which the app already imported. ✅ normalised to UTF-8 and
   `requests==2.34.2` pinned.

---

## 8. Explicitly out of scope

Do not build, in any phase:

- ❌ Hospital ERP / provider-facing patient intake, billing, or scheduling dashboards.
- ❌ An unmonitored dispatch backend that implies a human saw the alert.
- ❌ Elective medical-tourism packages (cosmetic/dental/orthopedic surgery tourism, visa letters, flight booking, pricing comparison).
- ❌ Mandatory authentication before triage or emergency action.
- ❌ Full UI-string translation as a substitute for medical flashcards.
- ❌ Waiting-room queue telematics as a core feature (the `/admin` intake board idea is shelved with `/admin`).

If a hospital *wants* to publish bed availability or an international-desk number, that belongs in the facility record (§5.5) — a field they can update, not a portal they must log into.

---

## 9. Risks & open questions

| # | Item | Notes |
| --- | --- | --- |
| 1 | **Uber/Ola deep-link formats** unverified | Confirm on Android + iOS in Phase 1; fall back to Google Maps directions. |
| 2 | **Overpass data completeness** varies by region | Mitigated by the directory merge (30k verified facilities) and by keeping `tel:` primary. |
| 3 | **Overpass rate limits / outages** | sessionStorage cache + 20 s abort + directory fallback. |
| 4 | **Nominatim usage policy** | Requires a identifying User-Agent/Referer; low volume here. Never block the coordinate display on it. |
| 5 | **`tel:112` in a browser** opens the OS dialler — some desktop browsers do nothing | Acceptable: the product is mobile-first; desktop shows the number in huge text to read aloud. |
| 6 | **Guest-local appointments are device-local** | By design. Optional sync is the escape hatch; users on shared/public devices must be warned. |
| 7 | **"Patient copy" receipts vs. insurer expectations** | Some insurers require a hospital-stamped bill. Wording in §6.3 is deliberate; do not soften it. |
| 8 | **Uncommitted work in the tree** | `git status` shows ~24 modified + ~30 untracked files (this whole feature set is uncommitted). **Commit before Phase 1 starts.** Do not rewrite pushed history (see root `AGENTS.md` — Lovable sync). |

---

## 10. Build order

See [`project_progress.md`](./project_progress.md) for the phase-by-phase checklist.

**Phase 1 — Emergency toolkit (highest value):** SOS sheet with `tel:112`, non-blocking GPS address, Overpass top-3, ride-hail links, flashcards, de-lie the existing SOS copy, fix the backend defects in §7.
**Phase 2 — Guest-first shell:** nav rework, demote/remove auth CTAs, retitle `/dashboard` to symptom triage, route `/emergency`.
**Phase 3 — Appointments:** local store, three tabs, calendar export, honest visit record, optional sync prompt.
**Phase 4 — Cleanup:** deprecate `/admin` and the SOS backend write path, bounding-box query, `foreign_pcare` column, dead-code removal (`mock-data.ts`, dormant i18n), docs.
