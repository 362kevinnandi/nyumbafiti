import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Coins, CheckCircle2, Clock } from "lucide-react";

export default function AdminDisbursementsPage() {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [target, setTarget] = useState(null); // disbursement row to mark paid
  const [form, setForm] = useState({ mpesa_receipt: "", note: "" });
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/disbursements");
      setRows(r.data.items || []);
      setSummary(r.data.summary || {});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const markPaid = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await api.post(`/admin/disbursements/${target.id}/mark-paid`, form);
      toast.success("Marked paid");
      setTarget(null);
      setForm({ mpesa_receipt: "", note: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="admin-disbursements-page">
      <PageHeader overline="Super Admin" title="Disbursements" />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <SummaryCard label="Caretakers owed (pending)" value={formatKES(summary.pending_caretaker_total || 0)} icon={Clock} tone="amber" testId="summary-pending" />
        <SummaryCard label="Caretakers paid (lifetime)" value={formatKES(summary.paid_caretaker_total || 0)} icon={CheckCircle2} tone="emerald" testId="summary-paid" />
        <SummaryCard label="Platform viewing revenue" value={formatKES(summary.platform_revenue_viewings || 0)} icon={Coins} tone="sky" testId="summary-revenue" />
      </div>

      <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="disbursements-table">
        {loading ? <div className="p-6 text-zinc-500">Loading...</div>
          : rows.length === 0 ? <div className="p-12 text-center text-zinc-500">No disbursements yet — caretaker shares will appear here after the first paid viewing.</div>
          : (
            <table className="w-full text-sm min-w-[700px]">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Created</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Kind</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Landlord</th>
                  <th className="text-right px-4 py-3 overline text-zinc-500">Gross</th>
                  <th className="text-right px-4 py-3 overline text-zinc-500">Caretaker</th>
                  <th className="text-right px-4 py-3 overline text-zinc-500">Platform</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`disb-row-${r.id}`}>
                    <td className="px-4 py-3 text-xs text-zinc-500 font-mono-num">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3"><span className="badge-status bg-zinc-100 text-zinc-700">{r.kind}</span></td>
                    <td className="px-4 py-3">{r.landlord_name}</td>
                    <td className="px-4 py-3 text-right font-mono-num">{formatKES(r.gross_amount)}</td>
                    <td className="px-4 py-3 text-right font-mono-num text-emerald-700 font-semibold">{formatKES(r.caretaker_share)}</td>
                    <td className="px-4 py-3 text-right font-mono-num text-zinc-600">{formatKES(r.platform_share)}</td>
                    <td className="px-4 py-3">
                      <span className={`badge-status ${r.status === "paid" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{r.status}</span>
                      {r.mpesa_receipt && <div className="text-[10px] text-zinc-500 font-mono-num mt-1">{r.mpesa_receipt}</div>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {r.status === "pending" && (
                        <Button size="sm" className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700" onClick={() => setTarget(r)} data-testid={`mark-paid-${r.id}`}>
                          Mark paid
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      <Dialog open={!!target} onOpenChange={(o) => !o && setTarget(null)}>
        <DialogContent className="rounded-md max-w-sm" data-testid="mark-paid-dialog">
          <DialogHeader>
            <DialogTitle className="font-display font-black text-2xl">Mark disbursement paid</DialogTitle>
            <DialogDescription>
              {target && `KES ${target.caretaker_share.toLocaleString()} to caretaker — record the M-Pesa B2C transaction code.`}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={markPaid} className="space-y-4">
            <div>
              <Label className="overline">M-Pesa B2C receipt (optional)</Label>
              <Input value={form.mpesa_receipt} onChange={(e) => setForm({ ...form, mpesa_receipt: e.target.value.toUpperCase() })} className="mt-1 font-mono-num" placeholder="e.g. SGH7XYZ123" data-testid="mark-paid-receipt" />
            </div>
            <div>
              <Label className="overline">Note (optional)</Label>
              <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="mt-1" data-testid="mark-paid-note" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setTarget(null)}>Cancel</Button>
              <Button type="submit" disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700" data-testid="mark-paid-submit">
                {submitting ? "Saving..." : "Confirm"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryCard({ label, value, icon: Icon, tone, testId }) {
  const tones = {
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-900",
    sky: "bg-sky-50 border-sky-200 text-sky-900",
  };
  return (
    <div className={`${tones[tone]} border rounded-md p-4`} data-testid={testId}>
      <Icon className="w-5 h-5 mb-2" />
      <div className="overline">{label}</div>
      <div className="font-display font-black text-2xl mt-1 font-mono-num">{value}</div>
    </div>
  );
}
