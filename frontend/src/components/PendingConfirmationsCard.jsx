import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Receipt, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Dashboard widget for landlord/caretaker/admin showing bills awaiting their confirmation
 * after a tenant has submitted an M-Pesa receipt. One-click Confirm/Reject inline.
 */
export default function PendingConfirmationsCard() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/bills/pending-confirmations");
      setItems(r.data || []);
    } catch (err) {
      // Quiet failure on dashboard — non-critical widget
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const confirm = async (bill) => {
    if (!window.confirm(`Confirm KES ${bill.rent_receipt_amount?.toLocaleString()} from ${bill.tenant_name}?\n\nM-Pesa code: ${bill.rent_receipt_code}`)) return;
    setBusyId(bill.id);
    try {
      await api.post(`/bills/${bill.id}/confirm-rent-receipt`);
      toast.success("Confirmed — bill marked paid");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to confirm"));
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (bill) => {
    const reason = window.prompt(`Reject receipt ${bill.rent_receipt_code}? Reason for ${bill.tenant_name}:`, "Receipt code not found in my M-Pesa SMS");
    if (reason === null) return;
    setBusyId(bill.id);
    try {
      await api.post(`/bills/${bill.id}/reject-rent-receipt`, { reason });
      toast.success("Rejected — tenant notified to re-submit");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to reject"));
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return null;
  if (items.length === 0) return null;

  return (
    <div className="mb-8 bg-white border-2 border-amber-200 rounded-md overflow-hidden" data-testid="pending-confirmations-card">
      <div className="bg-amber-50 px-4 py-3 border-b border-amber-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Receipt className="w-5 h-5 text-amber-700" />
          <h3 className="font-display font-bold text-base">
            Pending confirmations
            <span className="ml-2 badge-status bg-amber-200 text-amber-900" data-testid="pending-count">{items.length}</span>
          </h3>
        </div>
        <Link to="/bills" className="text-xs text-zinc-600 hover:text-zinc-950 flex items-center gap-1">
          See all <ChevronRight className="w-3 h-3" />
        </Link>
      </div>
      <div className="divide-y divide-zinc-100">
        {items.slice(0, 5).map((b) => (
          <div key={b.id} className="px-4 py-3 flex items-center justify-between gap-3" data-testid={`pending-row-${b.id}`}>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm truncate">{b.tenant_name} <span className="font-normal text-zinc-500">· {b.property_name} {b.unit_number}</span></div>
              <div className="text-xs text-zinc-600 mt-0.5">
                <span className="badge-status bg-zinc-100 text-zinc-700 mr-1">{b.bill_type}</span>
                <span className="font-mono-num font-semibold text-zinc-900">{formatKES(b.rent_receipt_amount)}</span>
                <span className="mx-1.5 text-zinc-300">·</span>
                <span className="font-mono-num">{b.rent_receipt_code}</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <Button
                size="sm"
                disabled={busyId === b.id}
                onClick={() => confirm(b)}
                className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700"
                data-testid={`pending-confirm-${b.id}`}
              >
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Confirm
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busyId === b.id}
                onClick={() => reject(b)}
                className="h-8 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                data-testid={`pending-reject-${b.id}`}
              >
                <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
              </Button>
            </div>
          </div>
        ))}
      </div>
      {items.length > 5 && (
        <div className="px-4 py-2 bg-zinc-50 border-t border-zinc-100 text-xs text-zinc-600 text-center">
          +{items.length - 5} more on the <Link to="/bills" className="font-semibold underline">Bills page</Link>
        </div>
      )}
    </div>
  );
}
