import { useCallback, useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const STATUS_STYLES = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  pending: "bg-zinc-100 text-zinc-700 border-zinc-200",
  overdue: "bg-red-50 text-red-700 border-red-200",
};

export default function AdminBillsPage() {
  const [bills, setBills] = useState([]);
  const [tab, setTab] = useState("unpaid");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/admin/bills");
    setBills(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const unpaid = bills.filter((b) => b.status !== "paid");
  const paid = bills.filter((b) => b.status === "paid");
  const totalUnpaid = unpaid.reduce((sum, b) => sum + (b.amount - b.amount_paid), 0);
  const totalCollected = paid.reduce((sum, b) => sum + b.amount_paid, 0);

  const renderTable = (rows) => (
    <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="admin-bills-table">
      <table className="w-full text-sm min-w-[800px]">
        <thead className="bg-zinc-50 border-b border-zinc-200">
          <tr>
            <th className="text-left px-4 py-3 overline text-zinc-500">Type / Period</th>
            <th className="text-left px-4 py-3 overline text-zinc-500">Tenant</th>
            <th className="text-left px-4 py-3 overline text-zinc-500">Landlord / Property</th>
            <th className="text-right px-4 py-3 overline text-zinc-500">Amount</th>
            <th className="text-right px-4 py-3 overline text-zinc-500">Paid</th>
            <th className="text-right px-4 py-3 overline text-zinc-500">Balance</th>
            <th className="text-left px-4 py-3 overline text-zinc-500">Due</th>
            <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const balance = b.amount - b.amount_paid;
            return (
              <tr key={b.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`admin-bill-row-${b.id}`}>
                <td className="px-4 py-3">
                  <div className="font-semibold capitalize">{b.bill_type}</div>
                  <div className="text-xs text-zinc-500 font-mono-num">{b.period}</div>
                </td>
                <td className="px-4 py-3 text-zinc-700">
                  <div>{b.tenant_name}</div>
                  <div className="text-xs text-zinc-500 font-mono-num">{b.tenant_phone}</div>
                </td>
                <td className="px-4 py-3 text-zinc-600 text-xs">
                  <div className="text-sm text-zinc-900 font-semibold">{b.landlord_name}</div>
                  <div>{b.property_name} · Unit {b.unit_number}</div>
                </td>
                <td className="px-4 py-3 text-right font-mono-num">{formatKES(b.amount)}</td>
                <td className="px-4 py-3 text-right font-mono-num text-emerald-600">{formatKES(b.amount_paid)}</td>
                <td className={`px-4 py-3 text-right font-mono-num font-semibold ${balance > 0 ? "text-red-600" : "text-zinc-400"}`}>{formatKES(balance)}</td>
                <td className="px-4 py-3 text-zinc-600 text-xs font-mono-num">{new Date(b.due_date).toLocaleDateString()}</td>
                <td className="px-4 py-3"><span className={`badge-status border ${STATUS_STYLES[b.status]}`}>{b.status}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div data-testid="admin-bills-page">
      <PageHeader overline="Super Admin" title="All Platform Bills" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-zinc-200 rounded-md p-5">
          <div className="overline text-zinc-500 mb-1">Total Unpaid Balance</div>
          <div className="font-display font-black text-2xl text-red-600 font-mono-num">{formatKES(totalUnpaid)}</div>
        </div>
        <div className="bg-white border border-zinc-200 rounded-md p-5">
          <div className="overline text-zinc-500 mb-1">Total Collected</div>
          <div className="font-display font-black text-2xl text-emerald-600 font-mono-num">{formatKES(totalCollected)}</div>
        </div>
        <div className="bg-white border border-zinc-200 rounded-md p-5">
          <div className="overline text-zinc-500 mb-1">Unpaid Bills</div>
          <div className="font-display font-black text-2xl font-mono-num">{unpaid.length}</div>
        </div>
        <div className="bg-white border border-zinc-200 rounded-md p-5">
          <div className="overline text-zinc-500 mb-1">Settled Bills</div>
          <div className="font-display font-black text-2xl font-mono-num">{paid.length}</div>
        </div>
      </div>

      {loading ? <div className="text-zinc-500">Loading...</div> : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-zinc-100 rounded-md mb-6">
            <TabsTrigger value="unpaid" data-testid="tab-unpaid">Unpaid ({unpaid.length})</TabsTrigger>
            <TabsTrigger value="paid" data-testid="tab-paid">Paid ({paid.length})</TabsTrigger>
            <TabsTrigger value="all" data-testid="tab-all">All ({bills.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="unpaid">{renderTable(unpaid)}</TabsContent>
          <TabsContent value="paid">{renderTable(paid)}</TabsContent>
          <TabsContent value="all">{renderTable(bills)}</TabsContent>
        </Tabs>
      )}
    </div>
  );
}
