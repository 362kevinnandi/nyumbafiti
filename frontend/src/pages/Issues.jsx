import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Wrench, MessageSquare, Send } from "lucide-react";

const STATUS_STYLES = {
  open: "bg-red-50 text-red-700 border-red-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  closed: "bg-zinc-100 text-zinc-700 border-zinc-200",
};
const PRIORITY_STYLES = {
  low: "bg-zinc-100 text-zinc-700",
  medium: "bg-blue-50 text-blue-700",
  high: "bg-amber-50 text-amber-700",
  urgent: "bg-red-50 text-red-700",
};

export default function IssuesPage() {
  const { user } = useAuth();
  const [issues, setIssues] = useState([]);
  const [caretakers, setCaretakers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "medium" });
  const [selectedIssue, setSelectedIssue] = useState(null);

  const load = useCallback(async () => {
    const calls = [api.get("/issues")];
    if (user.role === "landlord") calls.push(api.get("/caretakers"));
    const results = await Promise.all(calls);
    setIssues(results[0].data);
    if (user.role === "landlord") setCaretakers(results[1].data);
    setLoading(false);
  }, [user.role]);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/issues", form);
      toast.success("Issue reported");
      setOpen(false);
      setForm({ title: "", description: "", priority: "medium" });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const updateIssue = async (id, patch) => {
    try {
      await api.patch(`/issues/${id}`, patch);
      toast.success("Updated");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  return (
    <div data-testid="issues-page">
      <PageHeader
        overline="Operations"
        title={user.role === "tenant" ? "Report Issues" : user.role === "caretaker" ? "Service Tickets" : "Tenant Issues"}
        action={
          user.role === "tenant" && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="report-issue-button">
                  <Plus className="w-4 h-4 mr-1.5" /> Report Issue
                </Button>
              </DialogTrigger>
              <DialogContent className="rounded-md">
                <DialogHeader>
                  <DialogTitle className="font-display font-black text-2xl">Report an Issue</DialogTitle>
                  <DialogDescription>Your landlord and caretakers will see this immediately.</DialogDescription>
                </DialogHeader>
                <form onSubmit={create} className="space-y-4 mt-2" data-testid="issue-form">
                  <div><Label className="overline">Title</Label><Input required value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} placeholder="e.g. Kitchen sink leaking" className="mt-1" data-testid="issue-title-input" /></div>
                  <div><Label className="overline">Description</Label><Textarea required value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} rows={4} className="mt-1" data-testid="issue-description-input" /></div>
                  <div>
                    <Label className="overline">Priority</Label>
                    <select value={form.priority} onChange={(e) => setForm({...form, priority: e.target.value})} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="issue-priority-select">
                      <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
                    </select>
                  </div>
                  <DialogFooter>
                    <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="issue-submit-button">Submit</Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          )
        }
      />

      {loading ? <div className="text-zinc-500">Loading...</div> : issues.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
          <Wrench className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No issues</div>
          <div className="text-sm text-zinc-500">{user.role === "tenant" ? "Report an issue and it will appear here." : "No tenant issues currently."}</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="issues-grid">
          {issues.map((i) => (
            <div key={i.id} className="bg-white border border-zinc-200 rounded-md p-5 card-hover" data-testid={`issue-card-${i.id}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="font-display font-bold text-lg leading-tight">{i.title}</div>
                <span className={`badge-status border ${STATUS_STYLES[i.status]}`}>{i.status.replace("_", " ")}</span>
              </div>
              <div className="text-sm text-zinc-600 mb-3 leading-relaxed">{i.description}</div>
              <div className="flex items-center gap-2 flex-wrap text-xs mb-3">
                <span className={`badge-status ${PRIORITY_STYLES[i.priority]}`}>{i.priority}</span>
                {i.tenant_name && user.role !== "tenant" && <span className="text-zinc-500">From: <b>{i.tenant_name}</b></span>}
                {i.unit_number && user.role !== "tenant" && <span className="text-zinc-500">· Unit {i.unit_number}</span>}
                {i.assigned_to_name && <span className="text-zinc-500">· Assigned: <b>{i.assigned_to_name}</b></span>}
                <span className="text-zinc-400">· {new Date(i.created_at).toLocaleDateString()}</span>
              </div>

              {/* Controls per role */}
              <div className="flex items-center justify-between gap-2 pt-3 border-t border-zinc-100">
                <Button variant="outline" size="sm" className="rounded-md text-xs" onClick={() => setSelectedIssue(i)} data-testid={`issue-thread-${i.id}`}>
                  <MessageSquare className="w-3.5 h-3.5 mr-1" /> Discussion
                </Button>
                {user.role === "landlord" && (
                  <div className="flex gap-2">
                    <select
                      value={i.assigned_to || ""}
                      onChange={(e) => updateIssue(i.id, { assigned_to: e.target.value || null })}
                      className="text-xs h-8 border border-zinc-300 rounded-md px-2 bg-white"
                      data-testid={`assign-caretaker-${i.id}`}
                    >
                      <option value="">Unassigned</option>
                      {caretakers.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
                    </select>
                    <select
                      value={i.status}
                      onChange={(e) => updateIssue(i.id, { status: e.target.value })}
                      className="text-xs h-8 border border-zinc-300 rounded-md px-2 bg-white"
                      data-testid={`status-select-${i.id}`}
                    >
                      <option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option><option value="closed">Closed</option>
                    </select>
                  </div>
                )}
                {user.role === "caretaker" && (
                  <div className="flex gap-2">
                    {!i.assigned_to && (
                      <Button size="sm" className="bg-zinc-950 hover:bg-zinc-800 text-xs h-8" onClick={() => updateIssue(i.id, { assigned_to: user.id, status: "in_progress" })}>
                        Pick up
                      </Button>
                    )}
                    {i.assigned_to === user.id && i.status !== "resolved" && (
                      <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-xs h-8" onClick={() => updateIssue(i.id, { status: "resolved" })}>
                        Mark resolved
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedIssue && (
        <IssueThreadDialog issue={selectedIssue} onClose={() => setSelectedIssue(null)} />
      )}
    </div>
  );
}

function IssueThreadDialog({ issue, onClose }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await api.get(`/issues/${issue.id}/messages`);
    setMessages(r.data);
    setLoading(false);
  }, [issue.id]);
  useEffect(() => { load(); }, [load]);

  const send = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    await api.post(`/issues/${issue.id}/messages`, { body });
    setBody("");
    load();
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="rounded-md max-w-lg" data-testid="issue-thread-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-xl">{issue.title}</DialogTitle>
          <DialogDescription>Conversation thread</DialogDescription>
        </DialogHeader>
        <div className="max-h-96 overflow-y-auto space-y-3 my-2 pr-1">
          {loading ? <div className="text-zinc-500 text-sm">Loading...</div> : messages.length === 0 ? (
            <div className="text-center py-6 text-sm text-zinc-500">No messages yet. Start the conversation.</div>
          ) : messages.map((m) => (
            <div key={m.id} className={`flex flex-col ${m.author_id === user.id ? "items-end" : "items-start"}`}>
              <div className={`max-w-[80%] rounded-md px-3 py-2 text-sm ${m.author_id === user.id ? "bg-zinc-950 text-white" : "bg-zinc-100 text-zinc-900"}`}>
                {m.body}
              </div>
              <div className="text-xs text-zinc-400 mt-1">
                {m.author_name} ({m.author_role}) · {new Date(m.created_at).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={send} className="flex gap-2" data-testid="message-form">
          <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Type your message..." className="flex-1" data-testid="message-input" />
          <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="message-send-button">
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
