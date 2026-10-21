import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Toaster } from "@/components/ui/sonner";
import { MtrBackupPrompt } from "@/components/site/MtrBackupPrompt";

function NotFoundComponent() {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-16 font-sans">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="space-y-2">
          <p className="text-8xl font-black tracking-tighter text-foreground leading-none">
            404
          </p>
          <div className="mx-auto h-px w-16 bg-border" />
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-extrabold text-foreground">
            This page took a wrong turn
          </h1>
          <p className="text-sm font-medium text-muted-foreground leading-relaxed">
            The link may be broken or the page has moved. If this happened
            during an emergency, head straight back to the gateway.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/"
            className="inline-flex w-full sm:w-auto items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Back to Home
          </Link>
          <Link
            to="/walk-in"
            className="inline-flex w-full sm:w-auto items-center justify-center rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground transition-colors hover:bg-muted"
          >
            Find a Clinic
          </Link>
        </div>

        <p className="text-[11px] font-semibold text-muted-foreground">
          Error 404 · Page not found
        </p>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content" },
      { title: "MedTour — AI Healthcare Navigation for Travellers in India" },
      { name: "description", content: "Find verified hospitals, AI-powered recommendations and 24/7 emergency SOS for tourists across India." },
      { name: "author", content: "MedTour" },
      { property: "og:title", content: "MedTour — AI Healthcare Navigation" },
      { property: "og:description", content: "Verified hospitals, AI recommendations and SOS for travellers in India." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/nyx.png", type: "image/png" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
      {/* Every toast.*() call in the app is a no-op unless this is mounted.
          Pinned to the top because the bottom of every screen is occupied by
          the floating dock / MobileNav. */}
      <Toaster position="top-center" richColors closeButton />
      {/* Answers promptMtrBackup(): every mutation of the patient's local
          records raises it, because those records exist nowhere else. */}
      <MtrBackupPrompt />
    </QueryClientProvider>
  );
}
