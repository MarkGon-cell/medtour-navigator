import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HeartPulse } from "lucide-react";
import api from "@/lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — MedTour" },
      {
        name: "description",
        content:
          "Sign in to your MedTour account to access AI healthcare navigation.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setSuccess("");
    setLoading(true);

    try {
      // FastAPI OAuth2PasswordRequestForm expects form data
      const formData = new URLSearchParams();

      formData.append("username", email);
      formData.append("password", password);

      const response = await api.post("/auth/login", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      const { access_token } = response.data;

      // Store JWT token
      localStorage.setItem("access_token", access_token);

      setSuccess("Login successful! Redirecting...");

      setTimeout(() => {
        navigate({ to: "/dashboard" });
      }, 1000);
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Unable to sign in. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      {/* Left Side */}
      <div className="relative hidden bg-gradient-hero p-10 text-white md:flex md:flex-col md:justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/15 backdrop-blur">
            <HeartPulse className="h-5 w-5" />
          </div>

          <span className="text-lg font-bold">
            MedTour
          </span>
        </Link>

        <div>
          <h2 className="text-3xl font-bold">
            Care that follows your journey.
          </h2>

          <p className="mt-2 text-white/85">
            Verified hospitals, AI recommendations and 24/7 SOS across India.
          </p>
        </div>

        <p className="text-xs text-white/70">
          © {new Date().getFullYear()} MedTour
        </p>
      </div>

      {/* Login Form */}
      <div className="flex items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md rounded-2xl border-border/70 shadow-soft">
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold">
              Welcome back
            </h1>

            <p className="mt-1 text-sm text-muted-foreground">
              Sign in to continue your care journey.
            </p>

            <form
              className="mt-6 space-y-4"
              onSubmit={handleLogin}
            >
              <div className="space-y-2">
                <Label htmlFor="email">
                  Email
                </Label>

                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">
                    Password
                  </Label>

                  <a
                    href="#"
                    className="text-xs text-primary hover:underline"
                  >
                    Forgot?
                  </a>
                </div>

                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              {success && (
                <div className="rounded-md bg-green-500/10 p-3 text-sm text-green-600">
                  {success}
                </div>
              )}

              <Button
                type="submit"
                className="w-full bg-gradient-hero text-white hover:opacity-95"
                size="lg"
                disabled={loading}
              >
                {loading ? "Signing in..." : "Sign in"}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              New to MedTour?{" "}
              <Link
                to="/register"
                className="font-medium text-primary hover:underline"
              >
                Create an account
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}