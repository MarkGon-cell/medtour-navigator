// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import basicSsl from "@vitejs/plugin-basic-ssl";

export default defineConfig({
  // HTTPS for the dev server. The Geolocation API and getUserMedia (the
  // walk-in microphone) are both restricted to secure contexts, and neither
  // Chrome nor Firefox can be configured to relax that: served from plain
  // http://192.168.x.x:8080 the browser grants the permission prompt and then
  // hands back an EMPTY position, so location and voice can never work over
  // the network. localhost and https:// are the only exemptions.
  //
  // The dev URL therefore becomes https://localhost:8080 and
  // https://<lan-ip>:8080. The certificate is self-signed, so each device
  // shows a one-time warning to click past (Advanced -> Proceed), and the
  // /api proxy to FastAPI keeps working unchanged.
  plugins: [basicSsl()],
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    server: {
      // Vite's host check blocks unknown Host headers (403). Allow the
      // ngrok tunnel domain so phones can load the app over HTTPS.
      allowedHosts: [".ngrok-free.app", ".ngrok.app", "localhost"],
      // Forward API calls to FastAPI so the app works through a single
      // ngrok HTTPS tunnel (frontend + backend on one URL, same-origin,
      // no CORS, no mixed-content blocking).
      proxy: {
        "/auth": "http://127.0.0.1:8000",
        "/ai": "http://127.0.0.1:8000",
        "/emergency": "http://127.0.0.1:8000",
        "/appointments": "http://127.0.0.1:8000",
        // The doctor PORTAL page is the frontend route /doctor (no trailing
        // segment); the API paths are /doctor/appointments, /doctor/diagnosis,
        // /doctor/auth/login, /doctor/claim/<code>, … — trailing slash only.
        // Proxying bare /doctor would send the page request to FastAPI (404).
        "^/doctor/": "http://127.0.0.1:8000",
        "/admin": "http://127.0.0.1:8000",
        "/waiting-time": "http://127.0.0.1:8000",
        "/waiting-observations": "http://127.0.0.1:8000",
        "/profile": "http://127.0.0.1:8000",
        "/health": "http://127.0.0.1:8000",
        "/v1": "http://127.0.0.1:8000",
        "/api": {
          target: "http://127.0.0.1:8000",
          rewrite: (path: string) => path.replace(/^\/api/, ""),
        },
        // Frontend route is exactly /hospitals (list page); API paths are
        // /hospitals/<id>, /hospitals/nearby, etc. — trailing slash only.
        "^/hospitals/": "http://127.0.0.1:8000",
      },
    },
  },
});
