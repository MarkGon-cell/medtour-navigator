// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
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
        "/waiting-time": "http://127.0.0.1:8000",
        "/waiting-observations": "http://127.0.0.1:8000",
        "/profile": "http://127.0.0.1:8000",
        "/health": "http://127.0.0.1:8000",
        "/v1": "http://127.0.0.1:8000",
        // Frontend route is exactly /hospitals (list page); API paths are
        // /hospitals/<id>, /hospitals/nearby, etc. — trailing slash only.
        "^/hospitals/": "http://127.0.0.1:8000",
      },
    },
  },
});
