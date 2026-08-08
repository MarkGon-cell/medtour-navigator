import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HeartPulse } from "lucide-react";
import api from "@/lib/api";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — MedTour" },
      {
        name: "description",
        content:
          "Create your MedTour account for AI-powered hospital discovery and travel-ready healthcare.",
      },
    ],
  }),
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
      await api.post("/auth/register", {
        full_name: `${firstName} ${lastName}`.trim(),
        email: email,
        password: password,
      });
  setSuccess("Registration successful! Redirecting to login...");

  setTimeout(() => {
    navigate({ to: "/login" });
  }, 2000);
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Unable to create account. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      {/* Registration Form */}
      <div className="flex items-center justify-center p-6 md:p-10">
        <Card className="w-full max-w-md border-0 shadow-none">
          <CardContent className="p-0">
            <div className="mb-8">
              <h1 className="text-3xl font-bold">
                Create your account
              </h1>

              <p className="mt-2 text-muted-foreground">
                Get personalized healthcare wherever you travel.
              </p>
            </div>

            <form
              className="space-y-4"
              onSubmit={handleRegister}
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">
                    First name
                  </Label>

                  <Input
                    id="firstName"
                    type="text"
                    value={firstName}
                    onChange={(e) =>
                      setFirstName(e.target.value)
                    }
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lastName">
                    Last name
                  </Label>

                  <Input
                    id="lastName"
                    type="text"
                    value={lastName}
                    onChange={(e) =>
                      setLastName(e.target.value)
                    }
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">
                  Email
                </Label>

                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.target.value)
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">
                  Password
                </Label>

                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) =>
                    setPassword(e.target.value)
                  }
                  required
                  minLength={6}
                />
              </div>

              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}
              {success && (
                <div className="rounded-md bg-success/10 p-3 text-sm text-success">
                  {success}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading
                  ? "Creating account..."
                  : "Create account"}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                Already have one?{" "}
                <Link
                  to="/login"
                  className="font-medium text-primary hover:underline"
                >
                  Sign in
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Right Side */}
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
            Your travel-ready health passport.
          </h2>

          <p className="mt-2 text-white/85">
            Free forever. No credit card required.
          </p>
        </div>

        <p className="text-xs text-white/70">
          © {new Date().getFullYear()} MedTour
        </p>
      </div>
    </div>
  );
}