import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ThumbsUp, Heart, PartyPopper, HandHeart } from "lucide-react";

const REACTIONS = [
  { type: "like", icon: ThumbsUp, label: "Like", color: "text-sky-600" },
  { type: "love", icon: Heart, label: "Love", color: "text-rose-600" },
  { type: "celebrate", icon: PartyPopper, label: "Celebrate", color: "text-amber-600" },
  { type: "support", icon: HandHeart, label: "Support", color: "text-emerald-600" },
];

/**
 * Reactions bar for announcements, forum threads or replies.
 * targetType: 'announcement' | 'thread' | 'reply'
 */
export default function ReactionsBar({ targetType, targetId }) {
  const [counts, setCounts] = useState({});
  const [my, setMy] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const r = await api.get(`/social/${targetType}/${targetId}/reactions`);
      setCounts(r.data.counts || {});
      setMy(r.data.my_reaction);
    } catch {/* silent */}
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [targetType, targetId]);

  const onClick = async (type) => {
    setLoading(true);
    try {
      const r = await api.post(`/social/${targetType}/${targetId}/react?reaction=${type}`);
      setCounts(r.data.counts || {});
      setMy(my === type ? null : type);
    } catch {/* */} finally { setLoading(false); }
  };

  return (
    <div className="flex items-center gap-1.5 flex-wrap" data-testid={`reactions-bar-${targetType}-${targetId}`}>
      {REACTIONS.map((r) => {
        const Icon = r.icon;
        const active = my === r.type;
        const n = counts[r.type] || 0;
        return (
          <button
            key={r.type}
            type="button"
            onClick={() => onClick(r.type)}
            disabled={loading}
            className={`flex items-center gap-1 px-2.5 h-7 rounded-full border text-xs font-semibold transition-all ${
              active
                ? `bg-amber-50 border-amber-300 ${r.color}`
                : "bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400"
            }`}
            data-testid={`reaction-${r.type}-${targetId}`}
            title={r.label}
          >
            <Icon className={`w-3.5 h-3.5 ${active ? r.color : ""}`} fill={active && r.type !== "like" ? "currentColor" : "none"} />
            {n > 0 && <span className="font-mono-num">{n}</span>}
          </button>
        );
      })}
    </div>
  );
}
