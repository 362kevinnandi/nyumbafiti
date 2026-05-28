import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Plus, FileText, Trash2, Sparkles, Smartphone, CheckCircle2, Inbox, XCircle, HelpCircle } from "lucide-react";

const STATUS_STYLES = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  pending: "bg-zinc-100 text-zinc-700 border-zinc-200",
  awaiting_rent_receipt: "bg-sky-50 text-sky-700 border-sky-200",
  awaiting_landlord_confirmation: "bg-amber-50 text-amber-700 border-amber-200",
  overdue: "bg-red-50 text-red-700 border-red-200",
};

const STATUS_LABEL = {
  paid: "paid",
  partial: "partial",
  pending: "pending",
  awaiting_rent_receipt: "awaiting rent",
  awaiting_landlord_confirmation: "awaiting confirm",
  overdue: "overdue",
};

export default function BillsPage() {
  const { user } = useAuth();
  const isLandlord = user.role === "landlord";
  const [bills, setBills] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("all"); // landlord: "all" | "confirmations"
  const [confirmations, setConfirmations] = useState([]);
  const [form, setForm] = useState({
    tenant_id: "", unit_id: "", bill_type: "rent", amount: 0,
    period: new Date().toISOString().slice(0, 7),
    due_date: "", description: "",
  });

  const load = useCallback(async () => {
    const calls = [api.get("/bills")];
    if (isLandlord) {
      calls.push(api.get("/tenants"));
      calls.push(api.get("/units"));
      calls.push(api.get("/bills/pending-confirmations"));
    }
    const results = await Promise.all(calls);
    setBills(results[0].data);
    if (isLandlord) {
      setTenants(results[1].data);
      setUnits(results[2].data);
      setConfirmations(results[3].data || []);
    }
    setLoading(false);
  }, [isLandlord]);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/bills", { ...form, amount: Number(form.amount) });
      toast.success("Bill created");
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
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
      {user.role === "tenant" && user.approval_status === "pending" && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-md p-4 flex items-start gap-3" data-testid="tenant-pending-banner">
          <div className="w-2 h-2 rounded-full bg-amber-500 mt-2 animate-pulse" />
          <div>
            <div className="font-display font-bold text-amber-900">Account pending admin verification</div>
            <div className="text-sm text-amber-800 mt-1 leading-relaxed">
              Your landlord has added you, but you can't pay bills via M-Pesa until our platform admin verifies your account.
              This usually takes less than 24 hours and protects you from fraudulent billing.
            </div>
          </div>
        </div>
      )}
      {user.role === "tenant" && user.approval_status === "rejected" && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4" data-testid="tenant-rejected-banner">
          <div className="font-display font-bold text-red-900">Account rejected</div>
          <div className="text-sm text-red-800 mt-1">Your account has been rejected by the platform admin. Please contact support for help.</div>
        </div>
      )}
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

      {isLandlord && (
        <div className="mb-5 flex items-center gap-2 border-b border-zinc-200" data-testid="bills-tabs">
          <button
            type="button"
            onClick={() => setTab("all")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === "all" ? "border-zinc-950 text-zinc-950" : "border-transparent text-zinc-500 hover:text-zinc-800"}`}
            data-testid="bills-tab-all"
          >
            <FileText className="w-4 h-4 inline mr-1.5 -mt-0.5" /> All Bills
          </button>
          <button
            type="button"
            onClick={() => setTab("confirmations")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-1.5 ${tab === "confirmations" ? "border-zinc-950 text-zinc-950" : "border-transparent text-zinc-500 hover:text-zinc-800"}`}
            data-testid="bills-tab-confirmations"
          >
            <Inbox className="w-4 h-4" /> Confirmations
            {confirmations.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-amber-500 text-white text-[10px] font-bold" data-testid="bills-confirmations-count">
                {confirmations.length}
              </span>
            )}
          </button>
        </div>
      )}

      {isLandlord && tab === "confirmations" ? (
        <ConfirmationsPanel rows={confirmations} loading={loading} onChanged={load} />
      ) : loading ? <div className="text-zinc-500">Loading...</div> : bills.length === 0 ? (
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
                      <span className={`badge-status border ${STATUS_STYLES[b.status] || STATUS_STYLES.pending}`}>{STATUS_LABEL[b.status] || b.status}</span>
                      {!isLandlord && b.info_request_message && (
                        <div className="mt-1.5 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 max-w-[220px]" data-testid={`tenant-info-request-${b.id}`}>
                          <strong>Landlord needs info:</strong> {b.info_request_message}
                        </div>
                      )}
                      {!isLandlord && b.rent_receipt_rejection && b.status === "pending" && (
                        <div className="mt-1.5 text-[11px] text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1 max-w-[220px]" data-testid={`tenant-rejection-${b.id}`}>
                          <strong>Rejected:</strong> {b.rent_receipt_rejection}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!isLandlord && b.status !== "paid" && (
                        <PayDialog bill={b} onPaid={load} />
                      )}
                      {isLandlord && b.status === "awaiting_landlord_confirmation" && (
                        <ConfirmReceiptButton bill={b} onConfirmed={load} />
                      )}
                      {isLandlord && b.status !== "awaiting_landlord_confirmation" && (
                        <button onClick={() => deleteBill(b.id)} className="text-zinc-400 hover:text-red-600" data-testid={`delete-bill-${b.id}`}>
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
  const [submitting, setSubmitting] = useState(false);
  const [pollingPaymentId, setPollingPaymentId] = useState(null);
  const [status, setStatus] = useState(null);
  const [stkInfo, setStkInfo] = useState(null);
  const [feePaid, setFeePaid] = useState(bill.status === "awaiting_rent_receipt" || bill.status === "awaiting_landlord_confirmation");
  const [feeFailed, setFeeFailed] = useState(false);
  const [rentReceipt, setRentReceipt] = useState("");
  const [rentAmount, setRentAmount] = useState(bill.amount - bill.amount_paid);
  const [elapsed, setElapsed] = useState(0);

  const isRent = bill.bill_type === "rent";
  const billTypeLabel = bill.bill_type === "rent" ? "rent" : bill.bill_type === "water" ? "water bill" : bill.bill_type === "electricity" ? "electricity bill" : bill.bill_type === "service_charge" ? "service charge" : `${bill.bill_type} bill`;
  const recipientLabel = "landlord";

  const startFeePayment = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatus(null);
    setFeeFailed(false);
    setElapsed(0);
    try {
      const r = await api.post("/payments/mpesa/stk-push", { bill_id: bill.id, phone_number: phone });
      setStkInfo(r.data);
      setPollingPaymentId(r.data.payment_id);
      setStatus("Check your phone for the M-Pesa STK push prompt");
      const start = Date.now();
      const tick = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
      const interval = setInterval(async () => {
        try {
          const pr = await api.get(`/payments/${r.data.payment_id}`);
          if (pr.data.status === "succeeded") {
            clearInterval(interval); clearInterval(tick);
            setStatus("Service fee paid! Receipt: " + pr.data.mpesa_receipt);
            setFeePaid(true);
            toast.success("Service fee paid — now pay " + billTypeLabel + " to " + recipientLabel);
          } else if (pr.data.status === "failed") {
            clearInterval(interval); clearInterval(tick);
            setFeeFailed(true);
            setStatus("Payment did not go through: " + (pr.data.result_desc || "no response"));
            toast.error("STK push failed — try again");
          }
        } catch { /* keep polling */ }
        // After 25s, force a real Safaricom status query (truth, not assumption)
        if (Date.now() - start > 25_000 && Date.now() - start < 28_000) {
          try { await api.post(`/payments/${r.data.payment_id}/check`); } catch { /* ignore */ }
        }
      }, 2500);
      // Hard timeout at 100s
      setTimeout(() => { clearInterval(interval); clearInterval(tick); }, 100_000);
    } catch (err) {
      toast.error(formatApiError(err, "Failed to initiate"));
    } finally {
      setSubmitting(false);
    }
  };

  const cancelPending = async () => {
    if (!pollingPaymentId) return;
    try {
      await api.post(`/payments/${pollingPaymentId}/cancel`);
      setFeeFailed(true);
      setStatus("Payment cancelled — you can retry now");
    } catch (err) {
      toast.error(formatApiError(err, "Cancel failed"));
    }
  };

  const restart = () => {
    setPollingPaymentId(null);
    setStatus(null);
    setFeeFailed(false);
    setElapsed(0);
  };

  const submitReceipt = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/bills/${bill.id}/submit-rent-receipt`, {
        mpesa_receipt: rentReceipt.trim(),
        amount_paid: Number(rentAmount),
      });
      toast.success("Receipt submitted — waiting for " + recipientLabel + " to confirm");
      setOpen(false);
      onPaid();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to submit receipt"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) restart(); }}>
      <DialogTrigger asChild>
        <Button className="bg-mpesa hover:bg-mpesa text-white rounded-md h-8 text-xs" data-testid={`pay-bill-${bill.id}`}>
          <Smartphone className="w-3.5 h-3.5 mr-1" /> Pay
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-2xl">Pay {billTypeLabel}</DialogTitle>
          <DialogDescription>
            {bill.period} · Balance {formatKES(bill.amount - bill.amount_paid)}
          </DialogDescription>
        </DialogHeader>

        {/* STEP 1: pay flat KES 33 service fee */}
        {!feePaid && !pollingPaymentId && (
          <form onSubmit={startFeePayment} className="space-y-4 mt-2" data-testid="pay-fee-form">
            <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs">
              <div className="font-semibold text-amber-900 mb-1">Two-step payment</div>
              <ol className="text-amber-900/90 leading-relaxed list-decimal list-inside space-y-0.5">
                <li><strong>STK push now for the KES 33 service fee</strong> for using the platform for administration support.</li>
                <li><strong>Then pay {billTypeLabel}</strong> directly to your {recipientLabel}'s M-Pesa Paybill.</li>
              </ol>
            </div>
            <div>
              <Label className="overline">M-Pesa phone (your number)</Label>
              <Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712345678" className="mt-1 font-mono-num" data-testid="pay-phone-input" />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={submitting} className="bg-mpesa hover:bg-mpesa text-white w-full" data-testid="pay-fee-submit">
                <Smartphone className="w-4 h-4 mr-1.5" />
                {submitting ? "Sending..." : "Pay KES 33 service fee"}
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* In-flight STK — only when truly pending. Show failure state if Safaricom rejected. */}
        {!feePaid && pollingPaymentId && !feeFailed && (
          <div className="py-8 text-center space-y-3" data-testid="pay-fee-status">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 flex items-center justify-center">
              <Smartphone className="w-6 h-6 text-mpesa animate-pulse" />
            </div>
            <div className="font-display font-bold">{status}</div>
            <div className="text-xs text-zinc-500 font-mono-num">elapsed: {elapsed}s</div>
            {stkInfo && (
              <div className="text-xs text-zinc-500">
                Fee: {formatKES(stkInfo.service_fee_amount)} → Platform paybill {stkInfo.platform_paybill} / {stkInfo.platform_account}
              </div>
            )}
            <button type="button" onClick={cancelPending} className="text-xs text-zinc-500 hover:text-red-600 underline" data-testid="pay-cancel-button">
              Cancel and retry
            </button>
          </div>
        )}

        {/* Failure state */}
        {!feePaid && pollingPaymentId && feeFailed && (
          <div className="py-6 text-center space-y-3" data-testid="pay-fee-failed">
            <div className="w-12 h-12 mx-auto rounded-full bg-red-50 flex items-center justify-center">
              <Smartphone className="w-6 h-6 text-red-600" />
            </div>
            <div className="font-display font-bold text-lg">Payment didn't go through</div>
            <div className="text-sm text-red-700 max-w-sm mx-auto">{status}</div>
            <div className="text-xs text-zinc-500">Common reasons: cancelled the prompt, didn't enter PIN in time, insufficient M-Pesa balance.</div>
            <Button onClick={restart} className="bg-zinc-950 hover:bg-zinc-800" data-testid="pay-retry-button">Try again</Button>
          </div>
        )}

        {/* STEP 2: show landlord paybill + receipt form */}
        {feePaid && (
          <form onSubmit={submitReceipt} className="space-y-4 mt-2" data-testid="pay-rent-form">
            <div className="bg-emerald-50 border-2 border-emerald-200 rounded-md p-4 text-sm">
              <div className="font-display font-bold mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Fee paid · Now pay {billTypeLabel} to {recipientLabel}
              </div>
              <div className="text-xs space-y-1">
                <div>1. Open M-Pesa → <strong>Lipa na M-Pesa</strong> → <strong>Pay Bill</strong></div>
                <div>2. Business no.: <span className="font-mono-num font-bold">{stkInfo?.landlord_paybill || bill.landlord_paybill || "ASK LANDLORD"}</span></div>
                <div>3. Account no.: <span className="font-mono-num font-bold">{stkInfo?.landlord_account_number || bill.landlord_account_number || "ASK LANDLORD"}</span></div>
                <div>4. Amount: <span className="font-mono-num font-bold">{formatKES(stkInfo?.rent_amount || (bill.amount - bill.amount_paid))}</span></div>
                <div>5. Enter PIN → save the receipt code you get via SMS</div>
              </div>
            </div>
            <div>
              <Label className="overline">M-Pesa receipt code (from SMS)</Label>
              <Input required value={rentReceipt} onChange={(e) => setRentReceipt(e.target.value.toUpperCase())} placeholder="e.g. SGH7XYZ123" className="mt-1 font-mono-num uppercase" data-testid="pay-rent-receipt" />
            </div>
            <div>
              <Label className="overline">Amount paid (KES)</Label>
              <Input required type="number" min="1" value={rentAmount} onChange={(e) => setRentAmount(e.target.value)} className="mt-1 font-mono-num text-lg" data-testid="pay-rent-amount" />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={submitting} className="bg-zinc-950 hover:bg-zinc-800 w-full" data-testid="pay-receipt-submit">
                {submitting ? "Submitting..." : `Submit receipt for ${recipientLabel} confirmation`}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}


function ConfirmReceiptButton({ bill, onConfirmed }) {
  const [busy, setBusy] = useState(false);
  const confirm = async () => {
    if (!window.confirm(`Confirm receipt ${bill.rent_receipt_code} for KES ${bill.rent_receipt_amount}?`)) return;
    setBusy(true);
    try {
      await api.post(`/bills/${bill.id}/confirm-rent-receipt`);
      toast.success("Receipt confirmed — bill marked paid");
      onConfirmed();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setBusy(false);
    }
  };
  const reject = async () => {
    const reason = window.prompt("Reason for rejection?", "Receipt does not match");
    if (reason === null) return;
    setBusy(true);
    try {
      await api.post(`/bills/${bill.id}/reject-rent-receipt`, { reason });
      toast.success("Receipt rejected — tenant must re-submit");
      onConfirmed();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex gap-1 justify-end">
      <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs" onClick={confirm} disabled={busy} data-testid={`confirm-receipt-${bill.id}`}>
        <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Confirm
      </Button>
      <Button size="sm" variant="outline" className="h-8 text-xs text-red-600 hover:bg-red-50" onClick={reject} disabled={busy} data-testid={`reject-receipt-${bill.id}`}>
        Reject
      </Button>
    </div>
  );
}



function ConfirmationsPanel({ rows, loading, onChanged }) {
  const [dialog, setDialog] = useState(null); // { kind: 'reject'|'info', bill }
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const approve = async (bill) => {
    if (!window.confirm(`Confirm receipt ${bill.rent_receipt_code} for ${formatKES(bill.rent_receipt_amount)} from ${bill.tenant_name}?`)) return;
    try {
      await api.post(`/bills/${bill.id}/confirm-rent-receipt`);
      toast.success("Receipt confirmed — bill marked paid");
      onChanged();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const submitDialog = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      toast.error(dialog.kind === "reject" ? "Reason is required" : "Message is required");
      return;
    }
    setBusy(true);
    try {
      if (dialog.kind === "reject") {
        await api.post(`/bills/${dialog.bill.id}/reject-rent-receipt`, { reason: reason.trim() });
        toast.success("Receipt rejected — tenant must re-submit");
      } else {
        await api.post(`/bills/${dialog.bill.id}/request-info-rent-receipt`, { message: reason.trim() });
        toast.success("Info request sent to tenant");
      }
      setDialog(null);
      setReason("");
      onChanged();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="text-zinc-500" data-testid="confirmations-loading">Loading confirmations…</div>;

  if (!rows.length) {
    return (
      <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="confirmations-empty">
        <Inbox className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
        <div className="font-display font-bold text-lg mb-1">No pending confirmations</div>
        <div className="text-sm text-zinc-500 max-w-md mx-auto">
          When a tenant pays rent or any bill to your paybill and submits the M-Pesa receipt, it will appear here for you to approve, reject, or request more info.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="confirmations-table">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="bg-zinc-50 border-b border-zinc-200">
            <tr>
              <th className="text-left px-4 py-3 overline text-zinc-500">Tenant / Unit</th>
              <th className="text-left px-4 py-3 overline text-zinc-500">Bill</th>
              <th className="text-left px-4 py-3 overline text-zinc-500">M-Pesa receipt</th>
              <th className="text-right px-4 py-3 overline text-zinc-500">Amount</th>
              <th className="text-left px-4 py-3 overline text-zinc-500">Submitted</th>
              <th className="text-right px-4 py-3 overline text-zinc-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id} className="border-b border-zinc-100 hover:bg-zinc-50/50 align-top" data-testid={`confirmation-row-${b.id}`}>
                <td className="px-4 py-3">
                  <div className="font-semibold">{b.tenant_name || "—"}</div>
                  <div className="text-xs text-zinc-500">{b.property_name} · Unit {b.unit_number}</div>
                  {b.tenant_phone && <div className="text-xs text-zinc-400 font-mono-num">{b.tenant_phone}</div>}
                </td>
                <td className="px-4 py-3">
                  <div className="capitalize font-medium">{b.bill_type}</div>
                  <div className="text-xs text-zinc-500 font-mono-num">{b.period}</div>
                </td>
                <td className="px-4 py-3">
                  <div className="font-mono-num font-bold text-emerald-700">{b.rent_receipt_code || "—"}</div>
                  {b.info_request_message && (
                    <div className="text-[11px] text-amber-700 mt-1 max-w-[200px]">Info requested: {b.info_request_message}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono-num font-semibold">{formatKES(b.rent_receipt_amount || 0)}</td>
                <td className="px-4 py-3 text-xs text-zinc-600 font-mono-num">
                  {b.rent_receipt_submitted_at ? new Date(b.rent_receipt_submitted_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5 justify-end flex-wrap">
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs" onClick={() => approve(b)} data-testid={`approve-${b.id}`}>
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Approve
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-xs border-amber-300 text-amber-700 hover:bg-amber-50" onClick={() => { setDialog({ kind: "info", bill: b }); setReason(""); }} data-testid={`request-info-${b.id}`}>
                      <HelpCircle className="w-3.5 h-3.5 mr-1" /> Request info
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-xs border-red-300 text-red-700 hover:bg-red-50" onClick={() => { setDialog({ kind: "reject", bill: b }); setReason(""); }} data-testid={`reject-${b.id}`}>
                      <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!dialog} onOpenChange={(o) => { if (!o) { setDialog(null); setReason(""); } }}>
        <DialogContent className="rounded-md max-w-md" data-testid="confirmation-action-dialog">
          {dialog && (
            <>
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">
                  {dialog.kind === "reject" ? "Reject receipt" : "Request more info"}
                </DialogTitle>
                <DialogDescription>
                  {dialog.kind === "reject"
                    ? `Tenant ${dialog.bill.tenant_name} will be notified to re-submit a new receipt for ${dialog.bill.bill_type} (${dialog.bill.period}).`
                    : `Ask ${dialog.bill.tenant_name} for more details about M-Pesa receipt ${dialog.bill.rent_receipt_code}.`}
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={submitDialog} className="space-y-3 mt-2">
                <div>
                  <Label className="overline">
                    {dialog.kind === "reject" ? "Reason for rejection" : "What info do you need?"}
                  </Label>
                  <Textarea
                    required
                    rows={4}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={dialog.kind === "reject"
                      ? "e.g. Receipt code does not match any payment to my paybill"
                      : "e.g. Please share the M-Pesa SMS screenshot showing the timestamp"}
                    className="mt-1"
                    data-testid="confirmation-action-reason"
                  />
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => { setDialog(null); setReason(""); }}>Cancel</Button>
                  <Button
                    type="submit"
                    disabled={busy}
                    className={dialog.kind === "reject" ? "bg-red-600 hover:bg-red-700" : "bg-amber-600 hover:bg-amber-700"}
                    data-testid="confirmation-action-submit"
                  >
                    {busy ? "Sending…" : (dialog.kind === "reject" ? "Reject receipt" : "Send request")}
                  </Button>
                </DialogFooter>
              </form>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
