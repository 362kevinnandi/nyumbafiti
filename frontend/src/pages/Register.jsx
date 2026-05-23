import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Building2 } from "lucide-react";

export default function RegisterPage() {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register({ ...form, role: "landlord" });
      toast.success("Account created. Welcome!");
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex relative overflow-hidden bg-zinc-950 text-white p-12 flex-col justify-between">
        <div
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="relative z-10 flex items-center gap-2">
          <Building2 className="w-6 h-6" />
          <span className="font-display font-black text-xl tracking-tight">NYUMBA OS</span>
        </div>
        <div className="relative z-10 space-y-6">
          <div className="overline text-zinc-400">Start collecting rent today</div>
          <h1 className="font-display font-black text-5xl leading-none tracking-tight">
            One platform.<br/>Every unit.<br/>Zero spreadsheets.
          </h1>
        </div>
        <div className="relative z-10 overline text-zinc-500">Built for Nairobi · 2026</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12 bg-[#FAFAFA]">
        <div className="w-full max-w-sm space-y-8">
          <div>
            <div className="overline text-zinc-500 mb-2">Landlord registration</div>
            <h2 className="font-display font-black text-4xl tracking-tight leading-none">
              Create your account.
            </h2>
            <p className="text-sm text-zinc-500 mt-2">
              You'll be able to add properties, tenants and caretakers from your dashboard.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="register-form">
            <div>
              <Label className="overline text-zinc-600">Full name</Label>
              <Input
                required
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                placeholder="e.g. John Kamau"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="register-name-input"
              />
            </div>
            <div>
              <Label className="overline text-zinc-600">Email</Label>
              <Input
                required type="email"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                placeholder="you@example.com"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="register-email-input"
              />
            </div>
            <div>
              <Label className="overline text-zinc-600">Phone (Kenya)</Label>
              <Input
                required value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
                placeholder="0712345678"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="register-phone-input"
              />
            </div>
            <div>
              <Label className="overline text-zinc-600">Password</Label>
              <Input
                required type="password" minLength={6}
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                placeholder="At least 6 characters"
                className="mt-1.5 h-11 rounded-md border-zinc-300 bg-white"
                data-testid="register-password-input"
              />
            </div>
            <Button
              type="submit" disabled={loading}
              className="w-full h-11 rounded-md bg-zinc-950 hover:bg-zinc-800 text-white font-medium"
              data-testid="register-submit-button"
            >
              {loading ? "Creating account..." : "Create landlord account"}
            </Button>
          </form>

          <div className="text-sm text-zinc-500 text-center">
            Already have an account?{" "}
            <Link to="/login" className="text-zinc-950 font-semibold underline underline-offset-4" data-testid="login-link">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
