import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Building2, ShieldCheck, MapPin, User, Phone, Clock, CheckCircle2, AlertTriangle } from "lucide-react";

const STATUS_STYLE = {
  active: { bg: "from-emerald-50 to-white", badge: "bg-emerald-100 text-emerald-800 border-emerald-200", label: "VALID" },
  used: { bg: "from-zinc-100 to-white", badge: "bg-zinc-100 text-zinc-700 border-zinc-200", label: "USED" },
  expired: { bg: "from-amber-50 to-white", badge: "bg-amber-100 text-amber-800 border-amber-200", label: "EXPIRED" },
  cancelled: { bg: "from-red-50 to-white", badge: "bg-red-100 text-red-700 border-red-200", label: "CANCELLED" },
};

const fmt = (t) => {
  if (!t) return "—";
  const d = new Date(t);
  return isNaN(d.getTime()) ? String(t) : d.toLocaleString();
};

export default function PassViewPage() {
  const { token } = useParams();
  const [pass, setPass] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/public/pass/${token}`)
      .then((r) => setPass(r.data))
      .catch((e) => setError(e?.response?.status === 404 ? "Pass not found or invalid." : "Could not load this pass."))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-zinc-500" data-testid="pass-loading">Loading pass...</div>;

  if (error || !pass) {
    return (
      <div className="min-h-screen bg-warm flex items-center justify-center px-4" data-testid="pass-error">
        <div className="bg-white border border-red-200 rounded-md p-8 max-w-md text-center">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <div className="font-display font-black text-2xl mb-2">Pass not available</div>
          <div className="text-sm text-zinc-600 mb-4">{error}</div>
          <a href="/" className="text-sm font-semibold text-zinc-950 hover:underline">Back to homepage</a>
        </div>
      </div>
    );
  }

  const s = STATUS_STYLE[pass.status] || STATUS_STYLE.active;
  return (
    <div className={`min-h-screen bg-gradient-to-b ${s.bg}`} data-testid="pass-view-page">
      <header className="bg-white border-b border-zinc-200">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-zinc-950 rounded-md flex items-center justify-center">
              <Building2 className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display font-black text-base tracking-tight leading-none">NYUMBA FITI</div>
              <div className="overline text-zinc-500 text-[10px] mt-0.5">Visitor Entry Pass</div>
            </div>
          </div>
          <span className={`badge-status border ${s.badge}`} data-testid="pass-status-badge">{s.label}</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="bg-white border-2 border-emerald-200 rounded-2xl p-6 sm:p-8 shadow-sm" data-testid="pass-card">
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck className="w-5 h-5 text-emerald-700" />
            <span className="overline text-emerald-800">Show at the gate</span>
          </div>
          <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tight leading-none mb-1" data-testid="pass-visitor-name">
            {pass.visitor_name}
          </h1>
          <div className="text-sm text-zinc-500 mb-6">
            {pass.is_prospect_pass ? "Viewing entry pass — bring the ID you signed up with" : "Visitor entry pass"}
          </div>

          <div className="flex flex-col sm:flex-row gap-6 items-start">
            <img
              src={pass.qr_data_url}
              alt="Entry QR code"
              className="w-56 h-56 bg-white border border-zinc-100 rounded-md shrink-0 mx-auto sm:mx-0"
              data-testid="pass-qr-image"
            />
            <div className="flex-1 min-w-0 space-y-3 text-sm">
              {pass.property_name && (
                <div className="flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
                  <div>
                    <div className="overline text-zinc-500 text-[10px]">Property</div>
                    <div className="font-semibold" data-testid="pass-property-name">{pass.property_name}</div>
                    <div className="text-xs text-zinc-600">{pass.property_address}</div>
                  </div>
                </div>
              )}
              {pass.host_name && (
                <div className="flex items-start gap-2">
                  <User className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
                  <div>
                    <div className="overline text-zinc-500 text-[10px]">Host</div>
                    <div className="font-semibold" data-testid="pass-host-name">{pass.host_name}</div>
                  </div>
                </div>
              )}
              {pass.visitor_phone && (
                <div className="flex items-start gap-2">
                  <Phone className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
                  <div>
                    <div className="overline text-zinc-500 text-[10px]">Visitor phone</div>
                    <a href={`tel:${pass.visitor_phone}`} className="font-mono-num font-semibold">{pass.visitor_phone}</a>
                  </div>
                </div>
              )}
              <div className="flex items-start gap-2">
                <Clock className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
                <div>
                  <div className="overline text-zinc-500 text-[10px]">Expected</div>
                  <div className="font-semibold" data-testid="pass-expected">{fmt(pass.expected_time)}</div>
                  <div className="text-xs text-zinc-500">Expires {fmt(pass.expires_at)}</div>
                </div>
              </div>
              {pass.status === "used" && (
                <div className="flex items-start gap-2 pt-2 border-t border-zinc-100">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                  <div>
                    <div className="overline text-emerald-700 text-[10px]">Logged in</div>
                    <div className="font-semibold text-emerald-700">{fmt(pass.used_at)}</div>
                    {pass.used_by_caretaker_name && (
                      <div className="text-xs text-zinc-600">by {pass.used_by_caretaker_name}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {pass.notes && (
            <div className="mt-6 border-t border-zinc-100 pt-4 text-xs text-zinc-600">
              <div className="overline text-zinc-500 mb-1">Notes</div>
              {pass.notes}
            </div>
          )}

          <div className="mt-6 border-t border-zinc-100 pt-4 text-[10px] text-zinc-500 font-mono break-all" data-testid="pass-token">
            Token: {pass.token}
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-zinc-500">
          Anyone with this link can view the pass. Don't share publicly.
        </div>
      </main>
    </div>
  );
}
