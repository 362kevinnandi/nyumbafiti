import { useCallback, useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Users, Home, Wallet, TrendingUp, Building, AlertTriangle, Percent } from "lucide-react";

function Stat({ label, value, accent, sub, icon: Icon, testId }) {
  return (
    <div
      className={`bg-white border rounded-md p-5 card-hover ${
        accent === "green" ? "border-emerald-200" : accent === "red" ? "border-red-200" : "border-zinc-200"
      }`}
      data-testid={testId}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="overline text-zinc-500">{label}</div>
        {Icon && <Icon className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />}
      </div>
      <div className={`font-display font-black text-3xl tracking-tight leading-none font-mono-num ${
        accent === "green" ? "text-emerald-600" : accent === "red" ? "text-red-600" : "text-zinc-950"
      }`}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-2">{sub}</div>}
    </div>
  );
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await api.get("/admin/stats");
    setStats(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading || !stats) return <div className="text-zinc-500">Loading platform stats...</div>;

  const ratePct = (stats.current_commission_rate * 100).toFixed(2);

  return (
    <div data-testid="admin-dashboard-page">
      <PageHeader overline="Super Admin" title="Platform Overview" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat testId="stat-pending-approvals" label="Pending Approvals" value={stats.pending_approvals_total} accent={stats.pending_approvals_total > 0 ? "red" : undefined} icon={AlertTriangle} sub={`${stats.pending_property_approvals} props · ${stats.pending_tenant_approvals} tenants · ${stats.pending_caretaker_approvals} caretakers`} />
        <Stat testId="stat-arrears" label="Platform Arrears" value={formatKES(stats.total_arrears)} accent="red" sub="Outstanding tenant balances" icon={AlertTriangle} />
        <Stat testId="stat-commission" label="Commission Earned" value={formatKES(stats.total_commission_earned)} accent="green" sub={`${ratePct}% of all transactions`} icon={Percent} />
        <Stat testId="stat-gross" label="Gross Processed" value={formatKES(stats.total_gross_processed)} icon={TrendingUp} sub={`${stats.successful_payments_count} successful payments`} />
        <Stat testId="stat-net-payouts" label="Owed to Landlords" value={formatKES(stats.total_net_to_landlords)} icon={Wallet} />
        <Stat testId="stat-users" label="Total Users" value={stats.total_users} icon={Users} sub={`${stats.users_by_role.landlord} landlords · ${stats.users_by_role.tenant} tenants`} />
        <Stat testId="stat-properties" label="Properties" value={stats.properties} icon={Building} />
        <Stat testId="stat-open-issues" label="Open Issues" value={stats.open_issues} icon={AlertTriangle} />
      </div>

      <div className="bg-white border border-zinc-200 rounded-md p-6">
        <div className="overline text-zinc-500 mb-4">Revenue by Source</div>
        <div className="space-y-3">
          {stats.by_purpose.map((row) => (
            <div key={row._id || "rent_bill"} className="flex items-center justify-between border-b border-zinc-100 pb-3 last:border-0">
              <div>
                <div className="font-semibold capitalize">{(row._id || "rent_bill").replace("_", " ")}</div>
                <div className="text-xs text-zinc-500">{row.count} transactions</div>
              </div>
              <div className="text-right">
                <div className="font-mono-num font-bold">{formatKES(row.gross)}</div>
                <div className="text-xs text-emerald-600 font-mono-num">+{formatKES(row.commission)} commission</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        <TipCard title="Set commission rate" body="Adjust your platform fee from Settings. Currently 3.5%." />
        <TipCard title="Trigger landlord payouts" body="See balances owed and mark M-Pesa B2C disbursements as paid." />
        <TipCard title="Suspend abusive accounts" body="From Users, suspend any account that violates terms." />
      </div>
    </div>
  );
}

function TipCard({ title, body }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-md p-5">
      <div className="font-display font-bold text-base mb-2">{title}</div>
      <div className="text-sm text-zinc-600 leading-relaxed">{body}</div>
    </div>
  );
}
