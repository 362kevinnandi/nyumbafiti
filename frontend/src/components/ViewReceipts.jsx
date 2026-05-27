import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { Eye, Users } from "lucide-react";

/**
 * Read receipts dropdown. Visible to author + admin.
 * Shows who viewed an announcement and when.
 */
export default function ViewReceipts({ announcementId, authorId, currentUser }) {
  const [data, setData] = useState({ total: 0, views: [] });
  const [open, setOpen] = useState(false);

  const canSee =
    currentUser?.role === "admin" || currentUser?.id === authorId;

  useEffect(() => {
    if (!canSee || !open) return;
    api.get(`/social/announcement/${announcementId}/views`).then((r) => {
      setData(r.data || { total: 0, views: [] });
    }).catch(() => {});
  }, [open, announcementId, canSee]);

  if (!canSee) return null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-1 px-2 h-7 rounded-full border border-zinc-200 bg-white text-xs font-semibold text-zinc-600 hover:border-zinc-400"
          data-testid={`view-receipts-${announcementId}`}
          title="Read receipts"
        >
          <Eye className="w-3.5 h-3.5" />
          <span className="font-mono-num">{data.total || 0}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0 max-h-80 overflow-y-auto" data-testid={`view-receipts-panel-${announcementId}`}>
        <div className="px-4 py-3 border-b border-zinc-100 bg-zinc-50">
          <div className="font-display font-bold text-sm flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" /> {data.total} views
          </div>
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mt-0.5">Read receipts (private to author & admin)</div>
        </div>
        {data.views.length === 0 ? (
          <div className="py-6 text-center text-xs text-zinc-500">No views yet</div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {data.views.map((v) => (
              <div key={v.id} className="px-4 py-2.5">
                <div className="text-sm font-semibold text-zinc-900">{v.user_name}</div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{v.user_role}</div>
                <div className="text-xs text-zinc-600 mt-0.5">
                  Last viewed: {new Date(v.last_viewed_at).toLocaleString()}
                  {v.view_count > 1 && ` · ${v.view_count} times`}
                </div>
              </div>
            ))}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
