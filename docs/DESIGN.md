# MedTour Design Language System (DLS)
## Product Vision: Instant Emergency Toolkit for Sick Travelers

---

## 1. Visual Strategy & Logic

When a traveler opens MedTour, they are likely in a state of high stress, pain, or panic. The design system must prioritize **extreme utility over aesthetic decoration**. Every visual decision directly serves cognitive ease, speed, and immediate physical action.

### Core Visual Principles
*   **Zero Ambiguity:** Icons, text labels, and buttons have one single, unmistakable meaning.
*   **High-Contrast Accessibility:** Interfaces must be readable in intense sunlight, dark hospital corridors, or through blurred, teary vision.
*   **Calm & Assertive Hierarchy:** Neutral backdrops anchor the interface, while critical actionable zones (like the SOS block) command absolute priority.

---

## 2. Color Palette & Accessibility

The colors are mapped mathematically to psychological states and functional priority.

| Token | Hex Code | System Purpose | Accessibility Ratio (WCAG) |
| :--- | :--- | :--- | :--- |
| **`color-emergency-red`** | `#D92D20` | SOS Buttons, critical alerts, life-threatening actions. | 4.5:1 on White |
| **`color-action-blue`** | `#1570EF` | Secondary actions, deep-links (Uber/Ola), interactive links. | 4.5:1 on White |
| **`color-surface-pure`** | `#FFFFFF` | Core application background, driver flashcards. | N/A |
| **`color-surface-neutral`** | `#F9FAFB` | Card backdrops, subtle section breaks. | N/A |
| **`color-text-primary`** | `#101828` | Absolute dark charcoal for high-readability text/headers. | 16:1 on White |
| **`color-text-secondary`** | `#475467` | Descriptive metadata, helper labels, instructions. | 7:1 on White |
| **`color-success-green`** | `#039855` | Completed appointments, valid receipt statuses. | 4.5:1 on White |

---

## 3. Typography & Scale

To maximize local scanning speed, the type scale relies exclusively on highly accessible, pre-installed system fonts (**San Francisco** for iOS, **Roboto** for Android) to avoid network-dependent font loading lag.

*   **Emergency Display (GPS / SOS Text):** `40pt` / Bold / Tracking: `-0.02em`
*   **Driver Card Headline (Hindi/Marathi):** `32pt` / Heavy / Tracking: `0`
*   **Primary Section Header:** `20pt` / Semi-Bold / Line Height: `28pt`
*   **Card Titles / Component Labels:** `16pt` / Medium / Line Height: `24pt`
*   **Body Copy / Metadata:** `14pt` / Regular / Line Height: `20pt`

---

## 4. UI/UX Interaction Component Specifications

### A. The "Zero-Onboarding" Launcher
*   **Behavior:** No authentication screen. On first install, initialization triggers a background asynchronous task generating a UUID saved purely to native local storage (`AsyncStorage` / `SharedPreferences`).
*   **UI State:** Immediately displays the main dashboard layout. A small 12pt banner at the absolute top of the screen reads: `● Local Guest Mode Active (No account required)`.

### B. The Persistent SOS Block
*   **Layout Structure:** Sits permanently at either the top 1/3 of the home dashboard or anchored as a distinct global interactive persistent card.
*   **Component Breakdown:**
    1.  **Red Primary Trigger (`#D92D20`):** Full-bleed width button reading `📞 Call Emergency Services (112)`. Tapping executes an immediate native hardware dialer sequence (`tel:112`).
    2.  **GPS Address Reader:** A high-contrast container (`#F9FAFB`) framing the active alphanumeric street location and latitude/longitude parameters. Includes a conspicuous `[Copy Address]` utility icon.
    3.  **Transit Transport Deep Link:** Dual segmented control button layout reading `🚗 Order Uber to ER` and `🛺 Order Ola to ER`. Tapping executes a direct deep-link URI Scheme injection with exact geo-coordinates of the closest flagged emergency room infrastructure pre-populated into the destination parameter slot.

### C. Driver Communication Flashcards ("Show the Driver")
*   **Interface Mechanics:** Activating this feature forces the mobile device hardware layer to override auto-dimming variables, instantly locking screen brightness parameters to `100%`.
*   **Visual Layout:** Reverses to pure white background (`#FFFFFF`) with pure black type (`#000000`). Fully expands to maximize edge-to-edge display boundaries, removing all navigation chrome, tab bars, or status bar indicators to maximize screen real estate.
*   **Localization Logic:** Utilizes real-time reverse-geocoding via local hardware GPS queries. If the localized administrative area translates to a specific state region, the UI dynamically loops and cascades language arrays (e.g., rendering English + Hindi + Marathi text blocks simultaneously when coordinates fall within Maharashtra borders).

### D. Minimal Walk-In Directory & Local Receipts
*   **Data Strategy:** Eradicates full-stack cross-platform medical database dependencies. Directory operates as an immutable read-only flat JSON dictionary containing verified geographical healthcare facilities, updated over a highly compressed lightweight CDN cache file.
*   **The Appointment Workflow:** "Booking" translates to saving a structural timestamp data object down into the client-side local device memory space. 
*   **The Three-Tab Receipt Stack:** 
    *   `Upcoming`: Displays active walk-in destination route cards with real-time ETA countdown matrix.
    *   `Completed`: Lists historical visit entries. Each card entry features an isolated, explicit button anchor labeled `📄 Download Insurance-Ready Receipt`.
    *   `Cancelled`: Flat historical list logs for reference.
*   **Receipt Export Framework:** Tapping the download anchor calls a localized programmatic string-to-PDF utility module that renders a clean structured grid layout with timestamp markers, facility tax registry numbers, local currency cost indicators, and medical symptom checklists structured to cleanly satisfy global travel insurance verification policies.
