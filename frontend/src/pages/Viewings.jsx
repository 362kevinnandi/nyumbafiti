import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Calendar as CalendarIcon, MapPin, Phone, Mail, Building2 } from "lucide-react";

const STATUS_STYLES = {
  pending_payment: "bg-amber-50 text-amber-700 border-amber-200",
  scheduled: "bg-emerald-50 text-emerald-700 border-emerald-200",
  completed: "bg-zinc-100 text-zinc-700 border-zinc-200",
  cancelled: "bg-red-50 text-red-700 border-red-200",
};

export default function ViewingsPage() {
  const { user } = useAuth();
  const [viewings, setViewings] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const url = user.role === "landlord" ? "/viewings" : "/my-viewings";
    const r = await api.get(url);
    setViewings(r.data);
    setLoading(false);
  }, [user.role]);

  useEffect(() => { load(); }, [load]);

  const isLandlord = user.role === "landlord";

  return (
    <div data-testid="viewings-page">
      <PageHeader
        overline={isLandlord ? "Pipeline" : "My account"}
        title={isLandlord ? "Viewing Requests" : "My Viewings"}
      />

      {loading ? <div className="text-zinc-500">Loading...</div> : viewings.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <CalendarIcon className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">
            {isLandlord ? "No viewing requests yet" : "No viewings booked"}
          </div>
          <div className="text-sm text-zinc-500">
            {isLandlord
              ? "Once prospects book viewings from the public marketplace, they appear here."
              : (
                <>
                  Browse vacant properties on the{" "}
                  <Link to="/marketplace" className="text-zinc-950 font-semibold underline">marketplace</Link>{" "}
                  and book a viewing.
                </>
              )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="viewings-grid">
          {viewings.map((v) => (
            <div key={v.id} className="bg-white border border-zinc-200 rounded-md p-5 card-hover" data-testid={`viewing-card-${v.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="overline text-zinc-500 mb-1">{v.property_name} · Unit {v.unit_number}</div>
                  <div className="font-display font-bold text-lg leading-tight">
                    {v.scheduled_date} <span className="text-zinc-400">at</span> {v.scheduled_time}
                  </div>
                </div>
                <span className={`badge-status border ${STATUS_STYLES[v.status]}`}>
                  {v.status.replace("_", " ")}
                </span>
              </div>

              {isLandlord ? (
                <div className="space-y-2 text-sm border-t border-zinc-100 pt-3 mt-3">
                  <div className="flex items-center gap-2 text-zinc-700">
                    <span className="overline text-zinc-500 text-[10px] w-16">Prospect</span>
                    <span className="font-semibold">{v.prospect_name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-600">
                    <Phone className="w-3.5 h-3.5 text-zinc-400" />
                    <a href={`tel:${v.prospect_phone}`} className="font-mono-num">{v.prospect_phone}</a>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-600">
                    <Mail className="w-3.5 h-3.5 text-zinc-400" />
                    <a href={`mailto:${v.prospect_email}`}>{v.prospect_email}</a>
                  </div>
                  {v.notes && (
                    <div className="text-xs text-zinc-500 bg-zinc-50 rounded p-2 mt-2">{v.notes}</div>
                  )}
                </div>
              ) : (
                <div className="space-y-2 text-sm border-t border-zinc-100 pt-3 mt-3">
                  {v.property_address && (
                    <div className="flex items-start gap-2 text-zinc-600">
                      <MapPin className="w-3.5 h-3.5 text-zinc-400 mt-0.5" />
                      <span>{v.property_address}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-zinc-600">
                    <span className="overline text-zinc-500 text-[10px]">Fee paid</span>
                    <span className="font-mono-num font-semibold text-mpesa">{formatKES(v.viewing_fee)}</span>
                  </div>
                </div>
              )}

              <div className="overline text-zinc-400 text-[10px] mt-4 pt-3 border-t border-zinc-100">
                Booked {new Date(v.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLandlord && (
        <div className="mt-12 bg-white border border-zinc-200 rounded-md p-6 max-w-2xl">
          <Building2 className="w-6 h-6 text-zinc-400 mb-2" />
          <div className="font-display font-bold text-lg mb-1">Looking for more options?</div>
          <p className="text-sm text-zinc-600 mb-4">
            Hundreds of verified Nairobi units. Browse and book another viewing.
          </p>
          <Link to="/marketplace">
            <span className="inline-flex items-center gap-2 bg-zinc-950 text-white px-4 py-2 rounded-md text-sm font-semibold hover:bg-zinc-800">
              Explore listings
            </span>
          </Link>
        </div>
      )}
    </div>
  );
}
