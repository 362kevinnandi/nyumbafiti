import { useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, FileText, Trash2, Sparkles, Smartphone, CheckCircle2 } from "lucide-react";

const STATUS_STYLES = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  pending: "bg-zinc-100 text-zinc-700 border-zinc-200",
  overdue: "bg-red-50 text-red-700 border-red-200",
};

export default function BillsPage() {
  const { user } = useAuth();
  const isLandlord = user.role === "landlord";
  const [bills, setBills] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    tenant_id: "", unit_id: "", bill_type: "rent", amount: 0,
    period: new Date().toISOString().slice(0, 7),
    due_date: "", description: "",
  });

  const load = async () => {
    const calls = [api.get("/bills")];
    if (isLandlord) {
      calls.push(api.get("/tenants"));
      calls.push(api.get("/units"));
    }
    const results = await Promise.all(calls);
    setBills(results[0].data);
    if (isLandlord) {
      setTenants(results[1].data);
      setUnits(results[2].data);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/bills", { ...form, amount: Number(form.amount) });
      toast.success("Bill created");
      setOpen(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const generateMonthly = async () => {
    if (!window.confirm("Generate rent bills for all occupied units for this month?")) return;
    try {
      const r = await api.post("/bills/generate-monthly");
      toast.success(`${r.data.created} bills created (${r.data.skipped} already existed)`);
      load();
    } catch (err) {
      toast.error("Failed to generate");
    }
  };

  const deleteBill = async (id) => {
    if (!window.confirm("Delete this bill?")) return;
    await api.delete(`/bills/${id}`);
    toast.success("Deleted");
    load();
  };

  return (
    <div data-testid="bills-page">
      <PageHeader
        overline={isLandlord ? "Billing" : "My Account"}
        title={isLandlord ? "Bills & Invoices" : "My Bills"}
        action={
          isLandlord && (
            <div className="flex gap-2">
              <Button onClick={generateMonthly} variant="outline" className="rounded-md" data-testid="generate-monthly-button">
                <Sparkles className="w-4 h-4 mr-1.5" /> Generate Monthly Rent
              </Button>
              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="add-bill-button">
                    <Plus className="w-4 h-4 mr-1.5" /> New Bill
                  </Button>
                </DialogTrigger>
                <DialogContent className="rounded-md">
                  <DialogHeader>
                    <DialogTitle className="font-display font-black text-2xl">New Bill</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={create} className="space-y-4 mt-2" data-testid="bill-form">
                    <div>
                      <Label className="overline">Tenant</Label>
                      <select required value={form.tenant_id} onChange={(e) => {
                        const t = tenants.find((tt) => tt.id === e.target.value);
                        setForm({...form, tenant_id: e.target.value, unit_id: t?.unit_id || ""});
                      }} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="bill-tenant-select">
                        <option value="">Select tenant...</option>
                        {tenants.map((t) => <option key={t.id} value={t.id}>{t.full_name} — {t.property_name} {t.unit_number}</option>)}
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="overline">Bill type</Label>
                        <select value={form.bill_type} onChange={(e) => setForm({...form, bill_type: e.target.value})} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="bill-type-select">
                          <option value="rent">Rent</option><option value="water">Water</option><option value="electricity">Electricity</option><option value="service">Service charge</option><option value="other">Other</option>
                        </select>
                      </div>
                      <div><Label className="overline">Amount (KES)</Label><Input required type="number" value={form.amount} onChange={(e) => setForm({...form, amount: e.target.value})} className="mt-1" data-testid="bill-amount-input" /></div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div><Label className="overline">Period</Label><Input required type="month" value={form.period} onChange={(e) => setForm({...form, period: e.target.value})} className="mt-1" data-testid="bill-period-input" /></div>
                      <div><Label className="overline">Due date</Label><Input required type="date" value={form.due_date} onChange={(e) => setForm({...form, due_date: e.target.value})} className="mt-1" data-testid="bill-due-input" /></div>
                    </div>
                    <div><Label className="overline">Description</Label><Input value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} className="mt-1" /></div>
                    <DialogFooter>
                      <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="bill-submit-button">Create bill</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          )
        }
      />

      {loading ? <div className="text-zinc-500">Loading...</div> : bills.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <FileText className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No bills</div>
          <div className="text-sm text-zinc-500">{isLandlord ? "Create your first bill or generate monthly rent." : "You're all clear right now."}</div>
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="bills-table">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-zinc-50 border-b border-zinc-200">
              <tr>
                <th className="text-left px-4 py-3 overline text-zinc-500">Type / Period</th>
                {isLandlord && <th className="text-left px-4 py-3 overline text-zinc-500">Tenant / Unit</th>}
                <th className="text-right px-4 py-3 overline text-zinc-500">Amount</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Paid</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Balance</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Due</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => {
                const balance = b.amount - b.amount_paid;
                return (
                  <tr key={b.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`bill-row-${b.id}`}>
                    <td className="px-4 py-3">
                      <div className="font-semibold capitalize">{b.bill_type}</div>
                      <div className="text-xs text-zinc-500 font-mono-num">{b.period}</div>
                    </td>
                    {isLandlord && (
                      <td className="px-4 py-3 text-zinc-600">
                        <div>{b.tenant_name}</div>
                        <div className="text-xs text-zinc-400">Unit {b.unit_number}</div>
                      </td>
                    )}
                    <td className="px-4 py-3 text-right font-mono-num">{formatKES(b.amount)}</td>
                    <td className="px-4 py-3 text-right font-mono-num text-emerald-600">{formatKES(b.amount_paid)}</td>
                    <td className={`px-4 py-3 text-right font-mono-num font-semibold ${balance > 0 ? "text-red-600" : "text-zinc-400"}`}>{formatKES(balance)}</td>
                    <td className="px-4 py-3 text-zinc-600 text-xs font-mono-num">{new Date(b.due_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <span className={`badge-status border ${STATUS_STYLES[b.status]}`}>{b.status}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!isLandlord && b.status !== "paid" && (
                        <PayDialog bill={b} onPaid={load} />
                      )}
                      {isLandlord && (
                        <button onClick={() => deleteBill(b.id)} className="text-zinc-400 hover:text-red-600">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
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

function PayDialog({ bill, onPaid }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState(user.phone || "");
  const [amount, setAmount] = useState(bill.amount - bill.amount_paid);
  const [submitting, setSubmitting] = useState(false);
  const [pollingPaymentId, setPollingPaymentId] = useState(null);
  const [status, setStatus] = useState(null);

  const startPay = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatus(null);
    try {
      const r = await api.post("/payments/mpesa/stk-push", {
        bill_id: bill.id, phone_number: phone, amount: Number(amount),
      });
      setPollingPaymentId(r.data.payment_id);
      setStatus(r.data.demo_mode ? "Demo M-Pesa STK Push — auto-confirming..." : "Check your phone for the M-Pesa prompt");
      // poll
      const interval = setInterval(async () => {
        try {
          const pr = await api.get(`/payments/${r.data.payment_id}`);
          if (pr.data.status === "succeeded") {
            clearInterval(interval);
            setStatus("Payment received! Receipt: " + pr.data.mpesa_receipt);
            toast.success("Payment successful!");
            setTimeout(() => { setOpen(false); onPaid(); }, 1500);
          } else if (pr.data.status === "failed") {
            clearInterval(interval);
            setStatus("Payment failed: " + (pr.data.result_desc || "unknown error"));
            toast.error("Payment failed");
          }
        } catch {}
      }, 2000);
      setTimeout(() => clearInterval(interval), 90000);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to initiate");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setPollingPaymentId(null); setStatus(null); } }}>
      <DialogTrigger asChild>
        <Button className="bg-mpesa hover:bg-mpesa text-white rounded-md h-8 text-xs" data-testid={`pay-bill-${bill.id}`}>
          <Smartphone className="w-3.5 h-3.5 mr-1" /> Pay
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-2xl">Pay with M-Pesa</DialogTitle>
          <DialogDescription>
            {bill.bill_type.toUpperCase()} · {bill.period} · Balance {formatKES(bill.amount - bill.amount_paid)}
          </DialogDescription>
        </DialogHeader>
        {!pollingPaymentId ? (
          <form onSubmit={startPay} className="space-y-4 mt-2" data-testid="pay-form">
            <div><Label className="overline">M-Pesa phone (Kenya)</Label><Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712345678" className="mt-1 font-mono-num" data-testid="pay-phone-input" /></div>
            <div><Label className="overline">Amount (KES)</Label><Input required type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="mt-1 font-mono-num text-lg" data-testid="pay-amount-input" /></div>
            <DialogFooter>
              <Button type="submit" disabled={submitting} className="bg-mpesa hover:bg-mpesa text-white" data-testid="pay-submit-button">
                <Smartphone className="w-4 h-4 mr-1.5" />
                {submitting ? "Sending..." : `Pay ${formatKES(amount)}`}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="py-8 text-center space-y-3" data-testid="pay-status">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 flex items-center justify-center">
              {status?.includes("received") ? <CheckCircle2 className="w-6 h-6 text-emerald-600" /> : <Smartphone className="w-6 h-6 text-mpesa animate-pulse" />}
            </div>
            <div className="font-display font-bold">{status}</div>
            <div className="text-xs text-zinc-500">Payment ID: <span className="font-mono-num">{pollingPaymentId.slice(0, 8)}</span></div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
