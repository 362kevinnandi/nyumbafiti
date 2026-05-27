import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
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
import { Plus, QrCode, ScanLine, Check, X, Clock } from "lucide-react";

const STATUS_COLORS = {
  active: "bg-emerald-50 text-emerald-800 border-emerald-200",
  used: "bg-zinc-100 text-zinc-700 border-zinc-200",
  expired: "bg-amber-50 text-amber-800 border-amber-200",
  cancelled: "bg-red-50 text-red-700 border-red-200",
};

export default function VisitorsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [activeQr, setActiveQr] = useState(null);
  const [scanOpen, setScanOpen] = useState(false);
  const [scanToken, setScanToken] = useState("");
  const [form, setForm] = useState({ visitor_name: "", visitor_phone: "", expected_time: "", notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/visitor-passes");
    setItems(r.data || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post("/visitor-passes", form);
      toast.success("Pass created. Share the QR code with your visitor.");
      setOpen(false);
      setForm({ visitor_name: "", visitor_phone: "", expected_time: "", notes: "" });
      setActiveQr(r.data);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const cancel = async (id) => {
    if (!window.confirm("Cancel this pass?")) return;
    await api.delete(`/visitor-passes/${id}`);
    toast.success("Cancelled");
    load();
  };

  const scan = async (e) => {
    e.preventDefault();
    if (!scanToken.trim()) return;
    try {
      const r = await api.post(`/visitor-passes/scan/${scanToken.trim()}`);
      toast.success(`Welcome ${r.data.visitor_name}! Entry logged.`);
      setScanOpen(false);
      setScanToken("");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Scan failed"));
    }
  };

  const isTenant = user.role === "tenant";
  const isStaff = ["caretaker", "landlord", "admin"].includes(user.role);

  return (
    <div data-testid="visitors-page">
      <PageHeader
        overline="Security"
        title="Visitor Passes"
        action={
          <div className="flex gap-2">
            {isStaff && (
              <Dialog open={scanOpen} onOpenChange={setScanOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="rounded-md" data-testid="scan-pass-button">
                    <ScanLine className="w-4 h-4 mr-1.5" /> Scan / Log Entry
                  </Button>
                </DialogTrigger>
                <DialogContent className="rounded-md max-w-sm">
                  <DialogHeader>
                    <DialogTitle className="font-display font-black text-2xl">Log Visitor Entry</DialogTitle>
                    <DialogDescription>Type or paste the visitor's pass token (from their QR).</DialogDescription>
                  </DialogHeader>
                  <form onSubmit={scan} className="space-y-4" data-testid="scan-form">
                    <div>
                      <Label className="overline">Pass token</Label>
                      <Input required value={scanToken} onChange={(e) => setScanToken(e.target.value)} placeholder="Paste QR contents here" className="mt-1 font-mono-num" data-testid="scan-token-input" />
                    </div>
                    <DialogFooter>
                      <Button type="submit" className="bg-emerald-600 hover:bg-emerald-700" data-testid="scan-submit">
                        <Check className="w-4 h-4 mr-1.5" /> Log Entry
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            )}
            {isTenant && (
              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="new-visitor-button">
                    <Plus className="w-4 h-4 mr-1.5" /> New Pass
                  </Button>
                </DialogTrigger>
                <DialogContent className="rounded-md max-w-md">
                  <DialogHeader>
                    <DialogTitle className="font-display font-black text-2xl">Invite a Visitor</DialogTitle>
                    <DialogDescription>One-time QR pass, expires in 24 hours.</DialogDescription>
                  </DialogHeader>
                  <form onSubmit={create} className="space-y-4" data-testid="visitor-form">
                    <div>
                      <Label className="overline">Visitor name</Label>
                      <Input required value={form.visitor_name} onChange={(e) => setForm({ ...form, visitor_name: e.target.value })} className="mt-1" data-testid="visitor-name-input" />
                    </div>
                    <div>
                      <Label className="overline">Visitor phone (optional)</Label>
                      <Input value={form.visitor_phone} onChange={(e) => setForm({ ...form, visitor_phone: e.target.value })} className="mt-1 font-mono-num" data-testid="visitor-phone-input" />
                    </div>
                    <div>
                      <Label className="overline">Expected arrival</Label>
                      <Input required type="datetime-local" value={form.expected_time} onChange={(e) => setForm({ ...form, expected_time: e.target.value })} className="mt-1" data-testid="visitor-time-input" />
                    </div>
                    <div>
                      <Label className="overline">Notes (optional)</Label>
                      <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1" data-testid="visitor-notes-input" />
                    </div>
                    <DialogFooter>
                      <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="visitor-submit">Generate Pass</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            )}
          </div>
        }
      />

      {activeQr && (
        <div className="bg-white border-2 border-emerald-300 rounded-md p-6 mb-6 flex items-center gap-6 max-w-2xl" data-testid="active-qr-card">
          <img src={activeQr.qr_data_url} alt="QR code" className="w-44 h-44 bg-white" data-testid="active-qr-image" />
          <div className="flex-1">
            <div className="overline text-emerald-700 mb-1">New pass for</div>
            <div className="font-display font-black text-2xl mb-2">{activeQr.visitor_name}</div>
            <div className="text-sm text-zinc-600 mb-3">Expected: {new Date(activeQr.expected_time).toLocaleString()}</div>
            <div className="bg-zinc-50 border border-zinc-200 rounded-md p-2 text-[10px] font-mono break-all mb-3">{activeQr.token}</div>
            <Button size="sm" variant="outline" onClick={() => setActiveQr(null)} data-testid="close-qr-button">Done</Button>
          </div>
        </div>
      )}

      {loading ? <div className="text-zinc-500">Loading...</div>
        : items.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="visitors-empty">
            <QrCode className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No visitor passes yet</div>
            <div className="text-sm text-zinc-500">{isTenant ? "Create a pass to invite someone." : "No tenant has invited a visitor yet."}</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="visitors-grid">
            {items.map((p) => (
              <div key={p.id} className={`bg-white border rounded-md p-4 ${STATUS_COLORS[p.status]?.split(" ").slice(-1)[0] || "border-zinc-200"}`} data-testid={`visitor-card-${p.id}`}>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="font-display font-bold text-lg">{p.visitor_name}</div>
                  <span className={`badge-status ${STATUS_COLORS[p.status] || ""}`}>{p.status.toUpperCase()}</span>
                </div>
                <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1"><Clock className="w-3 h-3" /> Expected {new Date(p.expected_time).toLocaleString()}</div>
                {p.visitor_phone && <div className="text-xs text-zinc-600 font-mono-num mb-2">{p.visitor_phone}</div>}
                {p.tenant_name && user.role !== "tenant" && <div className="overline text-zinc-500 text-[10px] mb-2">Host: {p.tenant_name}</div>}
                {p.qr_data_url && p.status === "active" && (
                  <img src={p.qr_data_url} alt="QR" className="w-32 h-32 mt-2 mx-auto bg-white border border-zinc-100" data-testid={`visitor-qr-${p.id}`} />
                )}
                {p.token && p.status === "active" && (
                  <button
                    type="button"
                    onClick={() => {
                      const url = `${window.location.origin}/pass/${p.token}`;
                      navigator.clipboard.writeText(url);
                      toast.success("Pass link copied — send to your guest");
                    }}
                    className="mt-2 w-full text-xs h-7 border border-zinc-200 hover:border-zinc-400 rounded-md font-semibold"
                    data-testid={`visitor-share-${p.id}`}
                  >
                    Copy share link for guest
                  </button>
                )}
                {p.used_at && (
                  <div className="text-xs text-emerald-700 mt-3 pt-3 border-t border-zinc-100">
                    Entry logged at {new Date(p.used_at).toLocaleString()}
                    {p.used_by_caretaker_name && ` by ${p.used_by_caretaker_name}`}
                  </div>
                )}
                {isTenant && p.status === "active" && (
                  <Button size="sm" variant="outline" onClick={() => cancel(p.id)} className="mt-2 w-full text-xs h-7" data-testid={`visitor-cancel-${p.id}`}>
                    <X className="w-3 h-3 mr-1" /> Cancel pass
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
