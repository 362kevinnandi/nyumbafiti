import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Percent, Wallet, Calendar } from "lucide-react";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    platform_paybill: "",
    platform_account: "",
    service_fee_pct: "",
    viewing_caretaker_share: "",
    viewing_platform_share: "",
    commission_rate: "",
  });

  const load = useCallback(async () => {
    const r = await api.get("/admin/settings");
    setSettings(r.data);
    setForm({
      platform_paybill: r.data.platform_paybill || "247247",
      platform_account: r.data.platform_account || "0740479864",
      service_fee_pct: ((r.data.service_fee_pct || 0.025) * 100).toFixed(2),
      viewing_caretaker_share: r.data.viewing_caretaker_share || 150,
      viewing_platform_share: r.data.viewing_platform_share || 50,
      commission_rate: ((r.data.commission_rate || 0.035) * 100).toFixed(2),
    });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.patch("/admin/settings", {
        platform_paybill: form.platform_paybill.trim(),
        platform_account: form.platform_account.trim(),
        service_fee_pct: parseFloat(form.service_fee_pct) / 100,
        viewing_caretaker_share: parseFloat(form.viewing_caretaker_share),
        viewing_platform_share: parseFloat(form.viewing_platform_share),
        commission_rate: parseFloat(form.commission_rate) / 100,
      });
      toast.success("Settings updated");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) return <div className="text-zinc-500">Loading...</div>;

  return (
    <div data-testid="admin-settings-page">
      <PageHeader overline="Super Admin" title="Platform Settings" />

      <form onSubmit={save} className="max-w-2xl space-y-6" data-testid="settings-form">
        {/* Platform paybill */}
        <section className="bg-white border border-zinc-200 rounded-md p-6">
          <div className="flex items-center gap-2 mb-3">
            <Wallet className="w-5 h-5 text-emerald-700" />
            <h2 className="font-display font-bold text-xl">Platform M-Pesa Paybill</h2>
          </div>
          <p className="text-sm text-zinc-600 mb-4 leading-relaxed">
            All service fees, viewing fees, and yard-sale fees land here.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="overline">Paybill number</Label>
              <Input required value={form.platform_paybill} onChange={(e) => setForm({ ...form, platform_paybill: e.target.value })} className="mt-1 font-mono-num" data-testid="setting-paybill" />
            </div>
            <div>
              <Label className="overline">Account number</Label>
              <Input required value={form.platform_account} onChange={(e) => setForm({ ...form, platform_account: e.target.value })} className="mt-1 font-mono-num" data-testid="setting-account" />
            </div>
          </div>
        </section>

        {/* Service fee */}
        <section className="bg-white border border-zinc-200 rounded-md p-6">
          <div className="flex items-center gap-2 mb-3">
            <Percent className="w-5 h-5 text-amber-700" />
            <h2 className="font-display font-bold text-xl">Rent & Bill Service Fee</h2>
          </div>
          <p className="text-sm text-zinc-600 mb-4 leading-relaxed">
            Tenants pay this percentage on top of every rent/bill, via STK push to the platform paybill. Rounded up to nearest KES 10.
          </p>
          <div>
            <Label className="overline">Service fee % on tenant payments</Label>
            <Input required type="number" step="0.01" min="0" max="50" value={form.service_fee_pct} onChange={(e) => setForm({ ...form, service_fee_pct: e.target.value })} className="mt-1 font-mono-num text-lg" data-testid="setting-fee-pct" />
            <div className="text-xs text-zinc-500 mt-1">e.g. 2.5 means KES 250 fee on a KES 10,000 rent</div>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 mt-3 text-xs font-mono-num">
            Sample: rent KES 10,000 → fee KES {Math.ceil(10000 * (parseFloat(form.service_fee_pct || 0) / 100) / 10) * 10} → tenant total KES {(10000 + Math.ceil(10000 * (parseFloat(form.service_fee_pct || 0) / 100) / 10) * 10).toLocaleString()}
          </div>
        </section>

        {/* Viewings split */}
        <section className="bg-white border border-zinc-200 rounded-md p-6">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-5 h-5 text-sky-700" />
            <h2 className="font-display font-bold text-xl">Viewing Fee Split (KES 200 booking)</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="overline">Caretaker share (KES)</Label>
              <Input required type="number" min="0" value={form.viewing_caretaker_share} onChange={(e) => setForm({ ...form, viewing_caretaker_share: e.target.value })} className="mt-1 font-mono-num" data-testid="setting-caretaker-share" />
            </div>
            <div>
              <Label className="overline">Platform share (KES)</Label>
              <Input required type="number" min="0" value={form.viewing_platform_share} onChange={(e) => setForm({ ...form, viewing_platform_share: e.target.value })} className="mt-1 font-mono-num" data-testid="setting-platform-share" />
            </div>
          </div>
          <div className="text-xs text-zinc-500 mt-2">After each paid viewing, the caretaker share is added to <a href="/admin/disbursements" className="underline">Disbursements queue</a> for you to pay out via M-Pesa B2C.</div>
        </section>

        {/* Legacy commission (for non-rent receipts) */}
        <section className="bg-white border border-zinc-200 rounded-md p-6">
          <div className="overline text-zinc-500">Legacy field (unused for new rent flow)</div>
          <Label className="overline mt-2 block">Commission rate %</Label>
          <Input type="number" step="0.01" min="0" max="50" value={form.commission_rate} onChange={(e) => setForm({ ...form, commission_rate: e.target.value })} className="mt-1 font-mono-num max-w-xs" data-testid="setting-commission" />
          <div className="text-xs text-zinc-500 mt-1">Kept for backwards compatibility with reports.</div>
        </section>

        <Button type="submit" disabled={saving} className="bg-zinc-950 hover:bg-zinc-800 h-11 w-full" data-testid="settings-save-button">
          {saving ? "Saving..." : "Save all settings"}
        </Button>
      </form>

      <div className="text-xs text-zinc-500 mt-4">Last updated: {new Date(settings.updated_at).toLocaleString()}</div>
    </div>
  );
}
