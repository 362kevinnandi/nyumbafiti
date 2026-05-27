import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Home, Users, AlertTriangle, Wallet, Wrench, CheckCircle2, QrCode, ShieldCheck } from "lucide-react";

function formatPassTime(t) {
  if (!t) return "—";
  const d = new Date(t);
  if (!isNaN(d.getTime())) return d.toLocaleString();
  return String(t);
}

function StatCard({ label, value, sub, accent, testId, icon: Icon }) {
  return (
    <div
      className={`bg-white border rounded-md p-5 card-hover ${
        accent === "red"
          ? "border-red-200"
          : accent === "green"
          ? "border-emerald-200"
          : "border-zinc-200"
      }`}
      data-testid={testId}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="overline text-zinc-500">{label}</div>
        {Icon && <Icon className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />}
      </div>
      <div
        className={`font-display font-black text-3xl tracking-tight leading-none font-mono-num ${
          accent === "red"
            ? "text-red-600"
            : accent === "green"
            ? "text-emerald-600"
            : "text-zinc-950"
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-zinc-500 mt-2">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [prospectPasses, setProspectPasses] = useState([]);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => {
      setStats(r.data);
      setLoading(false);
    });
    if (user.role === "prospect") {
      api.get("/visitor-passes")
        .then((r) => setProspectPasses((r.data || []).filter((p) => p.status === "active")))
        .catch(() => {});
    }
  }, [user.role]);

  const greet = `Good ${
    new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"
  }, ${user?.full_name?.split(" ")[0]}`;

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline={user.role + " · Nairobi"} title={greet} />

      {user.role === "prospect" && prospectPasses.length > 0 && (
        <div className="mb-8 bg-gradient-to-br from-emerald-50 to-white border-2 border-emerald-300 rounded-md p-6" data-testid="prospect-qr-banner">
          <div className="flex flex-col sm:flex-row items-start gap-6">
            <img
              src={prospectPasses[0].qr_data_url}
              alt="Your viewing entry pass QR"
              className="w-44 h-44 bg-white border border-emerald-100 rounded-md shrink-0"
              data-testid="prospect-qr-image"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck className="w-5 h-5 text-emerald-700" />
                <span className="overline text-emerald-800">Your viewing entry pass</span>
              </div>
              <h2 className="font-display font-black text-2xl sm:text-3xl tracking-tight mb-2">
                Show this QR at the gate
              </h2>
              <p className="text-sm text-zinc-700 leading-relaxed mb-4">
                Auto-issued by NyumbaOS after your viewing payment. Valid for 24 hours.
                Security will scan it on arrival — carry the same ID you signed up with.
              </p>
              <div className="flex flex-wrap gap-2 text-xs text-zinc-600">
                <span className="badge-status bg-emerald-50 text-emerald-800 border border-emerald-200">VALID</span>
                <span>Expected: <span className="font-mono-num font-semibold">{formatPassTime(prospectPasses[0].expected_time)}</span></span>
              </div>
              <div className="mt-4 flex gap-2">
                <Link to="/visitors">
                  <button className="text-xs font-semibold px-3 h-8 rounded-md bg-zinc-950 text-white hover:bg-zinc-800 flex items-center gap-1.5" data-testid="prospect-view-all-passes-button">
                    <QrCode className="w-3.5 h-3.5" /> View all my passes
                  </button>
                </Link>
                <Link to="/viewings">
                  <button className="text-xs font-semibold px-3 h-8 rounded-md border border-zinc-300 bg-white hover:bg-zinc-50" data-testid="prospect-view-viewings-button">
                    My Viewings
                  </button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {loading || !stats ? (
        <div className="text-zinc-500">Loading stats...</div>
      ) : user.role === "landlord" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard testId="stat-properties" label="Properties" value={stats.properties} icon={Home} />
          <StatCard testId="stat-units" label="Units" value={stats.units} sub={`${stats.occupied_units} occupied · ${stats.vacant_units} vacant`} icon={Home} />
          <StatCard testId="stat-tenants" label="Active Tenants" value={stats.tenants} icon={Users} />
          <StatCard testId="stat-issues" label="Open Issues" value={stats.open_issues} icon={Wrench} />
          <StatCard testId="stat-arrears" label="Arrears" value={formatKES(stats.arrears)} accent="red" icon={AlertTriangle} sub="Outstanding balances" />
          <StatCard testId="stat-collected" label="Total Collected" value={formatKES(stats.total_collected)} accent="green" icon={Wallet} sub="All-time M-Pesa receipts" />
        </div>
      ) : user.role === "tenant" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard testId="stat-arrears" label="Outstanding" value={formatKES(stats.arrears)} accent={stats.arrears > 0 ? "red" : "green"} icon={Wallet} sub={stats.arrears > 0 ? "Pay now via M-Pesa" : "All clear"} />
          <StatCard testId="stat-pending-bills" label="Pending Bills" value={stats.pending_bills} icon={AlertTriangle} />
          <StatCard testId="stat-paid-bills" label="Bills Settled" value={stats.paid_bills} accent="green" icon={CheckCircle2} />
          <StatCard testId="stat-open-issues" label="Open Issues" value={stats.open_issues} icon={Wrench} />
        </div>
      ) : user.role === "caretaker" ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard testId="stat-assigned" label="My Open Tickets" value={stats.assigned_open} icon={Wrench} />
          <StatCard testId="stat-unassigned" label="Unassigned (Available)" value={stats.unassigned_open} icon={AlertTriangle} accent="red" />
          <StatCard testId="stat-resolved" label="Resolved" value={stats.resolved} accent="green" icon={CheckCircle2} />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard testId="stat-total-viewings" label="Total Bookings" value={stats.total_viewings} icon={Home} />
          <StatCard testId="stat-scheduled" label="Scheduled" value={stats.scheduled} accent="green" icon={CheckCircle2} />
          <StatCard testId="stat-pending" label="Awaiting Payment" value={stats.pending} icon={AlertTriangle} />
          <StatCard testId="stat-completed" label="Completed" value={stats.completed} icon={CheckCircle2} />
        </div>
      )}

      <div className="mt-12">
        <div className="overline text-zinc-500 mb-4">Quick Tips</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {user.role === "landlord" && (
            <>
              <TipCard title="Add your first property" body="Start by creating a property and then add units within it." />
              <TipCard title="Onboard tenants" body="Assign a tenant to each unit — they get a login automatically." />
              <TipCard title="Generate monthly bills" body="One click creates rent invoices for all occupied units." />
            </>
          )}
          {user.role === "tenant" && (
            <>
              <TipCard title="Pay rent in 3 taps" body="Open Bills → tap Pay → enter M-Pesa PIN on your phone." />
              <TipCard title="Report an issue" body="Burst pipe? Broken lock? Open a ticket and the caretaker will be notified." />
              <TipCard title="Track every shilling" body="Every M-Pesa payment is logged with a Safaricom receipt code." />
            </>
          )}
          {user.role === "caretaker" && (
            <>
              <TipCard title="Pick up unassigned tickets" body="Tickets without an owner are waiting for you." />
              <TipCard title="Update status in real time" body="Mark issues in progress so tenants stay informed." />
              <TipCard title="Communicate clearly" body="Use the issue messages to coordinate visit times." />
            </>
          )}
          {user.role === "prospect" && (
            <>
              <TipCard title="Track your viewings" body="See upcoming appointments and caretaker contact details in one place." />
              <TipCard title="Browse more listings" body="Hundreds of verified Nairobi units. Book additional viewings anytime." />
              <TipCard title="Same fee, same flow" body="Every viewing is KES 200 — secured and tracked." />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TipCard({ title, body }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-md p-5 card-hover">
      <div className="font-display font-bold text-base mb-2">{title}</div>
      <div className="text-sm text-zinc-600 leading-relaxed">{body}</div>
    </div>
  );
}
