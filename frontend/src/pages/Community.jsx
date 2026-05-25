import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatApiError, mediaUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Megaphone, MessageSquare, Plus, Pin, Lock, Trash2, Paperclip,
  Send, ArrowLeft,
} from "lucide-react";

const PROPERTY_SCOPED = ["landlord", "tenant", "caretaker"];

function isImage(p) {
  return /\.(png|jpe?g|gif|webp|heic|heif)$/i.test(p);
}

function Attachment({ path }) {
  const url = mediaUrl(path);
  const fname = path.split("/").pop();
  if (isImage(path)) {
    return (
      <a href={url} target="_blank" rel="noreferrer">
        <img src={url} alt={fname} className="w-24 h-24 object-cover rounded-md border border-zinc-200" />
      </a>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center gap-2 px-3 py-2 bg-zinc-50 border border-zinc-200 rounded-md text-xs hover:bg-zinc-100"
    >
      <Paperclip className="w-3.5 h-3.5" />
      <span className="font-mono-num truncate max-w-[200px]">{fname}</span>
    </a>
  );
}

export default function CommunityPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("announcements");

  return (
    <div data-testid="community-page">
      <PageHeader
        overline="Community"
        title="Tenant Community Hub"
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-zinc-100 rounded-md mb-6">
          <TabsTrigger value="announcements" data-testid="tab-announcements" className="rounded-sm">
            <Megaphone className="w-4 h-4 mr-1.5" /> Announcements
          </TabsTrigger>
          <TabsTrigger value="forum" data-testid="tab-forum" className="rounded-sm">
            <MessageSquare className="w-4 h-4 mr-1.5" /> Forum
          </TabsTrigger>
        </TabsList>
        <TabsContent value="announcements">
          <Announcements user={user} />
        </TabsContent>
        <TabsContent value="forum">
          <Forum user={user} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Announcements({ user }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [properties, setProperties] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    scope: user.role === "admin" ? "global" : "property",
    property_id: "",
    title: "",
    body: "",
    pinned: false,
  });
  const [files, setFiles] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/announcements");
    setItems(r.data || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    if (user.role === "landlord" || user.role === "admin") {
      api.get("/properties").then((r) => setProperties(r.data || []));
    }
  }, [load, user.role]);

  const canPost = user.role === "admin" || user.role === "landlord";

  const submit = async (e) => {
    e.preventDefault();
    try {
      const fd = new FormData();
      fd.append("scope", form.scope);
      fd.append("title", form.title);
      fd.append("body", form.body);
      fd.append("pinned", form.pinned ? "true" : "false");
      if (form.scope === "property") fd.append("property_id", form.property_id);
      files.forEach((f) => fd.append("attachments", f));
      await api.post("/announcements", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Announcement posted");
      setOpen(false);
      setForm({ scope: user.role === "admin" ? "global" : "property", property_id: "", title: "", body: "", pinned: false });
      setFiles([]);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this announcement?")) return;
    await api.delete(`/announcements/${id}`);
    toast.success("Deleted");
    load();
  };

  const togglePin = async (id) => {
    await api.patch(`/announcements/${id}/pin`);
    load();
  };

  return (
    <div data-testid="announcements-section">
      {canPost && (
        <div className="mb-6 flex justify-end">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="new-announcement-button">
                <Plus className="w-4 h-4 mr-1.5" /> New Announcement
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-md max-w-lg">
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">New Announcement</DialogTitle>
                <DialogDescription>Reach your tenants instantly.</DialogDescription>
              </DialogHeader>
              <form onSubmit={submit} className="space-y-4" data-testid="announcement-form">
                {user.role === "admin" && (
                  <div>
                    <Label className="overline">Scope</Label>
                    <select
                      value={form.scope}
                      onChange={(e) => setForm({ ...form, scope: e.target.value })}
                      className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                      data-testid="announcement-scope"
                    >
                      <option value="global">Global (all users)</option>
                      <option value="property">Specific property</option>
                    </select>
                  </div>
                )}
                {form.scope === "property" && (
                  <div>
                    <Label className="overline">Property</Label>
                    <select
                      required
                      value={form.property_id}
                      onChange={(e) => setForm({ ...form, property_id: e.target.value })}
                      className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                      data-testid="announcement-property-select"
                    >
                      <option value="">Select property...</option>
                      {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                )}
                <div>
                  <Label className="overline">Title</Label>
                  <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1" data-testid="announcement-title-input" />
                </div>
                <div>
                  <Label className="overline">Message</Label>
                  <Textarea required rows={5} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="mt-1" data-testid="announcement-body-input" />
                </div>
                <div>
                  <Label className="overline">Attachments (PDF or images, max 5MB each)</Label>
                  <Input
                    type="file"
                    accept="image/*,application/pdf"
                    multiple
                    onChange={(e) => setFiles(Array.from(e.target.files || []).slice(0, 5))}
                    className="mt-1"
                    data-testid="announcement-files-input"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} data-testid="announcement-pin-checkbox" />
                  Pin to top
                </label>
                <DialogFooter>
                  <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="announcement-submit-button">Post</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {loading ? <div className="text-zinc-500">Loading...</div>
        : items.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="announcements-empty">
            <Megaphone className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No announcements yet</div>
            <div className="text-sm text-zinc-500">Check back soon.</div>
          </div>
        ) : (
          <div className="space-y-4" data-testid="announcements-list">
            {items.map((a) => (
              <div key={a.id} className="bg-white border border-zinc-200 rounded-md p-5" data-testid={`announcement-${a.id}`}>
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {a.pinned && <span className="badge-status bg-amber-50 text-amber-800 flex items-center gap-1"><Pin className="w-3 h-3" /> PINNED</span>}
                    <span className={`badge-status ${a.scope === "global" ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-700"}`}>
                      {a.scope === "global" ? "GLOBAL" : "PROPERTY"}
                    </span>
                    <span className="overline text-zinc-500">by {a.author_name} · {a.author_role}</span>
                  </div>
                  {(user.role === "admin" || a.author_id === user.id) && (
                    <div className="flex gap-1">
                      <button onClick={() => togglePin(a.id)} className="text-zinc-400 hover:text-amber-600 p-1" title="Toggle pin" data-testid={`announcement-pin-${a.id}`}>
                        <Pin className="w-4 h-4" />
                      </button>
                      <button onClick={() => remove(a.id)} className="text-zinc-400 hover:text-red-600 p-1" title="Delete" data-testid={`announcement-delete-${a.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
                <h3 className="font-display font-bold text-xl mb-2">{a.title}</h3>
                <p className="text-zinc-700 whitespace-pre-wrap text-sm leading-relaxed">{a.body}</p>
                {a.attachments?.length > 0 && (
                  <div className="flex gap-2 flex-wrap mt-4">
                    {a.attachments.map((p) => <Attachment key={p} path={p} />)}
                  </div>
                )}
                <div className="text-[10px] text-zinc-400 uppercase tracking-wider mt-3">
                  {new Date(a.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

function Forum({ user }) {
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);
  const [activeThread, setActiveThread] = useState(null);
  const [replies, setReplies] = useState([]);
  const [open, setOpen] = useState(false);
  const [properties, setProperties] = useState([]);
  const [form, setForm] = useState({ property_id: "", title: "", body: "" });
  const [files, setFiles] = useState([]);
  const [replyBody, setReplyBody] = useState("");
  const [replyFiles, setReplyFiles] = useState([]);

  const loadThreads = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/forum/threads");
    setThreads(r.data || []);
    setLoading(false);
  }, []);

  const loadThread = useCallback(async (id) => {
    const r = await api.get(`/forum/threads/${id}`);
    setActiveThread(r.data.thread);
    setReplies(r.data.replies || []);
  }, []);

  useEffect(() => {
    loadThreads();
    if (PROPERTY_SCOPED.includes(user.role) || user.role === "admin") {
      api.get("/properties").then((r) => {
        setProperties(r.data || []);
        if (user.role === "tenant" && r.data?.[0]) {
          setForm((f) => ({ ...f, property_id: r.data[0].id }));
        }
      });
    }
  }, [loadThreads, user.role]);

  useEffect(() => {
    if (activeId) loadThread(activeId);
  }, [activeId, loadThread]);

  const createThread = async (e) => {
    e.preventDefault();
    try {
      const fd = new FormData();
      fd.append("property_id", form.property_id);
      fd.append("title", form.title);
      fd.append("body", form.body);
      files.forEach((f) => fd.append("attachments", f));
      await api.post("/forum/threads", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Thread posted");
      setOpen(false);
      setForm({ property_id: properties[0]?.id || "", title: "", body: "" });
      setFiles([]);
      loadThreads();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const submitReply = async (e) => {
    e.preventDefault();
    if (!replyBody.trim()) return;
    try {
      const fd = new FormData();
      fd.append("body", replyBody);
      replyFiles.forEach((f) => fd.append("attachments", f));
      await api.post(`/forum/threads/${activeId}/replies`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setReplyBody("");
      setReplyFiles([]);
      loadThread(activeId);
      loadThreads();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to reply"));
    }
  };

  const moderate = async (action) => {
    const body = action === "pin"
      ? { pinned: !activeThread.pinned }
      : { locked: !activeThread.locked };
    await api.patch(`/forum/threads/${activeId}/moderate?${action}=${!activeThread[action === "pin" ? "pinned" : "locked"]}`);
    loadThread(activeId);
    loadThreads();
  };

  const deleteThread = async () => {
    if (!window.confirm("Delete thread and all replies?")) return;
    await api.delete(`/forum/threads/${activeId}`);
    toast.success("Deleted");
    setActiveId(null);
    setActiveThread(null);
    loadThreads();
  };

  if (activeId && activeThread) {
    const isMod = user.role === "admin" || (user.role === "landlord" && activeThread.landlord_id === user.id);
    return (
      <div data-testid="forum-thread-detail">
        <button onClick={() => { setActiveId(null); setActiveThread(null); }} className="text-sm font-semibold text-zinc-600 hover:text-zinc-950 mb-4 flex items-center gap-1" data-testid="forum-back-button">
          <ArrowLeft className="w-4 h-4" /> Back to threads
        </button>
        <div className="bg-white border border-zinc-200 rounded-md p-5 mb-4">
          <div className="flex items-start justify-between mb-3 gap-3">
            <div className="flex items-center gap-2 flex-wrap">
              {activeThread.pinned && <span className="badge-status bg-amber-50 text-amber-800 flex items-center gap-1"><Pin className="w-3 h-3" /> PINNED</span>}
              {activeThread.locked && <span className="badge-status bg-red-50 text-red-700 flex items-center gap-1"><Lock className="w-3 h-3" /> LOCKED</span>}
              <span className="overline text-zinc-500">by {activeThread.author_name} · {activeThread.author_role}</span>
            </div>
            {(isMod || activeThread.author_id === user.id) && (
              <div className="flex gap-1">
                {isMod && (
                  <>
                    <button onClick={() => moderate("pin")} className="text-zinc-400 hover:text-amber-600 p-1" data-testid="thread-pin"><Pin className="w-4 h-4" /></button>
                    <button onClick={() => moderate("lock")} className="text-zinc-400 hover:text-zinc-900 p-1" data-testid="thread-lock"><Lock className="w-4 h-4" /></button>
                  </>
                )}
                <button onClick={deleteThread} className="text-zinc-400 hover:text-red-600 p-1" data-testid="thread-delete"><Trash2 className="w-4 h-4" /></button>
              </div>
            )}
          </div>
          <h2 className="font-display font-black text-3xl mb-3 tracking-tight">{activeThread.title}</h2>
          <p className="text-zinc-700 whitespace-pre-wrap text-sm leading-relaxed">{activeThread.body}</p>
          {activeThread.attachments?.length > 0 && (
            <div className="flex gap-2 flex-wrap mt-4">
              {activeThread.attachments.map((p) => <Attachment key={p} path={p} />)}
            </div>
          )}
          <div className="text-[10px] text-zinc-400 uppercase tracking-wider mt-3">
            {new Date(activeThread.created_at).toLocaleString()}
          </div>
        </div>

        <div className="space-y-3 mb-6" data-testid="forum-replies-list">
          {replies.map((r) => (
            <div key={r.id} className="bg-white border border-zinc-200 rounded-md p-4 ml-6" data-testid={`forum-reply-${r.id}`}>
              <div className="overline text-zinc-500 mb-1">{r.author_name} · {r.author_role} · {new Date(r.created_at).toLocaleString()}</div>
              <p className="text-sm text-zinc-800 whitespace-pre-wrap leading-relaxed">{r.body}</p>
              {r.attachments?.length > 0 && (
                <div className="flex gap-2 flex-wrap mt-2">
                  {r.attachments.map((p) => <Attachment key={p} path={p} />)}
                </div>
              )}
            </div>
          ))}
        </div>

        {!activeThread.locked && (
          <form onSubmit={submitReply} className="bg-white border border-zinc-200 rounded-md p-4" data-testid="forum-reply-form">
            <Label className="overline">Your reply</Label>
            <Textarea
              required
              rows={3}
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              className="mt-1 mb-3"
              placeholder="Share your thoughts..."
              data-testid="forum-reply-body"
            />
            <div className="flex items-center justify-between gap-2">
              <Input
                type="file"
                accept="image/*,application/pdf"
                multiple
                onChange={(e) => setReplyFiles(Array.from(e.target.files || []).slice(0, 5))}
                className="max-w-xs h-9 text-xs"
                data-testid="forum-reply-files"
              />
              <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="forum-reply-submit">
                <Send className="w-3.5 h-3.5 mr-1.5" /> Reply
              </Button>
            </div>
          </form>
        )}
      </div>
    );
  }

  return (
    <div data-testid="forum-threads-list">
      <div className="flex items-center justify-between mb-6">
        <div className="text-sm text-zinc-500">
          {threads.length} {threads.length === 1 ? "thread" : "threads"} · {user.role === "tenant" ? "Your property forum" : user.role === "admin" ? "All property forums" : "Your properties"}
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="new-thread-button">
              <Plus className="w-4 h-4 mr-1.5" /> New Thread
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-md max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display font-black text-2xl">Start a Thread</DialogTitle>
            </DialogHeader>
            <form onSubmit={createThread} className="space-y-4" data-testid="forum-thread-form">
              {properties.length > 1 && (
                <div>
                  <Label className="overline">Property</Label>
                  <select
                    required
                    value={form.property_id}
                    onChange={(e) => setForm({ ...form, property_id: e.target.value })}
                    className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                    data-testid="forum-thread-property"
                  >
                    <option value="">Select property...</option>
                    {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <Label className="overline">Title</Label>
                <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1" data-testid="forum-thread-title" />
              </div>
              <div>
                <Label className="overline">Message</Label>
                <Textarea required rows={5} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="mt-1" data-testid="forum-thread-body" />
              </div>
              <div>
                <Label className="overline">Attachments (PDF/images, max 5MB)</Label>
                <Input type="file" accept="image/*,application/pdf" multiple onChange={(e) => setFiles(Array.from(e.target.files || []).slice(0, 5))} className="mt-1" data-testid="forum-thread-files" />
              </div>
              <DialogFooter>
                <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="forum-thread-submit">Post Thread</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      {loading ? <div className="text-zinc-500">Loading...</div>
        : threads.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="forum-empty">
            <MessageSquare className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No threads yet</div>
            <div className="text-sm text-zinc-500">Be the first to start a conversation.</div>
          </div>
        ) : (
          <div className="space-y-3">
            {threads.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveId(t.id)}
                className="bg-white border border-zinc-200 rounded-md p-4 w-full text-left hover:border-zinc-400 transition-colors"
                data-testid={`forum-thread-card-${t.id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      {t.pinned && <Pin className="w-3 h-3 text-amber-600" />}
                      {t.locked && <Lock className="w-3 h-3 text-red-600" />}
                      <h3 className="font-display font-bold text-base truncate">{t.title}</h3>
                    </div>
                    <p className="text-sm text-zinc-600 line-clamp-1">{t.body}</p>
                    <div className="text-[10px] text-zinc-400 uppercase tracking-wider mt-2">
                      by {t.author_name} · {new Date(t.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono-num text-lg font-bold text-zinc-900">{t.replies_count || 0}</div>
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider">replies</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
    </div>
  );
}
