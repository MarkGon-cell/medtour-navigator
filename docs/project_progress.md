# Project Progress — Redesign Roadmap

Phased plan for the MedTour redesign. Spec: [`architecture.md`](./architecture.md) · endpoints: [`api_endpoints.md`](./api_endpoints.md) · schema: [`database_schema.md`](./database_schema.md).

**Decisions already taken (this pass):**

- ✅ Spec-first — no feature code until this document is signed off.
- ✅ **Guest-first, optional login** — `/login` and `/register` stay, but nothing critical is behind them and nav stops promoting them.
- ✅ **Overpass API (keyless)** as the primary source — and, per the data audit below, the *only* source of emergency-capability and contact tags. The local directory contributes named coverage, address and directions targets, **not** phones/accreditation (those columns are ~empty).
- ✅ **Guest-local appointments** with optional sync; three tabs; calendar export + honest visit record.
- ✅ **`sos_alerts` decision: A** — stop writing; endpoint is now a side-effect-free acknowledgement.
- ✅ **Auth scope (2026-10-09)** — `/auth`, `/profile` and all eight `/appointments` routes stay **mounted but deprecated**: module docstrings in `app/auth/auth.py` and `app/api/appointments.py` say so, and `GET /` now returns them under a `deprecated` key. Nothing links to them. Delete in Phase 4.
- ✅ **Badge policy (2026-10-09)** — render only what Overpass can prove; `English Speaking Staff`, `Cashless Insurance Desk`, `GSTIN` and `ICD-10` are never rendered. Full table in [`architecture.md`](./architecture.md) §5.0 item 5.
- ✅ **Hospital search = Overpass + Geoapify, store-new-only (2026-10-10)** — `GET /hospitals/discover` merges both providers with the local table. Both are OSM-backed, so the pair buys *availability* redundancy, not coverage: Overpass is keyless but its public mirrors are erratic, Geoapify is keyed but stable and explicitly permits caching/storing results. Anything already in Postgres is returned but **never re-inserted and never overwritten**; only genuinely new facilities are written, capped at 100 per call and guarded to India. Local-only `GET /hospitals/nearby` is unchanged and stays the fast path.
- ⏸ **Route naming** — deliberately not reconciled (user: "dont bother"). `architecture.md` §3 and `FRONTEND.md` §1 both remain; resolve at the start of the frontend phase, not before.

---

## Status: backend pass complete (2026-10-10)

Everything backend-side in Phases 1 and 4 below is **done**, except the
destructive re-import. Verified against a live server and the real `medtour_db`:

| | |
| --- | --- |
| Endpoint suite | **31/31** (`backend/scripts/verify_endpoints.py`) |
| Discovery suite (dedupe, persistence, live endpoint) | **36/36** (`backend/tests_api/test_discovery.py`) |
| Geo unit tests | **8/8** (`backend/tests_api/test_geo_helpers.py`) |
| Honest-SOS contract test | pass (`backend/tests_api/test_sos_api.py`) |
| `/hospitals/nearby` speedup | **14.3×** (100.2 ms → 7.0 ms), identical results |

### ⚠️ Data audit findings that changed the plan

Probed live (`backend/scripts/probe_hospital_data.py`), details in
[`architecture.md`](./architecture.md) §5.0:

- **DB has 10,607 of the CSV's 30,273 rows** and only **19 of 36 states** —
  Uttar Pradesh (3,158), Tamil Nadu (2,399), Rajasthan, Punjab, West Bengal,
  Odisha and Telangana are **entirely absent**. A traveller in Lucknow or
  Chennai currently gets zero results.
- **Delhi has 0 rows in the CSV itself**, so no re-import fixes it.
- **`emergency_available` is true for exactly 1 facility nationwide**; usable
  accreditation 0, beds 24, emergency phone 94. `emergency=true` therefore had
  to become a **rank**, not a filter.
- **`Foreign_pcare` is junk** — the planned column was cancelled rather than
  shipped broken.
- **Every insert into `hospitals` was broken.** The CSV importer rebuilds the
  table with `pandas.to_sql`, producing `id bigint NOT NULL` with no default
  and no identity column. SQLAlchemy omits `id` from the INSERT, so Postgres
  had nothing to fill it with. This silently broke `POST /hospitals/` before
  the redesign. Fixed by `_ensure_discovery_columns()` in `app/main.py`, which
  runs on every startup and survives a re-import.

### New P0

- [ ] **Set `GEOAPIFY_API_KEY` in `backend/.env`** (free tier, 3,000 req/day, no
      card). Without it `/hospitals/discover` reports `geoapify: "no_api_key"`
      and runs Overpass-only — which, on 2026-10-09, meant **every** provider
      was down and the endpoint correctly returned `degraded: true`.
- [ ] **Re-import the full CSV** (10,607 → 30,273 rows; 19 → 36 states).
      **Destructive:** `scripts/import_hospitals.py` issues
      `DROP TABLE IF EXISTS appointments CASCADE` first, so existing
      appointments are lost. Decide whether that matters (appointments are
      moving to localStorage anyway) and take a `pg_dump` before running.
- [x] **Fix `hospitals.id`** so inserts work — done via the startup migration.
- [ ] Decide what to do about **Delhi**: source data has none. Options —
      another dataset, or rely on Overpass for NCT coverage and say so.

---

## Phase 0 — Groundwork

- [ ] **Commit the current working tree first.** ~24 modified + ~30 untracked files — the entire auth/appointments/admin feature set is uncommitted. Never rewrite pushed history (root `AGENTS.md`: Lovable sync).
- [ ] Stop tracking compiled artefacts: drop `backend/**/__pycache__/*.pyc` from git and gitignore them.
- [ ] Sign-off on this spec (or amend it).
- [ ] Create the feature branch for Phase 1.

---

## Phase 1 — The emergency toolkit (highest value)

The phase that justifies the product.

**SOS surface**

- [ ] `/emergency` route + modal-from-`/` sheet, mobile-first full-screen.
- [ ] `tel:112` primary action and `tel:108` secondary — rendered and tappable **before** any async work resolves.
- [ ] Non-blocking GPS: `getCurrentPosition` → large monospace coordinates; Nominatim reverse geocode fills the street line behind it; geocode never blocks (8 s cap).
- [ ] Denied-permission fallback: city + "say your hotel/landmark name".
- [ ] Copy-to-clipboard of the whole location block; raw Maps pin for WhatsApp.
- [ ] **De-lie the existing copy**: remove *"SOS SENT — Help is on the way!"*, *"Ambulance dispatch logged in backend"*, *"Nearest 108 unit alerted"* from `src/routes/index.tsx` and `src/routes/dashboard.tsx`.

**Hospital lookup**

- [ ] Overpass client (`POST` + `data=`, `nwr` + `out center`, 20 s `AbortController`, sessionStorage cache, debounced).
- [ ] Merge with `GET /hospitals/nearby?sort=emergency&limit=3` for address/directions target; render offline-tolerant (Overpass-only is acceptable). **Get phones and `emergency=yes` from Overpass tags — the directory cannot supply them (§5.0).**
- [ ] Top 3 within ~10 km on the SOS sheet; full list stays on `/hospitals`.
- [ ] Ranking: distance → `amenity=hospital` > `clinic` > `doctor`, bonus for `emergency=yes`, `opening_hours=24/7`, phone present.

**Ride-hail & contacts**

- [ ] Uber deep link — **verify on Android + iOS**; fallback Google Maps directions.
- [ ] Ola deep link — **verify on Android + iOS**; fallback Google Maps directions.
- [ ] Universal `https://www.google.com/maps/dir/?api=1&destination=…`.
- [ ] Emergency-contact handoff: `wa.me` / `sms:` with pin + timestamp, user presses send (no Twilio, no backend).

**Flashcards**

- [ ] `/flashcards` + full-screen modal from the SOS sheet: *"PLEASE TAKE ME TO THE NEAREST EMERGENCY ROOM IMMEDIATELY…"*
- [ ] Languages: Hindi, Marathi, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Punjabi (+ English gloss).
- [ ] Symptom / allergy / prescription cards; language remembered in `localStorage`.
- [ ] Keep it a standalone content module — do **not** extend `src/lib/i18n.tsx` (its provider is never mounted; it is dead code).

**Backend defects — ✅ all fixed (2026-10-09)**

- [x] `logger` undefined in `backend/app/api/emergency.py` → module now uses `logging.getLogger(__name__)`.
- [x] Double-scheduled background task → gone with the rewrite.
- [x] Response claiming `"eta_minutes": 8` / `"DISPATCH_INITIATED"` → endpoint now returns `dispatched: false`, `deprecated: true`, and states plainly that MedTour does not contact emergency services.

**Verification added this pass**

- [x] `backend/scripts/verify_endpoints.py` — 31 endpoint checks.
- [x] `backend/tests_api/test_geo_helpers.py` — haversine + bounding-box superset proofs.
- [x] `backend/tests_api/test_sos_api.py` — rewritten to assert honesty (was asserting `status == "success"`).
- [x] `backend/scripts/benchmark_nearby.py` — quantifies the speedup.

**Verify**

- [ ] Real phone, real browser: SOS sheet works with backend **stopped** (proves the emergency path is network-independent).
- [ ] Denied geolocation → still usable.
- [ ] Airplane-mode-ish / slow 3G → `tel:` still tappable instantly.
- [ ] Screenshot of each flashcard language.

---

## Phase 2 — Guest-first shell

- [ ] Rebuild nav: Home · Emergency · Hospitals · Flashcards · Appointments. Remove *Sign in / Get Started* as primary CTAs (`src/components/site/Navbar.tsx`, `PageHeader`, `ProfileMenu`).
- [ ] Landing `/`: emergency toolkit becomes the hero (above the fold: SOS + address + nearest 3); marketing content moves below.
- [ ] CTAs become *"Find care near me"* → `/hospitals`, not `/register`.
- [ ] Retitle `/dashboard` → **Symptom triage**; drop its duplicate SOS button (one SOS entry point only).
- [ ] `GET /profile` becomes optional — no failed-request noise for guests.
- [ ] `/login`, `/register` reachable only by URL and by the post-booking sync prompt.
- [ ] Audit all remaining links to `/register` and `/login` across `src/`.

---

## Phase 3 — Appointments for travellers

- [ ] Local store `medtour:appointments:v1` (schema in [`database_schema.md`](./database_schema.md) §4).
- [ ] Three tabs only — **Upcoming / Completed / Cancelled**; drop *All*.
- [ ] Remove patient-driven **Check In** / **Mark Completed** actions (hospital-side actions); keep **Cancel** and **Book again**.
- [ ] No `401` → `/login` redirect; the page never prompts for identity to read or create.
- [ ] `.ics` export (Blob download) from Upcoming.
- [ ] **Download visit record (patient copy)** from Completed — printable/PDF, labelled honestly, with a `tel:` shortcut to request the official hospital bill. **Do not print `registration_number`/`accreditation`** — those columns are empty for ~100% of rows (`architecture.md` §5.0).
- [ ] One-time optional sync prompt *after* a booking: "Sign in to see this on other devices" → mirror to `POST /appointments` best-effort, local copy remains source of truth on failure.
- [ ] Devices-shared warning on the local-only note.

---

## Phase 4 — Cleanup & hardening

**Backend — done this pass:**

- [x] **Unmount `/admin/*` endpoints** — returns 404; module retained on disk with a deprecation header *only because it is untracked in git*. **Still to do:** remove `src/routes/admin.tsx` and its `admin123` client-side gate.
- [x] **Stop writing `sos_alerts`** (decision A) — endpoint is side-effect free. **Still to do:** drop the table, the `SOSAlert` model, and `backend/sos_logs/`.
- [x] **Bounding-box pre-filter** for `GET /hospitals/nearby` (14.3× measured).
- [x] **Restrict unauthenticated writes** — `POST /hospitals/` and `POST /hospitals/{id}/queue` now need JWT + `X-Hospital-Write-Key`.
- [x] **Paginate `GET /hospitals/`** (was an unbounded full-table dump).
- [x] **Gate `sos_backend.py`** — simulated dispatch no longer imported by anything; header added, safe to delete.
- ❌ **Add `hospitals.foreign_pcare` — cancelled.** Source column is junk (`architecture.md` §5.5).

**Still open:**

- [ ] **Re-import the full CSV** (P0, destructive — see New P0 above).
- [ ] Decide fate of `hospital_queue_status` / `GET /hospitals/{id}/queue` and the three hospital-side appointment routes (`status`, `check-in`, `start-consultation`) — they are JWT-gated and dormant, but `start-consultation` is what feeds `HospitalWaitingObservation` for the waiting-time model.
- [ ] Delete dead code: `src/lib/mock-data.ts`, dormant `src/lib/i18n.tsx` + `src/i18n/` (or finally mount it — one or the other).
- [ ] Drop tracked `backend/**/__pycache__/*.pyc` from git.
- [ ] Lint + `vite build` green; smoke-test every route.

---

## Explicitly not scheduled

Do not pick these up as "quick wins" — they are out of scope by decision ([`architecture.md`](./architecture.md) §8):

- ❌ Hospital ERP / provider dashboards, patient intake, billing, scheduling
- ❌ An unmonitored dispatch backend
- ❌ Elective medical-tourism packages (cosmetic/dental/orthopedic tourism, visa letters, flights)
- ❌ Mandatory auth before triage or emergency action
- ❌ UI-string translation in place of medical flashcards

---

## Open questions blocking nothing (decide during the phase)

1. Uber/Ola deep-link formats — confirm on device in Phase 1; fall back to Google Maps if either fails.
2. Keep `/login` + `/register` as-is, or slim them to a single "sync your visits" screen?
3. ~~`sos_alerts`: retire (A) vs repurpose (B)?~~ **Resolved: A implemented 2026-10-09.** B remains available later if we want anonymous usage telemetry.
4. Do we ship a PWA manifest + service worker? The spec's "offline-tolerant" principle leans yes, but it is not required for Phase 1.
5. **Delhi has no source data** — a re-import will not fix it. Do we add another dataset, or let Overpass carry NCT coverage?
