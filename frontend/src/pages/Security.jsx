import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Shield, Trash2 } from "lucide-react";

export default function SecurityPage() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", phone: "", password: "" });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await api.get("/security");
    setRows(r.data);
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/security", form);
      toast.success("Security personnel added");
      setOpen(false);
      setForm({ email: "", full_name: "", phone: "", password: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove security personnel?")) return;
    await api.delete(`/security/${id}`);
    toast.success("Removed");
    load();
  };

  return (
    <div data-testid="security-page">
      <PageHeader
        overline="People"
        title="Security Personnel"
        action={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="add-security-button">
                <Plus className="w-4 h-4 mr-1.5" /> Add Security
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-md">
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">New Security Personnel</DialogTitle>
              </DialogHeader>
              <form onSubmit={create} className="space-y-4 mt-2" data-testid="security-form">
                <div><Label className="overline">Full name</Label><Input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="mt-1" data-testid="security-name-input" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="overline">Email</Label><Input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1" data-testid="security-email-input" /></div>
                  <div><Label className="overline">Phone</Label><Input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-1" data-testid="security-phone-input" /></div>
                </div>
                <div><Label className="overline">Initial password</Label><Input required type="text" minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-1" data-testid="security-password-input" /></div>
                <DialogFooter>
                  <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="security-submit-button">Create</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />
      {loading ? <div className="text-zinc-500">Loading...</div> : rows.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <Shield className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No security personnel yet</div>
          <div className="text-sm text-zinc-500">Add security staff to handle gate scans, ticket triage and visitor entry.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((c) => (
            <div key={c.id} className="bg-white border border-zinc-200 rounded-md p-5 card-hover" data-testid={`security-card-${c.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 bg-zinc-950 text-white rounded-md flex items-center justify-center font-display font-bold">
                  <Shield className="w-5 h-5" />
                </div>
                <button onClick={() => remove(c.id)} className="text-zinc-400 hover:text-red-600" data-testid={`delete-security-${c.id}`}>
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="font-display font-bold text-lg flex items-center gap-2">
                {c.full_name}
                {c.approval_status === "pending" && <span className="badge-status bg-amber-50 text-amber-700 text-[10px]">Pending</span>}
                {c.approval_status === "rejected" && <span className="badge-status bg-red-50 text-red-700 text-[10px]">Rejected</span>}
              </div>
              <div className="text-xs text-zinc-500">{c.email}</div>
              <div className="text-xs text-zinc-600 font-mono-num mt-2">{c.phone}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
