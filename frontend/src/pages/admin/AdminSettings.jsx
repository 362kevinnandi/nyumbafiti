import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Percent } from "lucide-react";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState(null);
  const [ratePct, setRatePct] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/admin/settings");
    setSettings(r.data);
    setRatePct((r.data.commission_rate * 100).toFixed(2));
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const newRate = parseFloat(ratePct) / 100;
      await api.patch("/admin/settings", { commission_rate: newRate });
      toast.success("Commission rate updated");
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
      <div className="max-w-xl bg-white border border-zinc-200 rounded-md p-6">
        <div className="overline text-zinc-500 mb-1">Commission rate</div>
        <h2 className="font-display font-bold text-2xl mb-2 flex items-center gap-2">
          <Percent className="w-5 h-5 text-emerald-600" />
          Platform fee per successful transaction
        </h2>
        <p className="text-sm text-zinc-600 mb-6 leading-relaxed">
          This percentage is deducted from every successful M-Pesa payment (rent, utility bills, viewing fees).
          The landlord receives the net amount. Currently <span className="font-bold">{(settings.commission_rate * 100).toFixed(2)}%</span>.
        </p>

        <form onSubmit={save} className="space-y-4" data-testid="settings-form">
          <div>
            <Label className="overline">New commission rate (%)</Label>
            <Input
              required
              type="number"
              step="0.01"
              min="0"
              max="50"
              value={ratePct}
              onChange={(e) => setRatePct(e.target.value)}
              className="mt-1 font-mono-num text-lg"
              data-testid="commission-input"
            />
            <div className="text-xs text-zinc-500 mt-1">e.g. 3.5 means KES 35 commission on every KES 1,000</div>
          </div>

          <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4">
            <div className="overline text-zinc-500 mb-2">Example breakdown</div>
            <div className="space-y-1 text-sm font-mono-num">
              <div className="flex justify-between"><span>Tenant pays</span><span className="font-bold">KES 10,000</span></div>
              <div className="flex justify-between text-emerald-600"><span>Platform commission ({parseFloat(ratePct || 0).toFixed(2)}%)</span><span>−{Math.round(10000 * (parseFloat(ratePct || 0) / 100)).toLocaleString()}</span></div>
              <div className="flex justify-between border-t border-zinc-300 pt-1"><span>Landlord receives</span><span className="font-bold">{Math.round(10000 - 10000 * (parseFloat(ratePct || 0) / 100)).toLocaleString()}</span></div>
            </div>
          </div>

          <Button type="submit" disabled={saving} className="bg-zinc-950 hover:bg-zinc-800 h-11" data-testid="settings-save-button">
            {saving ? "Saving..." : "Update commission rate"}
          </Button>
        </form>

        <div className="text-xs text-zinc-500 mt-6 pt-6 border-t border-zinc-100">
          Last updated: {new Date(settings.updated_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}
