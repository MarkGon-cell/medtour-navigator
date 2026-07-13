import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HeartPulse } from "lucide-react";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — MedTour" },
      { name: "description", content: "Sign in to your MedTour account to access AI healthcare navigation." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <div className="relative hidden bg-gradient-hero p-10 text-white md:flex md:flex-col md:justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/15 backdrop-blur"><HeartPulse className="h-5 w-5" /></div>
          <span className="text-lg font-bold">MedTour</span>
        </Link>
        <div>
          <h2 className="text-3xl font-bold">Care that follows your journey.</h2>
          <p className="mt-2 text-white/85">Verified hospitals, AI recommendations and 24/7 SOS across India.</p>
        </div>
        <p className="text-xs text-white/70">© {new Date().getFullYear()} MedTour</p>
      </div>

      <div className="flex items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md rounded-2xl border-border/70 shadow-soft">
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold">Welcome back</h1>
            <p className="mt-1 text-sm text-muted-foreground">Sign in to continue your care journey.</p>
            <form className="mt-6 space-y-4" onSubmit={(e) => e.preventDefault()}>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" placeholder="you@example.com" />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  <a href="#" className="text-xs text-primary hover:underline">Forgot?</a>
                </div>
                <Input id="password" type="password" placeholder="••••••••" />
              </div>
              <Button className="w-full bg-gradient-hero text-white hover:opacity-95" size="lg">Sign in</Button>
            </form>
            <p className="mt-6 text-center text-sm text-muted-foreground">
              New to MedTour? <Link to="/register" className="font-medium text-primary hover:underline">Create an account</Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
