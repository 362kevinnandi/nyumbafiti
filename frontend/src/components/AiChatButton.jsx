import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Sparkles, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

const SUGGESTIONS = [
  "Westlands 2 bedroom under 30k",
  "Cheapest bedsitter near town",
  "How do paid viewings work?",
  "Recommend an own-compound for lease",
];

export default function AiChatButton() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  const reset = () => {
    setMessages([]);
    setSessionId(null);
    setInput("");
  };

  const send = async (text) => {
    const body = (text ?? input).trim();
    if (!body || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: body }]);
    setSending(true);
    try {
      const r = await api.post("/ai/chat", { session_id: sessionId, message: body });
      setSessionId(r.data.session_id);
      setMessages((m) => [...m, { role: "assistant", text: r.data.reply, used_llm: r.data.used_llm }]);
    } catch (err) {
      toast.error(formatApiError(err, "AI failed"));
    } finally {
      setSending(false);
    }
  };

  // Extract listing_id references from assistant text → render clickable chips
  const extractListingChips = (text) => {
    const matches = [...text.matchAll(/listing_id=([a-f0-9-]{8,})/gi)];
    return matches.map((m) => m[1]);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-zinc-950 h-10 rounded-md text-sm shadow-sm" data-testid="ai-chat-button">
          <Sparkles className="w-4 h-4 mr-1.5" /> AI Concierge
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-2xl max-w-lg p-0 overflow-hidden" data-testid="ai-chat-dialog">
        <DialogHeader className="px-6 pt-5 pb-3 border-b border-zinc-100 bg-gradient-to-r from-amber-50 to-amber-100/30">
          <DialogTitle className="font-display font-black text-2xl flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-600" /> Nyumba Concierge
          </DialogTitle>
          <DialogDescription>Ask anything about rentals in Nairobi — areas, price, units, how viewings work.</DialogDescription>
        </DialogHeader>

        <div ref={scrollRef} className="px-6 py-4 max-h-[55vh] min-h-[280px] overflow-y-auto space-y-3" data-testid="ai-chat-messages">
          {messages.length === 0 ? (
            <div className="space-y-3">
              <div className="text-sm text-zinc-600 leading-relaxed">
                👋 Hi! I help prospects find Nairobi rentals. Try one of these:
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="px-3 py-1.5 rounded-full bg-white border border-zinc-200 text-xs font-semibold text-zinc-700 hover:border-amber-400 hover:bg-amber-50 transition-all"
                    data-testid={`ai-chat-suggestion-${s.replace(/\s+/g, "-").toLowerCase()}`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, idx) => {
              const isUser = m.role === "user";
              const chips = !isUser ? extractListingChips(m.text) : [];
              const cleaned = !isUser ? m.text.replace(/\blisting_id=[a-f0-9-]+\b/gi, "").replace(/\s+/g, " ").trim() : m.text;
              return (
                <div key={idx} className={`flex ${isUser ? "justify-end" : "justify-start"}`} data-testid={`ai-chat-msg-${idx}`}>
                  <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    isUser ? "bg-zinc-950 text-white" : "bg-amber-50 text-zinc-900 border border-amber-100"
                  }`}>
                    <div className="whitespace-pre-wrap">{cleaned}</div>
                    {chips.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-amber-200">
                        {chips.map((id) => (
                          <Link
                            key={id}
                            to={`/marketplace/${id}`}
                            className="text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-zinc-950 text-white hover:bg-zinc-800"
                            data-testid={`ai-chat-listing-link-${id}`}
                          >
                            View →
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-amber-50 border border-amber-100 rounded-2xl px-4 py-2.5 text-sm flex items-center gap-2 text-zinc-700">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Thinking...
              </div>
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="px-4 py-3 border-t border-zinc-100 bg-white flex gap-2"
          data-testid="ai-chat-form"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. 1 bed in Kilimani under 40k"
            disabled={sending}
            data-testid="ai-chat-input"
            className="flex-1"
          />
          <Button type="submit" disabled={sending || !input.trim()} className="bg-zinc-950 hover:bg-zinc-800 px-3" data-testid="ai-chat-send">
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
