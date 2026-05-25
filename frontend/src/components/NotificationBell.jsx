import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Bell, Inbox } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const load = async () => {
    try {
      const r = await api.get("/notifications?limit=15");
      setItems(r.data.items || []);
      setUnread(r.data.unread_count || 0);
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const markAll = async () => {
    await api.post("/notifications/mark-all-read");
    load();
  };

  const markOne = async (id) => {
    await api.patch(`/notifications/${id}/read`);
    load();
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          className="relative p-2 rounded-md hover:bg-zinc-100 transition-colors"
          data-testid="notifications-bell"
          aria-label="Notifications"
        >
          <Bell className="w-5 h-5 text-zinc-700" strokeWidth={1.8} />
          {unread > 0 && (
            <span
              className="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center"
              data-testid="notifications-unread-count"
            >
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96 max-h-[80vh] overflow-y-auto p-0" data-testid="notifications-dropdown">
        <div className="px-4 py-3 border-b border-zinc-100 flex items-center justify-between">
          <div className="font-display font-black text-base">Notifications</div>
          {unread > 0 && (
            <button onClick={markAll} className="text-xs text-zinc-500 hover:text-zinc-950 font-semibold" data-testid="notifications-mark-all-read">
              Mark all read
            </button>
          )}
        </div>
        {items.length === 0 ? (
          <div className="py-12 text-center" data-testid="notifications-empty">
            <Inbox className="w-8 h-8 mx-auto text-zinc-300 mb-2" />
            <div className="text-sm text-zinc-500">You're all caught up</div>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {items.map((n) => {
              const inner = (
                <div
                  className={`px-4 py-3 flex gap-3 cursor-pointer hover:bg-zinc-50 transition-colors ${
                    !n.read ? "bg-amber-50/40" : ""
                  }`}
                  onClick={() => markOne(n.id)}
                  data-testid={`notification-item-${n.id}`}
                >
                  {!n.read && <span className="w-2 h-2 mt-2 rounded-full bg-amber-500 shrink-0" />}
                  <div className={`flex-1 ${n.read ? "ml-5" : ""}`}>
                    <div className="text-sm font-semibold text-zinc-900 line-clamp-1">{n.title}</div>
                    <div className="text-xs text-zinc-600 mt-0.5 line-clamp-2">{n.body}</div>
                    <div className="text-[10px] text-zinc-400 mt-1 uppercase tracking-wider">
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              );
              return n.link ? (
                <Link key={n.id} to={n.link} onClick={() => setOpen(false)}>{inner}</Link>
              ) : (
                <div key={n.id}>{inner}</div>
              );
            })}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
