import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Check, X, Home, Users, HardHat, ShieldCheck } from "lucide-react";

export default function AdminApprovalsPage() {
  const [data, setData] = useState({ properties: [], tenants: [], caretakers: [], total_pending: 0 });
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("properties");

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/admin/approvals");
    setData(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = async (kind, id, approve, reason = "") => {
    try {
      const url = kind === "property" ? `/admin/approvals/property/${id}` : `/admin/approvals/user/${id}`;
      await api.post(url, { approve, reason });
      toast.success(approve ? "Approved" : "Rejected");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  return (
    <div data-testid="admin-approvals-page">
      <PageHeader
        overline="Super Admin"
        title="Pending Approvals"
      />

      <div className="mb-6 bg-zinc-50 border border-zinc-200 rounded-md p-4 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
        <div className="text-sm text-zinc-700 leading-relaxed">
          New properties, tenants, and caretakers added by landlords appear here for verification before they can fully participate.
          This protects tenants from landlord manipulation and helps build platform trust.
        </div>
      </div>

      {loading ? <div className="text-zinc-500">Loading...</div> : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-zinc-100 rounded-md mb-6">
            <TabsTrigger value="properties" data-testid="tab-properties">
              <Home className="w-3.5 h-3.5 mr-1.5" /> Properties ({data.properties.length})
            </TabsTrigger>
            <TabsTrigger value="tenants" data-testid="tab-tenants">
              <Users className="w-3.5 h-3.5 mr-1.5" /> Tenants ({data.tenants.length})
            </TabsTrigger>
            <TabsTrigger value="caretakers" data-testid="tab-caretakers">
              <HardHat className="w-3.5 h-3.5 mr-1.5" /> Caretakers ({data.caretakers.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="properties">
            {data.properties.length === 0 ? <EmptyState icon={Home} text="No pending properties" /> : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="pending-properties-grid">
                {data.properties.map((p) => (
                  <ApprovalCard key={p.id} testIdPrefix={`prop-${p.id}`} onDecide={(approve, reason) => decide("property", p.id, approve, reason)}>
                    <div className="overline text-zinc-500 mb-1">Property</div>
                    <div className="font-display font-bold text-lg">{p.name}</div>
                    <div className="text-sm text-zinc-600 mb-2">{p.address}</div>
                    {p.description && <p className="text-xs text-zinc-500 mb-2">{p.description}</p>}
                    <div className="text-xs text-zinc-500">By <b>{p.landlord_name}</b> · {p.landlord_email}</div>
                  </ApprovalCard>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="tenants">
            {data.tenants.length === 0 ? <EmptyState icon={Users} text="No pending tenants" /> : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="pending-tenants-grid">
                {data.tenants.map((t) => (
                  <ApprovalCard key={t.id} testIdPrefix={`tenant-${t.id}`} onDecide={(approve, reason) => decide("user", t.id, approve, reason)}>
                    <div className="overline text-zinc-500 mb-1">Tenant</div>
                    <div className="font-display font-bold text-lg">{t.full_name}</div>
                    <div className="text-sm text-zinc-600">{t.email} · <span className="font-mono-num">{t.phone}</span></div>
                    {t.property_name && (
                      <div className="text-xs text-zinc-500 mt-2">
                        Assigned to <b>{t.property_name}</b> · Unit {t.unit_number} · {formatKES(t.rent_amount)}/mo
                      </div>
                    )}
                    <div className="text-xs text-zinc-500 mt-1">Onboarded by <b>{t.landlord_name}</b></div>
                  </ApprovalCard>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="caretakers">
            {data.caretakers.length === 0 ? <EmptyState icon={HardHat} text="No pending caretakers" /> : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="pending-caretakers-grid">
                {data.caretakers.map((c) => (
                  <ApprovalCard key={c.id} testIdPrefix={`caretaker-${c.id}`} onDecide={(approve, reason) => decide("user", c.id, approve, reason)}>
                    <div className="overline text-zinc-500 mb-1">Caretaker</div>
                    <div className="font-display font-bold text-lg">{c.full_name}</div>
                    <div className="text-sm text-zinc-600">{c.email} · <span className="font-mono-num">{c.phone}</span></div>
                    <div className="text-xs text-zinc-500 mt-2">Added by <b>{c.landlord_name}</b></div>
                  </ApprovalCard>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function ApprovalCard({ children, onDecide, testIdPrefix }) {
  return (
    <div className="bg-white border border-amber-200 rounded-md p-5 card-hover" data-testid={`approval-card-${testIdPrefix}`}>
      <div className="mb-4">{children}</div>
      <div className="flex gap-2 pt-3 border-t border-zinc-100">
        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white flex-1" onClick={() => onDecide(true)} data-testid={`approve-${testIdPrefix}`}>
          <Check className="w-3.5 h-3.5 mr-1" /> Approve
        </Button>
        <RejectDialog testIdPrefix={testIdPrefix} onSubmit={(reason) => onDecide(false, reason)} />
      </div>
    </div>
  );
}

function RejectDialog({ onSubmit, testIdPrefix }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  const submit = (e) => {
    e.preventDefault();
    onSubmit(reason);
    setOpen(false);
    setReason("");
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="text-red-600 border-red-200 hover:bg-red-50 flex-1" data-testid={`reject-${testIdPrefix}`}>
          <X className="w-3.5 h-3.5 mr-1" /> Reject
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-xl">Reject</DialogTitle>
          <DialogDescription>Tell the landlord why so they can fix and resubmit.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4 mt-2" data-testid="reject-form">
          <div>
            <Label className="overline">Reason</Label>
            <Input required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Missing property documentation" className="mt-1" data-testid="reject-reason-input" />
          </div>
          <DialogFooter>
            <Button type="submit" className="bg-red-600 hover:bg-red-700 text-white" data-testid="reject-submit-button">Reject</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EmptyState({ icon: Icon, text }) {
  return (
    <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
      <Icon className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
      <div className="font-display font-bold text-lg text-zinc-700">{text}</div>
      <div className="text-sm text-zinc-500 mt-1">All clear in this queue.</div>
    </div>
  );
}
