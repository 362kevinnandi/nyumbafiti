import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES, mediaUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, FileText, Download, CheckCircle2, X, Pen } from "lucide-react";

const STATUS_COLORS = {
  draft: "bg-zinc-100 text-zinc-700",
  sent: "bg-amber-50 text-amber-800",
  signed: "bg-emerald-50 text-emerald-800",
  cancelled: "bg-red-50 text-red-700",
};

export default function LeasesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [units, setUnits] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [signing, setSigning] = useState(null);
  const [form, setForm] = useState({
    tenant_id: "", unit_id: "", rent_amount: "", deposit_amount: "",
    start_date: "", end_date: "", terms: "", agreement_type: "lease",
  });

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/leases");
    setItems(r.data || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    if (user.role === "landlord") {
      api.get("/units").then((r) => {
        const occupied = (r.data || []).filter((u) => u.occupied && u.tenant_id);
        setUnits(occupied);
      });
      api.get("/users?role=tenant").then((r) => setTenants(r.data || [])).catch(() => {});
    }
  }, [load, user.role]);

  const onUnit = async (uid) => {
    const u = units.find((x) => x.id === uid);
    if (!u) return;
    // Fetch tenant tenancy_type to auto-pick agreement_type
    let agreementType = "lease";
    try {
      const tres = await api.get(`/tenants`);
      const t = (tres.data || []).find((x) => x.unit_id === uid);
      if (t?.tenancy_type) agreementType = t.tenancy_type;
    } catch {/* */}
    setForm((f) => ({
      ...f,
      unit_id: uid,
      tenant_id: u.tenant_id || "",
      rent_amount: String(u.rent_amount || ""),
      agreement_type: agreementType,
    }));
  };

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/leases", {
        tenant_id: form.tenant_id,
        unit_id: form.unit_id,
        rent_amount: Number(form.rent_amount),
        deposit_amount: Number(form.deposit_amount || 0),
        start_date: form.start_date,
        end_date: form.end_date,
        terms: form.terms,
        agreement_type: form.agreement_type,
      });
      toast.success(form.agreement_type === "rental" ? "Rental agreement sent" : "Lease sent");
      setOpen(false);
      setForm({ tenant_id: "", unit_id: "", rent_amount: "", deposit_amount: "", start_date: "", end_date: "", terms: "", agreement_type: "lease" });
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to create"));
    }
  };

  const sign = async (id) => {
    setSigning(id);
    try {
      await api.post(`/leases/${id}/sign`);
      toast.success("Lease signed!");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to sign"));
    } finally {
      setSigning(null);
    }
  };

  const cancel = async (id) => {
    if (!window.confirm("Cancel this lease?")) return;
    try {
      await api.delete(`/leases/${id}`);
      toast.success("Cancelled");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const canCreate = user.role === "landlord";

  return (
    <div data-testid="leases-page">
      <PageHeader
        overline="Documents"
        title={user.role === "tenant" ? "My Agreement" : "Rental & Lease Agreements"}
        action={canCreate && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="new-lease-button">
                <Plus className="w-4 h-4 mr-1.5" /> New Agreement
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-md max-w-lg">
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">Create Agreement</DialogTitle>
                <DialogDescription>
                  Generates a PDF and notifies the tenant for in-app e-signature.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={create} className="space-y-4" data-testid="lease-form">
                <div>
                  <Label className="overline">Unit</Label>
                  <select
                    required
                    value={form.unit_id}
                    onChange={(e) => onUnit(e.target.value)}
                    className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                    data-testid="lease-unit-select"
                  >
                    <option value="">Select an occupied unit...</option>
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.unit_number} · {u.tenant_name || "?"} · {formatKES(u.rent_amount)}/mo
                      </option>
                    ))}
                  </select>
                </div>
                {form.unit_id && (
                  <div>
                    <Label className="overline">Agreement type</Label>
                    <div className="flex gap-2 mt-2" data-testid="lease-agreement-type">
                      {[{value:"rental",label:"Rental Agreement"},{value:"lease",label:"Lease Agreement"}].map((t) => {
                        const active = form.agreement_type === t.value;
                        return (
                          <button type="button" key={t.value}
                            onClick={() => setForm({ ...form, agreement_type: t.value })}
                            className={`px-4 h-10 rounded-full border text-sm font-semibold ${active ? "bg-zinc-950 text-white border-zinc-950" : "bg-white border-zinc-300 text-zinc-700"}`}
                            data-testid={`lease-agreement-type-${t.value}`}>
                            {t.label}
                          </button>
                        );
                      })}
                    </div>
                    <div className="text-[10px] text-zinc-500 mt-1.5">Auto-set from tenant's assigned tenancy type — override if needed.</div>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="overline">Rent (KES)</Label>
                    <Input required type="number" value={form.rent_amount} onChange={(e) => setForm({ ...form, rent_amount: e.target.value })} className="mt-1" data-testid="lease-rent" />
                  </div>
                  <div>
                    <Label className="overline">Deposit (KES)</Label>
                    <Input type="number" value={form.deposit_amount} onChange={(e) => setForm({ ...form, deposit_amount: e.target.value })} className="mt-1" data-testid="lease-deposit" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="overline">Start date</Label>
                    <Input required type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="mt-1" data-testid="lease-start-date" />
                  </div>
                  <div>
                    <Label className="overline">End date</Label>
                    <Input required type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="mt-1" data-testid="lease-end-date" />
                  </div>
                </div>
                <div>
                  <Label className="overline">Additional terms (optional)</Label>
                  <Textarea rows={4} value={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.value })} className="mt-1" placeholder="House rules, special clauses..." data-testid="lease-terms" />
                </div>
                <DialogFooter>
                  <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="lease-submit">Generate & Send</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />

      {loading ? <div className="text-zinc-500">Loading...</div>
        : items.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="leases-empty">
            <FileText className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No leases yet</div>
            <div className="text-sm text-zinc-500">{canCreate ? "Create one to get started." : "Your landlord hasn't sent a lease yet."}</div>
          </div>
        ) : (
          <div className="bg-white border border-zinc-200 rounded-md overflow-hidden" data-testid="leases-table">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Tenant</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Type</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Period</th>
                  <th className="text-right px-4 py-3 overline text-zinc-500">Rent</th>
                  <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                  <th className="text-right px-4 py-3 overline text-zinc-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((l) => (
                  <tr key={l.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`lease-row-${l.id}`}>
                    <td className="px-4 py-3 font-semibold">{l.tenant_name}</td>
                    <td className="px-4 py-3">
                      <span className={`badge-status ${l.agreement_type === "rental" ? "bg-sky-50 text-sky-800" : "bg-indigo-50 text-indigo-800"}`}>
                        {(l.agreement_type || "lease").toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-600">{l.start_date} → {l.end_date}</td>
                    <td className="px-4 py-3 text-right font-mono-num">{formatKES(l.rent_amount)}</td>
                    <td className="px-4 py-3">
                      <span className={`badge-status ${STATUS_COLORS[l.status] || "bg-zinc-100"}`}>{l.status.toUpperCase()}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {l.pdf_path && (
                          <a href={mediaUrl(l.pdf_path)} target="_blank" rel="noreferrer" className="text-xs flex items-center gap-1 px-2 h-7 border border-zinc-200 rounded-md hover:bg-zinc-100" data-testid={`lease-download-${l.id}`}>
                            <Download className="w-3 h-3" /> PDF
                          </a>
                        )}
                        {user.role === "tenant" && l.status === "sent" && (
                          <Button size="sm" onClick={() => sign(l.id)} disabled={signing === l.id} className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs" data-testid={`lease-sign-${l.id}`}>
                            <Pen className="w-3 h-3 mr-1" /> {signing === l.id ? "Signing..." : "E-Sign"}
                          </Button>
                        )}
                        {l.status === "signed" && <CheckCircle2 className="w-4 h-4 text-emerald-600 inline" />}
                        {(user.role === "landlord" || user.role === "admin") && l.status !== "signed" && l.status !== "cancelled" && (
                          <button onClick={() => cancel(l.id)} className="text-zinc-400 hover:text-red-600 p-1.5" data-testid={`lease-cancel-${l.id}`}>
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
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
