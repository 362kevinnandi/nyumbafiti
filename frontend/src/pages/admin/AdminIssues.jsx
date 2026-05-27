import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import ExportMenu from "@/components/ExportMenu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { MessageSquare, Send, ShieldCheck } from "lucide-react";

const STATUS_STYLES = {
  open: "bg-red-50 text-red-700 border-red-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  closed: "bg-zinc-100 text-zinc-700 border-zinc-200",
};

export default function AdminIssuesPage() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    const r = await api.get("/admin/issues");
    setIssues(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="admin-issues-page">
      <PageHeader overline="Super Admin" title="All Platform Issues" action={<ExportMenu resource="issues" testIdPrefix="issues-export" />} />

      <div className="mb-6 bg-zinc-50 border border-zinc-200 rounded-md p-4 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
        <div className="text-sm text-zinc-700 leading-relaxed">
          Mediator view of every tenant issue across the platform. You can post messages in any thread to nudge resolution or protect tenants from unfair treatment.
        </div>
      </div>

      {loading ? <div className="text-zinc-500">Loading...</div> : issues.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <MessageSquare className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg">No issues on the platform</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="admin-issues-grid">
          {issues.map((i) => (
            <div key={i.id} className="bg-white border border-zinc-200 rounded-md p-5 card-hover" data-testid={`admin-issue-card-${i.id}`}>
              <div className="flex items-start justify-between mb-2 gap-3">
                <div className="font-display font-bold text-lg leading-tight">{i.title}</div>
                <span className={`badge-status border ${STATUS_STYLES[i.status]}`}>{i.status.replace("_", " ")}</span>
              </div>
              <p className="text-sm text-zinc-600 mb-3 leading-relaxed line-clamp-2">{i.description}</p>
              <div className="text-xs text-zinc-500 space-y-1 mb-3 pb-3 border-b border-zinc-100">
                <div>Tenant: <b>{i.tenant_name}</b> · {i.tenant_phone}</div>
                <div>Landlord: <b>{i.landlord_name}</b></div>
                <div>{i.property_name} · Unit {i.unit_number}</div>
                {i.assigned_to_name && <div>Caretaker: <b>{i.assigned_to_name}</b></div>}
                <div className="text-zinc-400">Opened {new Date(i.created_at).toLocaleString()}</div>
              </div>
              <Button size="sm" variant="outline" className="rounded-md text-xs" onClick={() => setSelected(i)} data-testid={`open-thread-${i.id}`}>
                <MessageSquare className="w-3.5 h-3.5 mr-1.5" /> Open discussion
              </Button>
            </div>
          ))}
        </div>
      )}

      {selected && <AdminThreadDialog issue={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function AdminThreadDialog({ issue, onClose }) {
  const [messages, setMessages] = useState([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await api.get(`/admin/issues/${issue.id}/messages`);
    setMessages(r.data);
    setLoading(false);
  }, [issue.id]);

  useEffect(() => { load(); }, [load]);

  const send = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    try {
      await api.post(`/admin/issues/${issue.id}/messages`, { body });
      setBody("");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="rounded-md max-w-lg" data-testid="admin-thread-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-xl">{issue.title}</DialogTitle>
          <DialogDescription>
            {issue.tenant_name} · {issue.landlord_name} · Unit {issue.unit_number}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-96 overflow-y-auto space-y-3 my-2 pr-1">
          {loading ? <div className="text-zinc-500 text-sm">Loading...</div> : messages.length === 0 ? (
            <div className="text-center py-6 text-sm text-zinc-500">No conversation yet.</div>
          ) : messages.map((m) => (
            <div key={m.id} className={`flex flex-col ${m.author_role === "admin" ? "items-end" : "items-start"}`}>
              <div className={`max-w-[80%] rounded-md px-3 py-2 text-sm ${
                m.author_role === "admin" ? "bg-emerald-600 text-white" :
                m.author_role === "tenant" ? "bg-zinc-100 text-zinc-900" :
                m.author_role === "landlord" ? "bg-blue-50 text-blue-900" :
                "bg-amber-50 text-amber-900"
              }`}>
                {m.body}
              </div>
              <div className="text-xs text-zinc-400 mt-1">
                {m.author_name} ({m.author_role}) · {new Date(m.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={send} className="flex gap-2" data-testid="admin-message-form">
          <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Post as platform admin..." className="flex-1" data-testid="admin-message-input" />
          <Button type="submit" className="bg-emerald-600 hover:bg-emerald-700" data-testid="admin-message-send"><Send className="w-4 h-4" /></Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
