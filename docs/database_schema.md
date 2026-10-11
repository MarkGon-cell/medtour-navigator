# Database Schema — As-Is → Target

Companion to [`architecture.md`](./architecture.md) and [`api_endpoints.md`](./api_endpoints.md).
Tables are created via `Base.metadata.create_all` in `backend/app/main.py` — there is no migration framework, so schema changes are additive-only or require a manual `ALTER`.

---

## 1. Tables (as-is)

| Table | Model | Rows / notes | Target |
| --- | --- | --- | --- |
| `users` | `app/models/user.py` | Registered travellers | ✅ **keep, demoted** — optional post-care signup only |
| `hospitals` | `app/models/hospital.py` | **30,274** (from `hospital_directory.csv`) | ✅ keep, 🔧 + `foreign_pcare` column |
| `appointments` | `app/models/appointment.py` | `user_id` is **`nullable=False`** → server rows are inherently per-user | ✅ keep for signed-in sync; 🔧 no longer the primary store |
| `sos_alerts` | `app/models/sos_alert.py` | Write-only from the UI's perspective; `status` defaults `PENDING` | ⛔ see §3 |
| `hospital_availability` | `app/models/hospital_availability.py` | Fed by `/hospitals/{id}/availability` | ✅ keep |
| `hospital_queue_status` | `app/models/hospital_queue_status.py` | Patient queue tracking | ⛔ **candidate for removal** with the queue/`/admin` features |
| `hospital_waiting_predictions` | `app/models/hospital_waiting_prediction.py` | ML waiting-time output | ✅ keep (serves walk-in expectation) |
| `hospital_waiting_observations` | `app/models/hospital_waiting_observation.py` | Training observations | ✅ keep |

---

## 2. `hospitals` — enrichment the redesign needs

Current model already carries most of what the emergency toolkit surfaces:

```
emergency_available (bool)   emergency_services (text)   emergency_phone
ambulance_phone              bloodbank_phone
phone  mobile  tollfree  helpline  website  email
total_beds  private_wards  doctors  accreditation  registration_number
latitude (indexed)  longitude (indexed)  city  state  district  address  pincode
```

**Column additions made (2026-10-10):**

| Column | Type | Why |
| --- | --- | --- |
| `source` | `VARCHAR NOT NULL DEFAULT 'csv_import'` | Provenance. `csv_import` for the directory load, otherwise the provider that discovered the row (`overpass`, `geoapify`). Makes the "add new, never overwrite" rule auditable. |
| `external_id` | `VARCHAR`, indexed | Provider-native id (`osm/way/123456`, a Geoapify `place_id`). Lets a repeat search recognise a facility it already stored even if the mapped name changed or coordinates drifted. |
| `opening_hours` | `VARCHAR` | OSM `opening_hours`, kept so the UI can render a truthful "Open Now" badge. Never synthesised — absent means absent. |
| `foreign_pcare` | `Boolean` | ❌ **cancelled.** The CSV column is junk: 30,271 of 30,273 rows are the literal string `'0'` and the other 2 contain a phone number. Verified — see `architecture.md` §5.0/§5.5. An "international desk" badge built on it would be wrong for every facility. |

**These are applied at startup, not by migration tooling.**
`_ensure_discovery_columns()` in `app/main.py` runs after
`Base.metadata.create_all` and issues `ADD COLUMN IF NOT EXISTS` on every boot.
That is necessary because `scripts/import_hospitals.py` rebuilds this table
with `pandas.to_sql(if_exists="replace")`, which **silently drops all three**
— and would drop them again on the next re-import.

> ⚠️ **Related defect, fixed.** The same pandas-built table created `id` as a
> bare `bigint NOT NULL` with **no default and no identity column**. SQLAlchemy
> omits `id` from the INSERT, so Postgres had nothing to fill it with and
> **every insert into `hospitals` raised `NotNullViolation`** — the pre-existing
> `POST /hospitals/` included. The startup hook now installs a
> sequence-backed default (`hospitals_id_seq`) and resets the sequence above
> `MAX(id)` each boot, so it is safe to run before or after a re-import.

No other schema change was needed for the redesign. Note also that **the live
table is only 10,607 of the CSV's 30,273 rows and covers 19 of 36 states** —
missing Uttar Pradesh, Tamil Nadu, Rajasthan, Punjab, West Bengal, Odisha and
Telangana entirely. That is a coverage bug, not a schema bug.

**Query change (no schema change):** `GET /hospitals/nearby` now applies a
bounding-box predicate on the already-indexed `latitude`/`longitude` before the
haversine pass — measured 14.3× faster (100.2 ms → 7.0 ms) with identical
results.

**Data-integrity change:** `POST /hospitals/` was an unauthenticated insert
into the "verified" directory, and `POST /hospitals/{id}/queue` an
unauthenticated write feeding the waiting-time predictor. Both now require JWT
plus `X-Hospital-Write-Key` (env `HOSPITAL_WRITE_KEY`) and return 403 when the
key is unset — writes are off by default. `GET` routes stay public.

---

## 3. `sos_alerts` — the table at the centre of the false promise

```python
status = Column(String, default="PENDING")   # PENDING, DISPATCHED, RESOLVED, CANCELLED
log_path = ...                                # backend/sos_logs/sos_<ts>.json
```

**Was:** the frontend POSTed, this row was created, a JSON file was written to
`backend/sos_logs/`, and the API replied `"simulated": true, "eta_minutes": 8`.
No human, gateway, or carrier ever read it. Meanwhile the UI told the user help
was coming.

**Decision: A — taken and implemented 2026-10-09.** `app/api/emergency.py` no
longer touches this table or writes files. The endpoint is a pure function of
its request and returns `dispatched: false`. The table and `SOSAlert` model
still exist but **nothing writes to them**; drop both (and the `sos_logs/`
directory) during frontend cleanup.

| Option | What it means | Verdict |
| --- | --- | --- |
| **A. Stop writing it** | Endpoint + table remain but unused; removed in cleanup. | ✅ **implemented** |
| **B. Repurpose as `sos_sessions`** | Store only *what the user actually did* — dialled 112, copied address, opened ride-hail. Anonymous, opt-out. | 🤔 still available if we ever want usage analytics |
| **C. Keep as-is with honest copy** | Table stays, UI says "logged locally, no dispatcher was contacted." | ❌ rejected: still writes a record nobody reads, for no user benefit |

The existing `backend/sos_logs/*.json` files (5 at time of writing) are
historical artefacts and can be deleted with the table.

**Optional future note:** `backend/app/api/admin.py` imports `SOSAlert` but the
router is no longer mounted, so nothing breaks. Drop the import when deleting
that file.

---

## 4. Guest-local "tables" (browser storage)

These live in `localStorage`, not Postgres — no server, no auth, no 401.

### `medtour:appointments:v1` → `AppointmentRecord[]`

Mirrors the backend shape minus `user_id`, so an optional sync can map 1:1:

```ts
interface AppointmentRecord {
  id: string;                    // local ULID/uuid — server assigns its own on sync
  serverId?: number;             // set only if optional sync succeeded
  hospital_id: number;
  hospital?: {                   // denormalised snapshot: survives the facility record changing
    id: number; name: string; city?: string; state: string;
    address?: string; phone?: string; emergency_phone?: string;
    latitude?: number; longitude?: number;
    registration_number?: string; // used on the visit record
  };
  department?: string;
  appointment_time: string;      // ISO
  status: "upcoming" | "completed" | "cancelled";
  symptoms?: string;
  amount_paid?: number;          // user-entered, for the visit record
  created_at: string;
  updated_at: string;
}
```

Notes:

- **Status is exactly three values** (the three tabs). Backend transitional states (`booked`, `checked_in`, `in_consultation`) are hospital-side and are *not* modelled locally — a patient does not check themselves in through a travel app.
- Sync constraint: `appointments.user_id` is `nullable=False`, so `POST /appointments` **only works for registered users**. The optional-sync prompt is therefore genuinely optional, and failure must never block a local save.
- Storage budget is trivial (dozens of records). Cap at ~100, oldest-first eviction, consistent with `src/lib/history.ts`'s existing pattern.

### `medtour:emergency_contact:v1`

```ts
{ name: string; phone: string }   // one saved companion/embassy number
```
Used only by the assisted WhatsApp/SMS handoff.

### `medtour:flashcard_language:v1` → `"hi" | "mr" | "ta" | ...`
Remembers the last language used on the Show-the-Driver card.

### Existing keys (unchanged)

| Key | Purpose |
| --- | --- |
| `access_token` | JWT for optional sync (`src/lib/api.ts` interceptor) |
| `i18n_language` | dormant i18n (`src/lib/i18n.tsx` — provider never mounted) |
| `medtour_history:<id\|guest>` | local triage/search history (`src/lib/history.ts`) |
| `medtour_admin_auth` | ⛔ removed with `/admin` |
| `ai_analysis_result` (**sessionStorage**) | triage handoff `/dashboard` → `/results` |

---

## 5. Schema change checklist

- [ ] Add `hospitals.foreign_pcare BOOLEAN DEFAULT FALSE` + import in `scripts/import_hospitals.py` *(Phase 4)*
- [ ] Decide `sos_alerts`: retire (A) vs repurpose (B) *(Phase 4)*
- [ ] Decide fate of `hospital_queue_status` + `/hospitals/{id}/queue` *(Phase 4)*
- [ ] Add bounding-box index usage / optional composite index on `(latitude, longitude)` *(Phase 4)*
- [ ] Drop tracked `__pycache__/*.pyc` from the repo and gitignore them — 8+ compiled files are currently versioned and showing as modified
