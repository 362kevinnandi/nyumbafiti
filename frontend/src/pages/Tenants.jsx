import { useEffect, useState } from "react";
import { api, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Users, Trash2, UserCircle } from "lucide-react";

export default function TenantsPage() {
  const [tenants, setTenants] = useState([]);
  const [units, setUnits] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", phone: "", password: "", unit_id: "" });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const [t, u] = await Promise.all([api.get("/tenants"), api.get("/units")]);
    setTenants(t.data);
    setUnits(u.data.filter((u) => !u.occupied));
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/tenants", form);
      toast.success(`Tenant ${form.full_name} added`);
      setOpen(false);
      setForm({ email: "", full_name: "", phone: "", password: "", unit_id: "" });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id, name) => {
    if (!window.confirm(`Remove tenant ${name}?`)) return;
    await api.delete(`/tenants/${id}`);
    toast.success("Tenant removed");
    load();
  };

  return (
    <div data-testid="tenants-page">
      <PageHeader
        overline="People"
        title="Tenants"
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="add-tenant-button">
                <Plus className="w-4 h-4 mr-1.5" /> Add Tenant
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-md">
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">Onboard Tenant</DialogTitle>
              </DialogHeader>
              <form onSubmit={create} className="space-y-4 mt-2" data-testid="tenant-form">
                <div><Label className="overline">Full name</Label><Input required value={form.full_name} onChange={(e) => setForm({...form, full_name: e.target.value})} className="mt-1" data-testid="tenant-name-input" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="overline">Email</Label><Input required type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className="mt-1" data-testid="tenant-email-input" /></div>
                  <div><Label className="overline">Phone</Label><Input required value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} placeholder="0712..." className="mt-1" data-testid="tenant-phone-input" /></div>
                </div>
                <div><Label className="overline">Initial password</Label><Input required type="text" minLength={6} value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} className="mt-1" data-testid="tenant-password-input" placeholder="Share with tenant" /></div>
                <div>
                  <Label className="overline">Assign to Unit</Label>
                  <select required value={form.unit_id} onChange={(e) => setForm({...form, unit_id: e.target.value})} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="tenant-unit-select">
                    <option value="">Select vacant unit...</option>
                    {units.map((u) => <option key={u.id} value={u.id}>{u.unit_number} — {formatKES(u.rent_amount)}/mo</option>)}
                  </select>
                  {units.length === 0 && <div className="text-xs text-zinc-500 mt-1">No vacant units. Create units first.</div>}
                </div>
                <DialogFooter>
                  <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="tenant-submit-button">Create tenant</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {loading ? <div className="text-zinc-500">Loading...</div> : tenants.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <Users className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No tenants yet</div>
          <div className="text-sm text-zinc-500">Add your first tenant and assign them to a vacant unit.</div>
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-md overflow-hidden" data-testid="tenants-table">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 border-b border-zinc-200">
              <tr>
                <th className="text-left px-4 py-3 overline text-zinc-500">Tenant</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Contact</th>
                <th className="text-left px-4 py-3 overline text-zinc-500">Property / Unit</th>
                <th className="text-right px-4 py-3 overline text-zinc-500">Rent</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`tenant-row-${t.id}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 bg-zinc-100 rounded-full flex items-center justify-center">
                        <UserCircle className="w-5 h-5 text-zinc-500" />
                      </div>
                      <div>
                        <div className="font-semibold">{t.full_name}</div>
                        <div className="text-xs text-zinc-500">{t.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-zinc-600 font-mono-num">{t.phone}</td>
                  <td className="px-4 py-3 text-zinc-600">
                    <div>{t.property_name || "—"}</div>
                    <div className="text-xs text-zinc-400">Unit {t.unit_number}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono-num">{formatKES(t.rent_amount)}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => remove(t.id, t.full_name)} className="text-zinc-400 hover:text-red-600" data-testid={`delete-tenant-${t.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </button>
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
