# API Endpoints — As-Is → Target

Companion to [`architecture.md`](./architecture.md). "As-is" reflects the code in `backend/app/` at time of writing (verified by reading the routers, not inferred).

Legend: ✅ keep · 🔧 change · ⛔ deprecate · 🆕 new

---

## 1. Frontend → Backend call map (as-is)

| Frontend caller | Method + path | Auth | Target |
| --- | --- | --- | --- |
| `src/routes/index.tsx:102` (landing SOS) | `POST /emergency/sos` | guest | ⛔ **remove the call** — replace with `tel:112` + UI (§4.1 of spec) |
| `src/routes/dashboard.tsx` (SOS button) | `POST /emergency/sos` | guest | ⛔ **remove the call** — same |
| `src/routes/dashboard.tsx` (profile greeting) | `GET /profile` | JWT | 🔧 make optional — greeting degrades for guests |
| `src/routes/dashboard.tsx` | `POST /ai/analyze` | guest | ✅ keep |
| `src/routes/dashboard.tsx` (Nominatim) | `GET nominatim.openstreetmap.org/*` | guest | ✅ keep — also powers the read-aloud address |
| `src/routes/results.tsx` | *(none — reads `sessionStorage`)* | — | ✅ keep |
| `src/routes/hospitals.tsx` | `GET /hospitals/nearby` | guest | 🔧 bounding-box query; merge with Overpass results |
| `src/routes/hospital-details.$hospitalId.tsx` | `GET /hospitals/{id}`, `/availability` | guest | ✅ keep |
| `src/routes/hospital-details.$hospitalId.tsx` | `POST /waiting-time/predict` | guest | ✅ keep |
| `src/routes/appointments.tsx` | `GET /appointments` (+ `PATCH …/cancel`, `PATCH …/status`, `POST …/check-in`) | **JWT required** | 🔧 guest reads/writes become local; optional sync keeps `POST /appointments` + `PATCH …/cancel` |
| `src/routes/login.tsx` / `register.tsx` | `POST /auth/login`, `POST /auth/register` | guest | ✅ keep — demoted to optional post-care signup |
| `src/routes/admin.tsx` | `POST /admin/verify`, `GET /admin/*`, `PATCH /admin/*`, `DELETE /admin/*` | client-side `admin123` | ⛔ **deprecate route + endpoints** |
| *(nothing today)* | Overpass | guest | 🆕 browser → `https://overpass-api.de/api/interpreter` |

---

## 2. Backend router inventory

### 2.1 Root — `backend/app/main.py`

| Method | Path | As-is auth | Target |
| --- | --- | --- | --- |
| GET | `/` | public | ✅ |
| GET | `/health` | public | ✅ |
| GET | `/profile` | **JWT** | 🔧 unchanged in backend; frontend treats as optional |

### 2.2 `/auth` — `app/api/auth` wiring

| Method | Path | Auth | Target |
| --- | --- | --- | --- |
| POST | `/auth/register` | public | ✅ keep |
| POST | `/auth/login` | public (OAuth2 form) | ✅ keep |

### 2.3 `/hospitals` — `app/api/hospitals.py` — ✅ REWORKED

| Method | Path | Was | Now |
| --- | --- | --- | --- |
| POST | `/hospitals/` | public (unauthenticated create!) | ✅ requires **JWT + `X-Hospital-Write-Key`** matching env `HOSPITAL_WRITE_KEY`; 403 when the key is unset, so directory writes are off by default |
| GET | `/hospitals/` | public, returned **all rows** | ✅ paginated: `limit` (1–100, default 20) / `offset`, returns `{total, limit, offset, items}`. Confirmed unused by the frontend. |
| GET | `/hospitals/nearby?latitude&longitude&radius_km&specialty&emergency` | **full-table scan** then haversine in Python | ✅ bounding-box SQL pre-filter → exact haversine on candidates. Measured **14.3×** (100.2 ms → 7.0 ms) with identical results. |
| ↳ new params | — | *(none)* | `sort=distance\|emergency` (default `distance`) and `limit` (e.g. `limit=3` for the SOS sheet) |
| ↳ `emergency=true` | — | hard filter | ✅ **ranks** emergency-capable/reachable facilities first instead of excluding the rest — a hard filter yields 1 facility for all of India (see `architecture.md` §5.0). Rows keep a truthful `emergency_available`. |
| ↳ response fields | — | subset | ✅ adds `emergency_phone`, `bloodbank_phone`, `mobile`, `tollfree`, `helpline`, `accreditation`, `registration_number`, `care_type`, and a computed `has_emergency_phone` hint |
| GET | `/hospitals/search` | public | ✅ unchanged behaviour, same payload shape as nearby |
| 🆕 GET | `/hospitals/discover?latitude&longitude&radius_km&limit&persist` | *(none)* | ✅ **new**: queries Overpass **and** Geoapify alongside the local table, dedupes against it, and inserts **only facilities that are genuinely new**. Returns `{results, sources, stats, degraded}`. |
| GET | `/hospitals/{id}` | public | ✅ unchanged |
| GET | `/hospitals/{id}/availability` | public | ✅ unchanged |
| POST | `/hospitals/{id}/queue` | **public write** feeding the waiting-time predictor | ✅ now requires `X-Hospital-Write-Key`; 403 otherwise. Anonymous callers could previously publish "0 doctors available" for any facility. |
| GET | `/hospitals/{id}/queue` | public | ✅ unchanged (read-only) |

#### `GET /hospitals/discover` — combined Overpass + Geoapify search

Use this when you want the network-backed view. Use `GET /hospitals/nearby` when
you don't: it touches no external service, so it stays fast and works offline.

```
GET /hospitals/discover?latitude=19.076&longitude=72.878&radius_km=5&limit=50&persist=true
```

Both providers draw on **OpenStreetMap**, so combining them buys *availability*
redundancy rather than extra coverage — Overpass is keyless but its public
mirrors are erratic (all four probed on 2026-10-09 returned 500/504 or timed
out), while Geoapify needs a key but is operationally stable and states that
results may be cached and stored without limit.

**Persistence policy** — a facility is written to `hospitals` only if it is new:

| Situation | Result |
| --- | --- |
| Already in the directory (≤60 m, or ≤300 m **and** names match, or same `external_id`) | returned as `origin: "local"`, `stored: true` — **never re-inserted, never overwritten** |
| Genuinely new | inserted, `stored: true`, `origin: "overpass"\|"geoapify"` |
| Outside India / no name | rejected with `stored_reason: outside_india` / `missing_name` |
| More than 100 new in one call | remainder flagged `persist_limit_reached` |

```jsonc
{
  "results": [
    { "name": "…", "latitude": 19.07, "longitude": 72.87, "distance_km": 0.4,
      "origin": "local", "external_id": null, "stored": true, "stored_reason": null }
  ],
  "sources": { "local": "ok", "overpass": "unreachable", "geoapify": "no_api_key" },
  "stats": { "returned": 635, "local": 635, "overpass": 0, "geoapify": 0,
             "duplicates_dropped": 0, "persisted": 0, "rejected": 0 },
  "degraded": true
}
```

**It never fails when a provider does.** If every external source is down you
still get local results plus `degraded: true` and a per-provider status — an
emergency flow must not break because a mirror is down. That is why the
response is an object rather than a bare array: the caller has to be able to
tell "no hospitals here" from "the providers were unreachable".

**Auth.** This route is deliberately *not* write-key gated, unlike
`POST /hospitals/` — it can only ever insert facilities fetched from the
providers themselves, filtered to India with a name and bounded to 100 rows
per call, so an anonymous caller cannot inject arbitrary data. It is a GET
with a side effect; the 15-minute per-area cache keeps a crawler from burning
the 3,000/day free Geoapify quota.

**Requires `GEOAPIFY_API_KEY`** in `backend/.env` (free tier, no card). Without
it the endpoint reports `geoapify: "no_api_key"` and runs Overpass-only.

### 2.4 `/appointments` — `app/api/appointments.py`

All eight routes use `Depends(get_current_user)` → **JWT required**.

| Method | Path | Target |
| --- | --- | --- |
| POST | `/appointments` | ✅ keep (used only by optional sync) |
| GET | `/appointments` | ✅ keep (signed-in users) |
| GET | `/appointments/{id}` | ✅ keep |
| PATCH/POST | `/appointments/{id}/cancel` | ✅ keep (both verbs registered on one handler) |
| PATCH | `/appointments/{id}/status` | 🔧 **candidate for removal** — "mark completed" is a hospital-side action a patient shouldn't drive |
| DELETE | `/appointments/{id}` | ✅ keep |
| POST | `/appointments/{id}/check-in` | ⛔ **candidate for removal** — same reason |
| POST | `/appointments/{id}/start-consultation` | ⛔ **remove** — this is clinical workflow, i.e. running the hospital |

**Decision needed:** whether to drop the three hospital-side routes or leave them dormant. Recommendation: leave them in place for now (harmless, JWT-gated, no frontend caller after Phase 3) and remove in a later cleanup — avoids a schema/data migration during the redesign.

### 2.5 `/emergency` — `app/api/emergency.py` — ✅ REWRITTEN

| Method | Path | Was | Now |
| --- | --- | --- | --- |
| POST | `/emergency/sos` | guest-allowed; inserted `sos_alerts` (`status="PENDING"`), wrote `backend/sos_logs/*.json`, returned `"simulated": true` + `"eta_minutes": 8` | ✅ **side-effect-free acknowledgement**: `{"status":"acknowledged","dispatched":false,"deprecated":true,"message":"MedTour does not contact emergency services or dispatch ambulances. Call 112 from your phone.","emergency_numbers":{...},"location":{...}}`. No DB row, no file, no async work. |

`logger`/`asyncio.create_task` defects are gone with the rewrite. The frontend
call in `src/routes/index.tsx:102` and `src/routes/dashboard.tsx:262` is now
redundant and should be deleted in Phase 1 of the frontend work — until then it
receives a truthful response.

### 2.6 `/ai` and waiting-time

| Method | Path | Auth | Target |
| --- | --- | --- | --- |
| POST | `/ai/analyze` | guest | ✅ keep — core triage |
| POST | `/waiting-time/predict` | guest | ✅ keep — sets walk-in expectations |
| POST | `/waiting-observations` | guest | ✅ keep |

### 2.7 `/admin` — `app/api/admin.py` — ✅ UNMOUNTED

| Method | Path | Was | Now |
| --- | --- | --- | --- |
| POST | `/admin/verify` | password `admin123` / env `ADMIN_PASSWORD` | ⛔ returns 404 |
| GET/PATCH/DELETE | `/admin/sos-alerts…` | **none** (`_verify_admin` exists but was never wired as a dependency) | ⛔ returns 404 |
| GET/PATCH/DELETE | `/admin/appointments…` | **none** | ⛔ returns 404 |

Rationale, not just hiding: the console existed to review SOS alerts and
moderate appointments. The redesign removes the SOS write path and makes
appointments guest-local, so there is nothing left to moderate — and the
surface was publicly writable.

The module file is retained with a deprecation header **only because it is
untracked in git** (deleting it would be unrecoverable). Delete it once the
frontend `/admin` route goes.

---

## 3. External services (browser → third party)

| Service | Endpoint | Auth | Used for | Phase |
| --- | --- | --- | --- | --- |
| 🆕 **Overpass API** | `POST https://overpass-api.de/api/interpreter` (+ 3 mirrors, tried in turn) | none | hospital/clinic capability tags via `nwr` + `out center`; `emergency_ward_entrance` used to flag ER-capable facilities | ✅ **backend** (`app/services/discovery.py`) |
| 🆕 **Geoapify Places** | `GET https://api.geoapify.com/v2/places` | **API key** (free tier, 3,000 req/day) | same search, second source; terms allow caching/storing results | ✅ **backend** (`app/services/discovery.py`) |
| Nominatim | `GET https://nominatim.openstreetmap.org/reverse` | none (needs identifying UA/referer) | read-aloud street address | 1 |
| 🆕 Google Maps | `https://www.google.com/maps/dir/?api=1&destination=lat,lng` | none | universal directions fallback | 1 |
| 🆕 Uber / Ola deep links | `https://m.uber.com/ul/...`, `https://book.olacabs.com/...` | none | ride to the nearest ER — **formats unverified, confirm on device** | 1 |
| 🆕 WhatsApp / SMS handoff | `https://wa.me/?text=...`, `sms:...?&body=...` | none | assisted send to a saved emergency contact | 1 |
| OS dialler | `tel:112`, `tel:108`, `tel:{hospital}` | none | the actual emergency action | 1 |
| Leaflet + OSM tiles | existing | none | facility maps | ✅ |

**No new API keys on the emergency path.** Every Phase-1 *browser* integration is
keyless — deliberate, so a guest's emergency path never depends on a secret we
might lose, quota, or bill. The one exception is Geoapify, which is a *backend*
call with a key held server-side, and which degrades to Overpass-plus-local when
absent.

**ABDM HFR was considered and rejected** as a search layer: it exposes a
`Nearby search` endpoint (docs.abdm.gov.in) but it is HPR-token-gated and aimed
at facility onboarding, not consumer search.

---

## 4. Build status & verification

| Item | Status |
| --- | --- |
| 🔧 `GET /hospitals/nearby` bounding-box pre-filter, `sort`, `limit`, expanded payload | ✅ **done** |
| 🔧 `GET /hospitals/` pagination | ✅ **done** |
| 🔧 write-key gating on `POST /hospitals/` and `POST /hospitals/{id}/queue` | ✅ **done** |
| 🔧 `/emergency/sos` made honest and side-effect free | ✅ **done** |
| 🔧 `/admin/*` unmounted | ✅ **done** |
| 🆕 `GET /hospitals/discover` — Overpass + Geoapify, dedup, store-new-only | ✅ **done** |
| 🆕 `hospitals.id` sequence fix — **every insert into `hospitals` previously raised `NotNullViolation`** | ✅ **done** (see below) |
| 🔧 `Hospital.foreign_pcare` | ❌ **cancelled** — the CSV column is junk (see `architecture.md` §5.5). Do not build UI on it. |
| ⏳ Set `GEOAPIFY_API_KEY` in `backend/.env` | ⏳ **operator action** — free tier, no card. Until then `discover` runs Overpass-only. |
| ⏳ Re-import full CSV (10,607 → 30,273 rows, 19 → 36 states) | ⏳ **pending, destructive** — `import_hospitals.py` runs `DROP TABLE … CASCADE` on `appointments` first. Tracked in `project_progress.md`. |

> **Latent bug found and fixed.** `scripts/import_hospitals.py` builds the
> `hospitals` table with `pandas.to_sql(if_exists="replace")`, which created
> `id` as a bare `bigint NOT NULL` with **no default and no identity column**.
> SQLAlchemy omits `id` from the INSERT, so Postgres had nothing to fill it
> with and **every insert into `hospitals` raised `NotNullViolation`** —
> including the pre-existing `POST /hospitals/`, which would have failed the
> first time anyone used it. `_ensure_discovery_columns()` in `app/main.py`
> now runs a sequence-backed default on every startup and re-lands it after a
> re-import. Same hook re-adds the `source` / `external_id` / `opening_hours`
> columns the importer also drops.

**How this was verified** (all against a live server + the real `medtour_db`):

```bash
# 31 endpoint checks: SOS honesty, nearby perf/shape, pagination,
# write-key gating, admin removal, search, detail
python scripts/verify_endpoints.py

# 36 checks: name matching, duplicate detection, guards,
# DB persistence idempotency, live /discover contract
python tests_api/test_discovery.py

# pure-function tests: haversine correctness + bounding-box superset proof
python tests_api/test_geo_helpers.py

# honest-SOS contract test
python tests_api/test_sos_api.py

# quantifies the nearby-query speedup
python scripts/benchmark_nearby.py
```

Results at time of writing: **31/31 endpoint checks**, **36/36 discovery
checks**, **8/8 geo tests**, **14.3×** nearby-query speedup with identical
result sets.
