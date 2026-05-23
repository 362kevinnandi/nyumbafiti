import { useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Home, Users, AlertTriangle, Wallet, Wrench, CheckCircle2 } from "lucide-react";

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

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => {
      setStats(r.data);
      setLoading(false);
    });
  }, []);

  const greet = `Good ${
    new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"
  }, ${user?.full_name?.split(" ")[0]}`;

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline={user.role + " · Nairobi"} title={greet} />

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
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard testId="stat-assigned" label="My Open Tickets" value={stats.assigned_open} icon={Wrench} />
          <StatCard testId="stat-unassigned" label="Unassigned (Available)" value={stats.unassigned_open} icon={AlertTriangle} accent="red" />
          <StatCard testId="stat-resolved" label="Resolved" value={stats.resolved} accent="green" icon={CheckCircle2} />
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
