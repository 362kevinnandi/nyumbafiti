import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import ExportMenu from "@/components/ExportMenu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Send } from "lucide-react";

export default function AdminPayoutsPage() {
  const [tab, setTab] = useState("owed");
  const [owed, setOwed] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [a, b] = await Promise.all([
      api.get("/admin/payouts"),
      api.get("/admin/payouts/history"),
    ]);
    setOwed(a.data);
    setHistory(b.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="admin-payouts-page">
      <PageHeader overline="Super Admin" title="Landlord Payouts" action={<ExportMenu resource="payouts" testIdPrefix="payouts-export" />} />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-zinc-100 rounded-md mb-6">
          <TabsTrigger value="owed" data-testid="tab-owed">Balances Owed ({owed.filter(r => r.balance_owed > 0).length})</TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">Payout History ({history.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="owed">
          {loading ? <div className="text-zinc-500">Loading...</div> : owed.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white text-zinc-500">No payments yet — payouts will appear here.</div>
          ) : (
            <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="payouts-table">
              <table className="w-full text-sm min-w-[750px]">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Landlord</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Gross Earned</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Commission</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Already Paid</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Balance Owed</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {owed.map((r) => (
                    <tr key={r.landlord_id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`payout-row-${r.landlord_id}`}>
                      <td className="px-4 py-3">
                        <div className="font-semibold">{r.landlord_name}</div>
                        <div className="text-xs text-zinc-500 font-mono-num">{r.landlord_phone}</div>
                      </td>
                      <td className="px-4 py-3 text-right font-mono-num">{formatKES(r.gross_earned)}</td>
                      <td className="px-4 py-3 text-right font-mono-num text-emerald-600">{formatKES(r.commission_taken)}</td>
                      <td className="px-4 py-3 text-right font-mono-num text-zinc-500">{formatKES(r.already_paid_out)}</td>
                      <td className={`px-4 py-3 text-right font-mono-num font-bold ${r.balance_owed > 0 ? "text-zinc-950" : "text-zinc-400"}`}>{formatKES(r.balance_owed)}</td>
                      <td className="px-4 py-3 text-right">
                        {r.balance_owed > 0 && (
                          <MarkPaidDialog landlord={r} onSaved={load} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="history">
          {loading ? <div className="text-zinc-500">Loading...</div> : history.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white text-zinc-500">No payouts recorded yet.</div>
          ) : (
            <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Date</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Landlord</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Amount</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id} className="border-b border-zinc-100">
                      <td className="px-4 py-3 text-xs font-mono-num text-zinc-600">{new Date(h.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3 font-semibold">{h.landlord_name}</td>
                      <td className="px-4 py-3 text-right font-mono-num">{formatKES(h.amount)}</td>
                      <td className="px-4 py-3 text-zinc-600 text-xs">{h.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MarkPaidDialog({ landlord, onSaved }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(landlord.balance_owed);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/admin/payouts/${landlord.landlord_id}/mark-paid`, {
        amount: Number(amount), note,
      });
      toast.success("Payout recorded");
      setOpen(false);
      onSaved();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="bg-zinc-950 hover:bg-zinc-800 text-xs h-8" data-testid={`pay-landlord-${landlord.landlord_id}`}>
          <Send className="w-3 h-3 mr-1" /> Mark paid
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-xl">Record Payout</DialogTitle>
          <DialogDescription>
            Pay {landlord.landlord_name} · Balance: {formatKES(landlord.balance_owed)}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4 mt-2" data-testid="payout-form">
          <div><Label className="overline">Amount (KES)</Label><Input required type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="mt-1 font-mono-num" data-testid="payout-amount-input" /></div>
          <div><Label className="overline">M-Pesa reference / note</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. M-Pesa B2C ref NXX123" className="mt-1" data-testid="payout-note-input" /></div>
          <div className="bg-zinc-50 border border-zinc-200 rounded-md p-3 text-xs text-zinc-600">
            This records the payout in your books. You must send the actual money via M-Pesa B2C / Bulk Disbursement.
          </div>
          <DialogFooter>
            <Button type="submit" disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="payout-submit-button">
              {submitting ? "Recording..." : "Record payout"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
