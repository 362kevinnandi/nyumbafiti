import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Building2 } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome back, ${u.full_name}`);
      navigate(u.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      toast.error(formatApiError(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Hero panel */}
      <div className="hidden lg:flex relative overflow-hidden bg-zinc-950 text-white p-12 flex-col justify-between">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1596005554384-d293674c91d7?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="relative z-10 flex items-center gap-2">
          <Building2 className="w-6 h-6" strokeWidth={2} />
          <span className="font-display font-black text-xl tracking-tight">
            NYUMBA FITI
          </span>
        </div>
        <div className="relative z-10 space-y-6">
          <div className="overline text-zinc-400">Nairobi Property Operations</div>
          <h1 className="font-display font-black text-5xl leading-none tracking-tight">
            Run your rentals like a real estate fund.
          </h1>
          <p className="text-zinc-300 text-base max-w-md leading-relaxed">
            Collect rent via M-Pesa, track arrears, resolve tenant issues, and
            coordinate caretakers — all from one control panel.
          </p>
          <div className="flex gap-8 pt-4">
            <div>
              <div className="font-display font-black text-2xl">M-PESA</div>
              <div className="overline text-zinc-500">Native STK Push</div>
            </div>
            <div>
              <div className="font-display font-black text-2xl">24/7</div>
              <div className="overline text-zinc-500">Tenant Portal</div>
            </div>
          </div>
        </div>
        <div className="relative z-10 overline text-zinc-500">
          Built for Nairobi landlords · 2026
        </div>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center p-6 sm:p-12 bg-[#FAFAFA]">
        <div className="w-full max-w-sm space-y-8">
          <div className="lg:hidden flex items-center gap-2 mb-4">
            <Building2 className="w-6 h-6" />
            <span className="font-display font-black text-xl">NYUMBA FITI</span>
          </div>
          <div>
            <div className="overline text-zinc-500 mb-2">Sign in</div>
            <h2 className="font-display font-black text-4xl tracking-tight leading-none">
              Welcome back.
            </h2>
            <p className="text-sm text-zinc-500 mt-2">
              Enter your credentials to access your portal.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="email" className="overline text-zinc-600">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="login-email-input"
              />
            </div>
            <div>
              <Label htmlFor="password" className="overline text-zinc-600">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="login-password-input"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-md bg-zinc-950 hover:bg-zinc-800 text-white font-medium"
              data-testid="login-submit-button"
            >
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <div className="text-sm text-zinc-500 text-center">
            Don't have an account?{" "}
            <Link to="/register" className="text-zinc-950 font-semibold underline underline-offset-4" data-testid="register-link">
              Register as Landlord
            </Link>
          </div>

          <Link
            to="/marketplace"
            className="block border border-zinc-200 bg-white rounded-md p-3 text-sm hover:border-zinc-300 group"
            data-testid="marketplace-link-from-login"
          >
            <div className="overline text-zinc-500 mb-1">Looking for a home?</div>
            <div className="flex items-center justify-between">
              <span className="font-display font-bold text-zinc-950">Browse verified Nairobi listings</span>
              <span className="text-zinc-400 group-hover:text-zinc-950 group-hover:translate-x-0.5 transition-all">→</span>
            </div>
          </Link>

          <div className="border border-zinc-200 bg-white rounded-md p-3 text-xs text-zinc-600 space-y-1">
            <div className="overline text-zinc-500">Tenants / Caretakers</div>
            <p>Accounts are created by your landlord. Use the credentials they shared with you.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
