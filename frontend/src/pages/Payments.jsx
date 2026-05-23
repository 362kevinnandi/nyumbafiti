import { useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { CreditCard, CheckCircle2, XCircle, Clock } from "lucide-react";

const STATUS_ICON = {
  succeeded: CheckCircle2,
  failed: XCircle,
  pending: Clock,
  cancelled: XCircle,
};

const STATUS_STYLES = {
  succeeded: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-zinc-100 text-zinc-700 border-zinc-200",
};

export default function PaymentsPage() {
  const { user } = useAuth();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/payments").then((r) => { setPayments(r.data); setLoading(false); });
  }, []);

  const isLandlord = user.role === "landlord";

  return (
    <div data-testid="payments-page">
      <PageHeader
        overline={isLandlord ? "Cash flow" : "History"}
        title={isLandlord ? "Payments Received" : "Payment History"}
      />
      {loading ? <div className="text-zinc-500">Loading...</div> : payments.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <CreditCard className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No payments yet</div>
          <div className="text-sm text-zinc-500">Payments will appear here once M-Pesa transactions complete.</div>
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="payments-table">
          <table className="w-full text-sm min-w-[600px]">
            <thead className="bg-zinc-50 border-b border-zinc-200">              <tr>
                <th className="text-left px-4 py-3 overline text-zinc-500">Date</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Phone</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Receipt</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Gross</th>
                {isLandlord && <th className="text-right px-4 py-3 overline text-zinc-500">Fee</th>}
                {isLandlord && <th className="text-right px-4 py-3 overline text-zinc-500">Net to You</th>}
                {!isLandlord && <th className="text-right px-4 py-3 overline text-zinc-500">Amount</th>}
                <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => {
                const Icon = STATUS_ICON[p.status] || Clock;
                return (
                  <tr key={p.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`payment-row-${p.id}`}>
                    <td className="px-4 py-3 text-xs font-mono-num text-zinc-600">{new Date(p.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono-num">{p.phone_number}</td>
                    <td className="px-4 py-3 font-mono-num text-xs text-zinc-600">{p.mpesa_receipt || "—"}</td>
                    <td className="px-4 py-3 text-right font-mono-num font-semibold">{formatKES(p.amount)}</td>
                    {isLandlord && <td className="px-4 py-3 text-right font-mono-num text-zinc-500 text-xs">−{formatKES(p.commission_amount || 0)}</td>}
                    {isLandlord && <td className="px-4 py-3 text-right font-mono-num text-emerald-600 font-bold">{formatKES(p.net_to_landlord || p.amount)}</td>}
                    {!isLandlord && <td className="px-4 py-3 text-right font-mono-num font-semibold">{formatKES(p.amount)}</td>}
                    <td className="px-4 py-3">
                      <span className={`badge-status border ${STATUS_STYLES[p.status]}`}>
                        <Icon className="w-3 h-3" /> {p.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
