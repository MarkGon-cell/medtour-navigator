# MedTour Navigator

Medical-tourism navigation: find clinics, book a walk-in visit, carry your
records in an encrypted `.mtr` file — and complete a visit end-to-end with a
NMC-verified doctor who issues a QR you scan back into your own ledger.

- **Frontend** — React + TanStack Start/Router, Vite, Tailwind v4.
- **Backend** — FastAPI + SQLAlchemy, PostgreSQL.
- **Storage rule** — Postgres holds *hospital data, doctor data, SOS logs and
  appointment status only*. Diagnosis, prescription, notes, invoice detail and
  the visit lifecycle live on the patient's device (localStorage + IndexedDB)
  and in their `.mtr` file. QR codes and the mediclaim PDF are rendered by the
  backend, never by the browser.

---

## 1. Prerequisites

| Tool      | Notes                                             |
| --------- | ------------------------------------------------- |
| Node.js   | v20+ (`npm -v` to confirm)                        |
| Python    | 3.11+                                             |
| PostgreSQL| 14+ (the repo is developed against PG 16 in Docker) |

Optional but recommended:

- **Docker** — easiest way to run PostgreSQL.
- **ngrok** — an HTTPS tunnel so a real phone can open the app (camera and
  geolocation require a secure context; see §6).

---

## 2. Database

Using Docker:

```bash
docker run -d --name medtour-postgres ^
  -e POSTGRES_PASSWORD=your_password ^
  -e POSTGRES_DB=medtour_db ^
  -p 5432:5432 ^
  postgres:16
```

Without Docker, create the database by hand:

```sql
CREATE DATABASE medtour_db;
```

No migrations need to be run manually — on startup the backend converges the
schema itself (§5).

---

## 3. Backend setup

```bash
cd backend

# 1. virtual environment
python -m venv venv

# 2. activate — Windows
venv\Scripts\activate
#    macOS / Linux
# source venv/bin/activate

# 3. dependencies
pip install -r requirements.txt

# 4. configure
copy .env.example .env      # then edit the values
```

### Environment variables (`backend/.env`)

| Key | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | e.g. `postgresql://postgres:password@localhost:5432/medtour_db` |
| `SECRET_KEY` | yes | JWT signing key for doctor tokens |
| `ALGORITHM` | yes | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | yes | doctor session length |
| `NVIDIA_NIM_API_KEY` | for AI triage / transcription | |
| `GEOAPIFY_API_KEY` | for hospital geocoding | |
| `VERIFICATION_BASE_URL` | no | base URL printed in the QR on the mediclaim PDF. Defaults to `http://localhost:8080` — set it to wherever the frontend is served (`https://<lan-ip>:8080` or your ngrok domain) so a scanned code opens the right host. |

### Start it

```bash
uvicorn app.main:app --port 8000
```

> Use **`--port 8000`** — the Vite dev proxy targets it. Prefer **no
> `--reload`** while testing: startup loads the whisper model (~3 min), so a
> reload on every edit is expensive. Restart manually after backend changes.

Verify:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"MedTour Navigator"}
```

`/docs` serves the interactive OpenAPI UI.

### Startup migration

`app/main.py` runs two idempotent routines on import:

- `_ensure_discovery_columns()` — adds the hospitals provenance/rating columns
  and repairs the `id` sequence.
- `_ensure_appointment_columns()` — converges `appointments` onto the
  status-only schema: adds `appointment_code`, `patient_name`, `reason`,
  `hospital_name`, `doctor_name`, `is_completed`, `is_verified`; backfills them
  from the legacy columns; drops the clinical/lifecycle columns; sets
  `appointment_code NOT NULL` + a unique index; drops the `users` table.

Each backfill checks that its source column still exists, so the routine is
safe to run against a fresh database, a legacy one, and one that a previous
run already half-converted.

---

## 4. Frontend setup

```bash
# from the repo root
npm install
npm run dev
```

The dev server is **HTTPS** (`https://localhost:8080`) because `getUserMedia`
(camera, QR scanning, voice input) and the Geolocation API are blocked on plain
HTTP. The certificate is self-signed — click *Advanced → Proceed* once per
device.

API calls are proxied to FastAPI:

```
/doctor/  → http://127.0.0.1:8000      (note: ^/doctor/ , never bare /doctor —
/auth     → http://127.0.0.1:8000       bare /doctor is the portal *page*)
/appointments, /hospitals, /emergency, ... → http://127.0.0.1:8000
```

Other scripts:

```bash
npm run build     # production build
npm run lint      # eslint
npm run format    # prettier --write
```

---

## 5. Seeding a test doctor

Doctor registration verifies a registration number against NMC via
`https://api.askmydoc.in/`. When that upstream is unavailable, seed a doctor
that is already marked verified:

```bash
cd backend
venv\Scripts\activate
python scripts/seed_test_doctor.py
```

Credentials: **`test@medtour.in` / `Test@1234`**
(`id=1`, `verified=True`, `hospital_id=NULL` → receives every appointment).

Other useful scripts: `scripts/debug_appointments.py` prints the current
appointment rows; `scripts/verify_endpoints.py` smoke-tests the API.

---

## 6. Testing on a real phone (camera + geolocation)

Both APIs need a secure context. Two options:

1. **Same LAN** — open `https://<your-lan-ip>:8080` on the phone and accept the
   certificate warning. The Vite proxy forwards `/doctor/*` etc. to the laptop,
   so port 8000 does not need to be exposed.
2. **ngrok** — tunnel the dev server for a trusted HTTPS domain
   (`allowedHosts` already permits `*.ngrok-free.app`).

Set `VERIFICATION_BASE_URL` to the same public URL, otherwise the QR printed on
the mediclaim PDF points at `localhost`.

---

## 7. The doctor → patient flow

```
PATIENT                              SERVER                         DOCTOR
  |                                    |                              |
  |-- POST /appointments ------------->|                              |
  |   name + reason from .mtr          | mints MT-XXXXXXXX            |
  |<-- appointment_code ---------------|                              |
  |                                    |<-- GET /doctor/appointments -|
  |                                    |<-- POST /doctor/diagnosis ---|  dx + rx + notes
  |                                    |    (nothing persisted)       |  → QR PNG + payload
  |                                    |<-----------------------------|
  |                                    |                              |
  |  scans the QR  ---------------------------------------------->    |
  |-- POST /doctor/scan ---------------------------------------------->|
  |   qr_payload {code, id, dx, rx}    | code ↔ id must match         |
  |                                    | → is_completed = true        |
  |<-- success + status row -----------|                              |
  |                                    |                              |
  |-- POST /doctor/claim/purchase ---->| $15 once → is_verified=true  |
  |<-- base64 PDF (encrypted) ---------|                              |
  |-- GET /verificationStatus?aid= --->| public badge page            |
```

### API surface

**Public**

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/appointments` | booking; body is `patient_name` + `reason` + slot; server mints the id |
| `GET` | `/verificationStatus?aid=MT-XXXXXXXX` | the destination of the QR on the PDF: badge, doctor/hospital/patient/visit blocks. No clinical detail. |
| `POST` | `/emergency/sos` | anonymous SOS dispatch log |

**Doctor (JWT in `doctor_access_token`, `role: "doctor"`)**

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/doctor/auth/register` | NMC verification + account |
| `POST` | `/doctor/auth/login` | |
| `GET` | `/doctor/auth/me` | |
| `POST` | `/doctor/auth/reverify` | re-check the registration number |
| `GET` | `/doctor/appointments` | status-only rows for the portal |
| `POST` | `/doctor/diagnosis` | clinical trio in → `qr_payload` + `qr_image_base64` out; **nothing written to the DB** |
| `POST` | `/doctor/qr` | re-render an existing QR |
| `GET` | `/doctor/appointment/{code}` | one appointment |
| `POST` | `/doctor/scan` | marks `is_completed`; returns HTTP 200 with `success:false` + `notes` on any mismatch so the UI can explain the refusal |
| `POST` | `/doctor/claim/purchase` | one-time **$15** → `is_verified = true` + PDF |
| `POST` | `/doctor/claim/pdf` | free re-download once verified |
| `GET` | `/doctor/claim/{code}` | claim status |

---

## 8. Where the appointment id (`aid`) comes from

The `MT-2F0580F2`-style id is **derived, not random**. The hash lives in
`backend/app/services/appointment_code.py`:

```python
MT- + sha256(appointment_time | patient_name | hospital_name | client_ip)[:8].upper()
```

- Material is the `|`-joined tuple above; the digest is truncated to 8 hex
  chars (32 bits).
- `client_ip()` (same file) supplies the fourth ingredient — `X-Forwarded-For`
  if present, otherwise the socket address. It is used as hash material only
  and never stored.
- **The doctor's name is deliberately excluded**: no doctor is assigned at
  booking time (they stamp `doctor_name` when entering the diagnosis), and
  re-minting the id mid-flow would break the patient's QR ↔ upcoming-appointment
  match.
- Collisions are caught by a `taken` callable and disambiguated by re-hashing
  with a counter salt, so the id stays derived rather than falling back to
  randomness.

It is minted in `POST /appointments` (`backend/app/api/appointments.py`) and
appears on the portal badge, in the QR payload, and on the PDF.

---

## 9. The mediclaim PDF

`backend/app/services/claim_pdf.py` renders it with reportlab:

- MedTour letterhead, patient/doctor/hospital/reason/diagnosis/prescription/notes
  sections, `$15.00` invoice, **IS VERIFIED** badge once paid.
- QR at the bottom with the verification link beside it → opens
  `/verificationStatus?aid=…`.
- **Encrypted with the patient's `.mtr` password**, supplied by the client in
  the request body. reportlab 5 has no AES in `reportlab.lib.pdfencrypt`, so it
  uses `StandardEncryption(..., strength=128)` with print-only permissions.
- Everything that goes into it comes from the client (`/claim/purchase`,
  `/claim/pdf`); the server persists status only.

---

## 10. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `column "symptoms" does not exist` at startup | already fixed — each backfill now checks its source column; restart the backend |
| Portal shows stale routes (`/auth/login`, `/profile`) | an old uvicorn is still bound to 8000; kill it and restart |
| Camera / mic / geolocation dead | you are on plain HTTP — use `https://localhost:8080` or an ngrok tunnel (§6) |
| Geolocation `code=2` | permission denied or no location fix — expected on desktop; the app falls back to a default pin |
| Scanned QR says "not checked in" | the modal shows the server's `notes`: unknown code, or the QR's `id` does not match the code |
| `POST /appointments` → 401 | booking requires a docked `.mtr` (or an active medical profile) — there are no patient accounts |
| askmydoc returns 503 / HTTP 404 | NMC verification is upstream-down; seed the test doctor instead (§5) |
| pip exits 1 with "Target directory already exists" | harmless on this machine — packages land in the shared `E:\pythonPackages` target and are installed |

---

## 11. Repository layout

```
backend/
  app/
    api/            routers: appointments, doctor, doctor_auth, verification,
                    hospitals, emergency, ai_analysis, mtr_vault, ...
    services/       claim_pdf, qr_service, appointment_code, ...
    models/         appointment, hospital, sos_alert, ...
    schemas/        pydantic contracts
    main.py         app factory + startup migration
  scripts/          seeding, debugging, data prep
  requirements.txt
src/
  routes/           __root, landing, walk-in, doctor, visits, ...
  components/       visits/, site/, ui/, ...
  lib/              api, mtrDatabase, mtrSession, claimPdf, ...
```
