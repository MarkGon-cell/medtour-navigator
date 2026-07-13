import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HeartPulse } from "lucide-react";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — MedTour" },
      { name: "description", content: "Create your MedTour account for AI-powered hospital discovery and travel-ready healthcare." },
    ],
  }),
  component: RegisterPage,
});

function RegisterPage() {
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <div className="flex items-center justify-center bg-background p-6 md:order-2">
        <Card className="w-full max-w-md rounded-2xl border-border/70 shadow-soft">
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold">Create your account</h1>
            <p className="mt-1 text-sm text-muted-foreground">Get personalized healthcare wherever you travel.</p>
            <form className="mt-6 space-y-4" onSubmit={(e) => e.preventDefault()}>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="first">First name</Label>
                  <Input id="first" placeholder="Aarav" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last">Last name</Label>
                  <Input id="last" placeholder="Shah" />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" placeholder="you@example.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" type="password" placeholder="At least 8 characters" />
              </div>
              <Button className="w-full bg-gradient-hero text-white hover:opacity-95" size="lg">Create account</Button>
            </form>
            <p className="mt-6 text-center text-sm text-muted-foreground">
              Already have one? <Link to="/login" className="font-medium text-primary hover:underline">Sign in</Link>
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="relative hidden bg-gradient-hero p-10 text-white md:flex md:flex-col md:justify-between md:order-1">
        <Link to="/" className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/15 backdrop-blur"><HeartPulse className="h-5 w-5" /></div>
          <span className="text-lg font-bold">MedTour</span>
        </Link>
        <div>
          <h2 className="text-3xl font-bold">Your travel-ready health passport.</h2>
          <p className="mt-2 text-white/85">Free forever. No credit card required.</p>
        </div>
        <p className="text-xs text-white/70">© {new Date().getFullYear()} MedTour</p>
      </div>
    </div>
  );
}
