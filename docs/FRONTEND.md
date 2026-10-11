## 1. Page Inventory & Routes

Because MedTour is an instant guest-first emergency toolkit, the entire frontend consists of **4 flat routes** and **1 hardware-level modal overlay**:

1. **`/` (The Emergency Gateway / Home)**: Persistent SOS, live GPS address reader, transit deep links, and rapid triage triggers.
2. **`/driver-card` (Fullscreen "Show the Driver" Mode)**: Hardware-brightened, zero-chrome emergency flashcard.
3. **`/walk-in` (Urgent Care Clinic Directory)**: Flat-file curated directory of walk-in clinics, English availability, and queue estimates.
4. **`/visits` (Walk-In Tracker & Insurance Receipts)**: The 3-tab ledger (`Upcoming`, `Completed`, `Cancelled`) with client-side PDF receipt generation.
5. **Global Overlay: Quick Medical ID Modal**: Emergency contact, allergies, and blood type stored strictly in device local storage.

---

## 2. Page-by-Page Specifications & Responsive Layout

### Page 1: Emergency Gateway (`/`)

#### Mobile View (Default Canvas: 390px - 430px)

* **Status Bar Strip**: 24px subtle banner (`#F9FAFB`): `● Local Guest Mode Active (No account required)`.
* **The Persistent SOS Block** (Occupies the top 40% of viewport):
* Primary Button: `#D92D20` full-bleed block, 56px height, pure white text: `📞 Call Emergency Services (112)`.
* GPS Address Box: `#F9FAFB` container with `#EAECF0` 1px border. Displays:
* Pin Icon + Street name (`20pt Bold`, `#101828`).
* City, State & Coordinates (`14pt Regular`, `#475467`).
* Inline `[Copy]` action icon.




* **Transit Dispatch Bar**: 2-column grid button row (`#1570EF` outline/fill):
* `🚗 Uber to Nearest ER` | `🛺 Ola to Nearest ER`.


* **Rapid Action Grid** (2x2 grid below the SOS block):
* `[📢 Show Driver Card]` (Navigates to `/driver-card`).
* `[🏥 Find Walk-in Clinic]` (Navigates to `/walk-in`).
* `[📋 My Visits & Receipts]` (Navigates to `/visits`).
* `[🪪 My Medical ID]` (Opens local overlay).



#### Desktop View (`min-width: 1024px`)

* Centered maximum-width frame (`max-w-4xl`, 896px) flanked by `#F9FAFB` ambient background.
* **Two-Column Split**:
* **Left Column (50%)**: Persistent SOS block with sticky positioning. Large 40pt GPS readouts, Call 112 trigger, and ride-hail links.
* **Right Column (50%)**: Rapid triage shortcuts, nearest 3 verified 24/7 ER cards (with distance in km, trauma level, and direct phone link), and emergency contact quick-dial.



---

### Page 2: "Show the Driver" Card (`/driver-card`)

#### Mobile View

* **Hardware Behavior**: Triggers Screen Wake Lock API (`navigator.wakeLock.request('screen')`) and requests 100% display brightness.
* **Visuals**: Zero navigation chrome, no header, no bottom bar. Pure white background (`#FFFFFF`) with pitch-black type (`#000000`).
* **Content Stack**:
* Top (Exit): High-contrast `[ ✕ Close ]` pill pinned to top-right.
* Primary Local Script (`32pt Heavy`): Dual language cascade based on GPS state (e.g., Hindi + Marathi in Maharashtra):
> **"कृपया मुझे तुरंत नजदीकी अस्पताल के इमरजेंसी (ER) ले जाएं। मैं विदेशी पर्यटक हूँ और स्थानीय भाषा नहीं बोलता।"**
> **"कृपया मला ताबडतोब जवळच्या रुग्णालयाच्या इमर्जन्सी (ER) विभागात घेऊन चला."**


* Secondary English Translation (`16pt Regular`, `#475467`):
> *"Please take me to the nearest hospital Emergency Room immediately. I am a tourist and do not speak the local language."*


* Destination Anchor Box: Large block lettering displaying the name and local-script spelling of the nearest verified hospital ER.



#### Desktop View

* Renders as a dedicated kiosk-style preview modal centered on the screen with a "Send to Phone via QR" fallback so a user looking at a laptop can transfer the card to their phone screen.

---

### Page 3: Walk-In Urgent Care Directory (`/walk-in`)

#### Mobile View

* **Header**: Search bar + 1-tap symptom pills (`Food Poisoning / Dehydration`, `Minor Wound / Stitches`, `High Fever / Dengue`, `Prescription Refill`).
* **Facility List**: Compact, scannable cards sorted strictly by GPS distance (nearest first).
* **Card Anatomy**:
* Facility name + Distance (`16pt Medium`, e.g., *"Apex Care Clinic • 0.8 km"*).
* Badges: `English Speaking Staff`, `Cashless Travel Insurance Desk`, `Open Now`.
* Primary Action: `[Schedule Walk-in Arrival]` (1 tap).
* Secondary Actions: `[Directions (Google Maps)]` and `[Call Front Desk]`.





#### Desktop View

* Split-pane interface:
* **Left Pane (40%)**: Facility list and symptom filters with immediate live query matching.
* **Right Pane (60%)**: Interactive map view marking verified clinics, operating hours, English desk contact numbers, and turn-by-turn routes from current GPS coordinates.



---

### Page 4: My Visits & Insurance Receipts (`/visits`)

#### Mobile View

* **Segmented Navigation Tab**: 3-segment switcher across the top: `Upcoming` | `Completed` | `Cancelled`.
* **Tab 1: Upcoming**:
* Active visit card showing arrival estimate countdown timer, clinic address, and two buttons: `[Cancel Visit]` and `[Mark as Completed]`.


* **Tab 2: Completed**:
* List of historical clinic visits with date/time stamps.
* **Primary Action on Each Card**: Large `#039855` button: `📄 Download Insurance-Ready Receipt (PDF)`.


* **Tab 3: Cancelled**:
* Archived list with reason tags (`Resolved on own`, `Went elsewhere`).
* Action: `[Re-book Walk-in]`.



#### Desktop View

* Full tabular layout with sticky tabs on the left. The `Completed` view renders an inline PDF preview pane on the right side so users on laptops can view, review, and print their claim document directly for their insurer portal.

---

## 3. Component Interaction & State Behaviors

| Component | Default / No Interaction | On Hover / Focus (Desktop) | On Tap / Active (Mobile) | Error / Offline State |
| --- | --- | --- | --- | --- |
| **SOS Button (`#D92D20`)** | Full color, high-contrast text, pulsing subtle ring. | Brightness drops 10%, cursor changes to pointer. | Native haptic feedback (`navigator.vibrate([100, 50, 100])`), executes `tel:112`. | Still executes `tel:112` via hardware dialer (does not require internet). |
| **GPS Address Box** | Displays loading spinner until reverse geocode resolves. | Border highlights to `#1570EF`. | Copies formatted address + coordinates to clipboard; shows toast `"Address Copied"`. | Displays raw cached lat/lng: `19.4563° N, 72.7925° E` if reverse-geocoding fails. |
| **Uber / Ola Deep Links** | Blue pill button with app icon. | Underline on title, elevation increases to `shadow-md`. | Dispatches URI scheme (`uber://...` / `ola://...`). Falls back to web URL if app is absent. | Opens web fallback (`m.uber.com`) with lat/lng pre-filled. |
| **Driver Card Trigger** | Standard button in action grid. | Inverts icon color. | Requests Wake Lock, overrides brightness, transitions full-screen via zero-duration route push. | Falls back to cached local-language strings stored in client bundle. |
| **Walk-in Booking Button** | Outline button: `Schedule Arrival`. | Fills with `#1570EF`. | Direct write to client-side storage; triggers immediate redirect to `/visits?tab=upcoming`. | Saves to local queue with zero network latency. |
| **Download Receipt Button** | Solid green button: `Download PDF`. | Shifts to `#027A48`. | Runs client-side PDF builder and triggers immediate file download (`visit-claim-[id].pdf`). | Generates offline using embedded font and stored visit object. |

---

## 4. Navigation Flow & Page Linking Architecture

```
                    ┌───────────────────────────────┐
                    │       Page 1: / (Home)        │
                    │  Persistent SOS & GPS Reader  │
                    └───────────────┬───────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│Page 2:           │      │Page 3:           │       │Page 4:           │
│/driver-card      │      │/walk-in          │       │/visits           │
│Fullscreen Flash  │      │Directory & Search│       │3-Tab Status Hub  │
└────────┬─────────┘      └────────┬─────────┘       └────────┬─────────┘
         │                         │                          │
         │ (Close [✕])             │ (Schedule Walk-in)       │ (Back to Home)
         └─────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
                       Redirects to /visits?tab=upcoming

```

* **`/` to `/driver-card**`: Accessed via one-tap prominent card. Closing routes back to `/` without clearing any active state.
* **`/` to `/walk-in**`: Direct link. Users filter clinics and tap `Schedule Arrival`.
* **`/walk-in` to `/visits**`: Booking bypasses confirmation modals. It writes to local storage and immediately executes `router.push('/visits?tab=upcoming')`.
* **Global Header/Footer**: Mobile uses a fixed 3-tab bottom bar (`SOS`, `Clinics`, `My Visits`). Desktop uses a clean top navigation bar with the SOS trigger pinned to the right corner.

---

## 5. Client-Side State & Inter-Page Communication

Because the platform eliminates server-side user authentication, all pages synchronize in real time through **three browser APIs**:

```
                       ┌───────────────────────────────┐
                       │     Hardware Geolocation      │
                       │ (navigator.geolocation watch) │
                       └───────────────┬───────────────┘
                                       │ Live Coordinates
                                       ▼
                       ┌───────────────────────────────┐
                       │       Shared State Hub        │
                       │ (Zustand / Nano Stores Sync)  │
                       └───────┬───────────────┬───────┘
                               │               │
            Writes / Updates   │               │ Reads / Hydrates
                               ▼               ▼
┌──────────────────────────────────────┐     ┌──────────────────────────────────┐
│      Browser IndexedDB / Storage     │     │       Active View Listeners      │
│  - Active GPS & Nearest ER ID        │     │  - /: Updates address string     │
│  - Visits: [Upcoming/Done/Cancelled] │ ──► │  - /driver-card: Updates scripts │
│  - User Medical ID (Allergies/Blood) │     │  - /visits: Syncs tab badges     │
└──────────────────────────────────────┘     └──────────────────────────────────┘

```

1. **Reactive Geolocation Store (`Zustand` / `Nano Stores`)**:
* Initialized on root mount using `navigator.geolocation.watchPosition`.
* Updates state: `{ lat, lng, nearestHospital, localLanguages }`.
* When updated, `/driver-card` automatically re-computes its local language array without network queries.


2. **The Offline Visit Ledger (`IndexedDB` / `localStorage`)**:
* Stores the flat array of visits:
```json
[
  {
    "id": "v-1092",
    "facilityName": "Apollo Clinic Indiranagar",
    "status": "upcoming",
    "timestamp": 1728499200000,
    "symptoms": ["Acute Gastroenteritis", "Dehydration"],
    "cost": "₹1,200",
    "insuranceTaxId": "GSTIN29AAACA1234D1Z5"
  }
]

```


* Any change made on `/walk-in` writes here. `/visits` listens to storage events and updates badge counts instantly.


3. **In-Browser PDF Generator (`@react-pdf/renderer` or `jspdf`)**:
* When the user taps `Download Insurance-Ready Receipt` on `/visits`:
* It takes the record from local storage, pulls the tourist's Medical ID name and passport number (if filled in), formats it with official ICD-10 medical symptom checkboxes and GSTIN tax details, and downloads the PDF directly to the device file system without making a backend network request.