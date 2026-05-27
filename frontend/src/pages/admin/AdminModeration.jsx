import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  Trash2, ShieldAlert, Megaphone, MessageSquare, ShoppingBag, Calendar,
  QrCode, Sparkles, Wrench, FileSignature, Eye, Search,
} from "lucide-react";

const TABS = [
  { value: "summary", label: "Overview", icon: ShieldAlert },
  { value: "yard-sale", label: "Yard Sale", icon: ShoppingBag, endpoint: "/admin/moderation/yard-sale" },
  { value: "announcements", label: "Announcements", icon: Megaphone, endpoint: "/admin/moderation/announcements" },
  { value: "forum/threads", label: "Forum", icon: MessageSquare, endpoint: "/admin/moderation/forum/threads" },
  { value: "viewings", label: "Viewings", icon: Calendar, endpoint: "/admin/moderation/viewings" },
  { value: "visitor-passes", label: "Visitor Passes", icon: QrCode, endpoint: "/admin/moderation/visitor-passes" },
  { value: "issues", label: "Issues", icon: Wrench, endpoint: "/admin/moderation/issues" },
  { value: "leases", label: "Leases", icon: FileSignature, endpoint: "/admin/moderation/leases" },
  { value: "ai-conversations", label: "AI Chats", icon: Sparkles, endpoint: "/admin/ai-conversations" },
];

export default function AdminModerationPage() {
  const [tab, setTab] = useState("summary");
  const [summary, setSummary] = useState(null);

  const loadSummary = useCallback(async () => {
    try {
      const r = await api.get("/admin/moderation/summary");
      setSummary(r.data);
    } catch (err) {
      toast.error(formatApiError(err, "Failed to load summary"));
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  return (
    <div data-testid="admin-moderation-page">
      <PageHeader
        overline="God-mode"
        title="Platform Moderation"
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-zinc-100 rounded-md mb-6 flex-wrap h-auto p-1" data-testid="admin-moderation-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <TabsTrigger key={t.value} value={t.value} className="rounded-sm text-xs" data-testid={`admin-mod-tab-${t.value.replace("/", "-")}`}>
                <Icon className="w-3.5 h-3.5 mr-1.5" /> {t.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="summary">
          <SummaryGrid summary={summary} onJump={setTab} />
        </TabsContent>

        {TABS.filter((t) => t.endpoint).map((t) => (
          <TabsContent key={t.value} value={t.value}>
            <ModerationList
              endpoint={t.endpoint}
              tabValue={t.value}
              onChange={loadSummary}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function SummaryGrid({ summary, onJump }) {
  if (!summary) return <div className="text-zinc-500" data-testid="summary-loading">Loading...</div>;
  const cards = [
    { label: "Users", count: summary.users, tab: null },
    { label: "Properties", count: summary.properties, tab: null },
    { label: "Units", count: summary.units, tab: null },
    { label: "Yard sale", count: summary.yard_sale, tab: "yard-sale" },
    { label: "Announcements", count: summary.announcements, tab: "announcements" },
    { label: "Forum threads", count: summary.forum_threads, tab: "forum/threads" },
    { label: "Forum replies", count: summary.forum_replies, tab: null },
    { label: "Viewings", count: summary.viewings, tab: "viewings" },
    { label: "Visitor passes", count: summary.visitor_passes, tab: "visitor-passes" },
    { label: "Issues", count: summary.issues, tab: "issues" },
    { label: "Leases", count: summary.leases, tab: "leases" },
    { label: "AI Conversations", count: summary.ai_conversations, tab: "ai-conversations" },
    { label: "Reactions", count: summary.reactions, tab: null },
    { label: "Payments", count: summary.payments, tab: null },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="moderation-summary-grid">
      {cards.map((c) => (
        <button
          key={c.label}
          onClick={() => c.tab && onJump(c.tab)}
          disabled={!c.tab}
          className={`text-left bg-white border border-zinc-200 rounded-md p-4 transition-all ${c.tab ? "hover:border-zinc-950 cursor-pointer" : "opacity-90 cursor-default"}`}
          data-testid={`summary-card-${c.label.toLowerCase().replace(/\s+/g, "-")}`}
        >
          <div className="overline text-zinc-500">{c.label}</div>
          <div className="font-display font-black text-3xl tracking-tight font-mono-num mt-1">{c.count}</div>
          {c.tab && <div className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Moderate →</div>}
        </button>
      ))}
    </div>
  );
}

function ModerationList({ endpoint, tabValue, onChange }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(endpoint);
      setItems(r.data || []);
    } catch (err) {
      toast.error(formatApiError(err, "Failed to load"));
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => { load(); }, [load]);

  const del = async (id) => {
    if (!window.confirm("Delete permanently? This cannot be undone.")) return;
    try {
      // For AI conversations the endpoint is /admin/moderation/ai-conversations/{id}
      const base = tabValue === "ai-conversations" ? "/admin/moderation/ai-conversations" : endpoint;
      await api.delete(`${base}/${id}`);
      toast.success("Deleted");
      load();
      onChange?.();
    } catch (err) {
      toast.error(formatApiError(err, "Delete failed"));
    }
  };

  const filtered = items.filter((it) => {
    if (!q.trim()) return true;
    const hay = JSON.stringify(it).toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  return (
    <div data-testid={`moderation-list-${tabValue.replace("/", "-")}`}>
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search any field..."
            className="pl-9 h-9"
            data-testid={`moderation-search-${tabValue.replace("/", "-")}`}
          />
        </div>
        <div className="text-xs text-zinc-500 uppercase tracking-wider">
          {filtered.length} of {items.length}
        </div>
      </div>

      {loading ? <div className="text-zinc-500">Loading...</div>
        : filtered.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid={`moderation-empty-${tabValue.replace("/", "-")}`}>
            <div className="font-display font-bold text-lg">No records</div>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((it) => (
              <RowCard key={it.id || it.session_id} item={it} tabValue={tabValue} onDelete={del} />
            ))}
          </div>
        )}
    </div>
  );
}

function RowCard({ item, tabValue, onDelete }) {
  const id = item.id || item.session_id;
  const fmtDate = (t) => {
    if (!t) return "—";
    const d = new Date(t);
    return isNaN(d.getTime()) ? String(t) : d.toLocaleString();
  };
  const renderBody = () => {
    switch (tabValue) {
      case "yard-sale":
        return (
          <>
            <div className="font-display font-bold">{item.title}</div>
            <div className="text-xs text-zinc-500">by {item.seller_name} · {item.seller_role || "?"} · {item.category}</div>
            <div className="text-xs text-zinc-600 mt-1">{formatKES(item.price)} · scope={item.scope} · featured={String(!!item.featured)} · status={item.status}</div>
          </>
        );
      case "announcements":
        return (
          <>
            <div className="font-display font-bold">{item.title}</div>
            <div className="text-xs text-zinc-500">by {item.author_name} ({item.author_role}) · {item.scope} · pinned={String(!!item.pinned)}</div>
            <p className="text-xs text-zinc-600 mt-1 line-clamp-2">{item.body}</p>
          </>
        );
      case "forum/threads":
        return (
          <>
            <div className="font-display font-bold">{item.title}</div>
            <div className="text-xs text-zinc-500">by {item.author_name} ({item.author_role}) · replies={item.replies_count || 0}</div>
            <p className="text-xs text-zinc-600 mt-1 line-clamp-2">{item.body}</p>
          </>
        );
      case "viewings":
        return (
          <>
            <div className="font-display font-bold">{item.prospect_name} · <span className="font-normal text-sm">{item.prospect_email}</span></div>
            <div className="text-xs text-zinc-500">{item.property_name} · {item.scheduled_date} {item.scheduled_time} · status={item.status}</div>
          </>
        );
      case "visitor-passes":
        return (
          <>
            <div className="font-display font-bold">{item.visitor_name} {item.is_prospect_pass && <span className="badge-status bg-amber-50 text-amber-800 ml-1">prospect</span>}</div>
            <div className="text-xs text-zinc-500">host={item.tenant_name} · landlord={item.landlord_id?.slice(0,8)} · status={item.status}</div>
            <div className="text-xs text-zinc-500">expected {fmtDate(item.expected_time)} · expires {fmtDate(item.expires_at)}</div>
          </>
        );
      case "issues":
        return (
          <>
            <div className="font-display font-bold">{item.title}</div>
            <div className="text-xs text-zinc-500">{item.category} · status={item.status} · severity={item.severity}</div>
            <p className="text-xs text-zinc-600 mt-1 line-clamp-2">{item.description}</p>
          </>
        );
      case "leases":
        return (
          <>
            <div className="font-display font-bold">Lease #{id.slice(0,8)}</div>
            <div className="text-xs text-zinc-500">type={item.agreement_type} · status={item.status} · rent={formatKES(item.monthly_rent)}</div>
          </>
        );
      case "ai-conversations":
        return (
          <>
            <div className="font-display font-bold">{item.user_name} <span className="text-zinc-500 text-xs">({item.user_role})</span></div>
            <div className="text-xs text-zinc-500">msgs={item.message_count} · {new Date(item.updated_at).toLocaleString()}</div>
            <p className="text-xs text-zinc-600 mt-1 line-clamp-2 italic">"{item.preview}"</p>
          </>
        );
      default:
        return <pre className="text-xs">{JSON.stringify(item, null, 2)}</pre>;
    }
  };

  return (
    <div className="bg-white border border-zinc-200 rounded-md p-4 flex items-start justify-between gap-3" data-testid={`moderation-row-${id}`}>
      <div className="flex-1 min-w-0">{renderBody()}</div>
      <div className="flex items-center gap-2 shrink-0">
        {tabValue === "yard-sale" && (
          <Link to={`/yard-sale/${id}`} className="p-2 text-zinc-400 hover:text-zinc-950" data-testid={`moderation-view-${id}`}>
            <Eye className="w-4 h-4" />
          </Link>
        )}
        <button
          onClick={() => onDelete(id)}
          className="p-2 text-zinc-400 hover:text-red-600"
          data-testid={`moderation-delete-${id}`}
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
