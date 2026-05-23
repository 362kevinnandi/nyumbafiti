import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { RotateCcw } from "lucide-react";

const STATUS_STYLES = {
  succeeded: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  refunded: "bg-zinc-100 text-zinc-700 border-zinc-200",
  cancelled: "bg-zinc-100 text-zinc-700 border-zinc-200",
};

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await api.get("/admin/payments");
    setPayments(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="admin-payments-page">
      <PageHeader overline="Super Admin" title="All Platform Payments" />
      {loading ? <div className="text-zinc-500">Loading...</div> : (
        <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="admin-payments-table">
          <table className="w-full text-sm min-w-[800px]">
            <thead className="bg-zinc-50 border-b border-zinc-200">
              <tr>
                <th className="text-left px-4 py-3 overline text-zinc-500">Date</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Landlord</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Purpose</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Phone</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Gross</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Commission</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Net</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`admin-payment-row-${p.id}`}>
                  <td className="px-4 py-3 text-xs font-mono-num text-zinc-600">{new Date(p.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-zinc-700">{p.landlord_name}</td>
                  <td className="px-4 py-3 text-zinc-600 text-xs">{p.purpose || "rent_bill"}</td>
                  <td className="px-4 py-3 font-mono-num text-xs">{p.phone_number}</td>
                  <td className="px-4 py-3 text-right font-mono-num">{formatKES(p.amount)}</td>
                  <td className="px-4 py-3 text-right font-mono-num text-emerald-600">{formatKES(p.commission_amount || 0)}</td>
                  <td className="px-4 py-3 text-right font-mono-num">{formatKES(p.net_to_landlord || 0)}</td>
                  <td className="px-4 py-3"><span className={`badge-status border ${STATUS_STYLES[p.status]}`}>{p.status}</span></td>
                  <td className="px-4 py-3 text-right">
                    {p.status === "succeeded" && <RefundDialog payment={p} onRefunded={load} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RefundDialog({ payment, onRefunded }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/admin/payments/${payment.id}/refund`, { reason });
      toast.success("Marked as refunded");
      setOpen(false);
      onRefunded();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="text-xs h-8" data-testid={`refund-button-${payment.id}`}>
          <RotateCcw className="w-3 h-3 mr-1" /> Refund
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-xl">Refund Payment</DialogTitle>
          <DialogDescription>
            {formatKES(payment.amount)} · {payment.mpesa_receipt} · {payment.phone_number}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4 mt-2" data-testid="refund-form">
          <div>
            <Label className="overline">Reason</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Landlord no-show, duplicate payment..." className="mt-1" data-testid="refund-reason-input" />
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-900">
            This marks the payment as refunded in your records and rolls back the linked bill / viewing. You must send the actual M-Pesa refund manually via the M-Pesa for Business portal.
          </div>
          <DialogFooter>
            <Button type="submit" disabled={submitting} className="bg-red-600 hover:bg-red-700 text-white" data-testid="refund-submit-button">
              {submitting ? "Recording..." : "Mark refunded"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
