import { useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError, formatKES } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Sparkles, ArrowRight } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = [
  { value: "apartment", label: "Apartment" },
  { value: "bedsitter", label: "Bedsitter" },
  { value: "single_room", label: "Single Room" },
  { value: "self_contained", label: "Self-Contained" },
  { value: "standalone", label: "Standalone" },
  { value: "compound", label: "Compound" },
  { value: "airbnb", label: "Airbnb" },
];

export default function AiRecommendButton() {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState(null);
  const [form, setForm] = useState({
    max_rent: "", preferred_bedrooms: "", area_keywords: "",
    preferred_categories: [],
  });

  const toggleCat = (v) => {
    setForm((f) => ({
      ...f,
      preferred_categories: f.preferred_categories.includes(v)
        ? f.preferred_categories.filter((x) => x !== v)
        : [...f.preferred_categories, v],
    }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setResults(null);
    try {
      const r = await api.post("/ai/recommend-properties", {
        max_rent: form.max_rent ? Number(form.max_rent) : null,
        preferred_bedrooms: form.preferred_bedrooms ? Number(form.preferred_bedrooms) : null,
        area_keywords: form.area_keywords || null,
        preferred_categories: form.preferred_categories.length ? form.preferred_categories : null,
      });
      setResults(r.data);
    } catch (err) {
      toast.error(formatApiError(err, "AI failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setResults(null); }}>
      <DialogTrigger asChild>
        <Button className="bg-gradient-to-r from-zinc-950 to-zinc-700 hover:from-zinc-800 hover:to-zinc-600 h-10 rounded-md text-sm" data-testid="ai-recommend-button">
          <Sparkles className="w-4 h-4 mr-1.5" /> AI Match
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-lg max-h-[85vh] overflow-y-auto" data-testid="ai-recommend-dialog">
        <DialogHeader>
          <DialogTitle className="font-display font-black text-2xl flex items-center gap-2">
            <Sparkles className="w-6 h-6" /> AI Property Match
          </DialogTitle>
          <DialogDescription>Tell us what you need. We'll pick your top 3.</DialogDescription>
        </DialogHeader>

        {!results ? (
          <form onSubmit={submit} className="space-y-4" data-testid="ai-recommend-form">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="overline">Max rent (KES)</Label>
                <Input type="number" value={form.max_rent} onChange={(e) => setForm({ ...form, max_rent: e.target.value })} placeholder="30000" className="mt-1" data-testid="ai-max-rent" />
              </div>
              <div>
                <Label className="overline">Bedrooms</Label>
                <Input type="number" value={form.preferred_bedrooms} onChange={(e) => setForm({ ...form, preferred_bedrooms: e.target.value })} placeholder="1" className="mt-1" data-testid="ai-bedrooms" />
              </div>
            </div>
            <div>
              <Label className="overline">Preferred areas (comma separated)</Label>
              <Input value={form.area_keywords} onChange={(e) => setForm({ ...form, area_keywords: e.target.value })} placeholder="westlands, kilimani" className="mt-1" data-testid="ai-area" />
            </div>
            <div>
              <Label className="overline">Property types</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                {CATEGORIES.map((c) => {
                  const active = form.preferred_categories.includes(c.value);
                  return (
                    <button
                      type="button"
                      key={c.value}
                      onClick={() => toggleCat(c.value)}
                      className={`px-3 h-8 rounded-full border text-xs font-semibold transition-all ${
                        active ? "bg-zinc-950 text-white border-zinc-950" : "bg-white border-zinc-300 text-zinc-700"
                      }`}
                      data-testid={`ai-cat-${c.value}`}
                    >
                      {c.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={submitting} className="bg-zinc-950 hover:bg-zinc-800 w-full h-11" data-testid="ai-submit">
                <Sparkles className="w-4 h-4 mr-1.5" /> {submitting ? "Thinking..." : "Find my match"}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="space-y-4" data-testid="ai-results">
            <div className="text-xs text-zinc-500 flex items-center gap-2">
              {results.used_llm ? <Sparkles className="w-3 h-3 text-amber-500" /> : null}
              <span>{results.message}</span>
            </div>
            {results.items.length === 0 ? (
              <div className="text-center py-8 border border-dashed border-zinc-200 rounded-md" data-testid="ai-results-empty">
                <div className="text-sm text-zinc-500">No matches — try widening your filters.</div>
              </div>
            ) : (
              <div className="space-y-3">
                {results.items.map((it, idx) => (
                  <Link
                    key={it.listing_id}
                    to={`/marketplace/${it.listing_id}`}
                    className="block bg-white border border-zinc-200 rounded-md p-4 hover:border-zinc-400 hover:shadow-sm transition-all"
                    data-testid={`ai-result-${idx}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-zinc-950 text-white flex items-center justify-center font-bold text-sm shrink-0">{idx + 1}</div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-zinc-800 leading-relaxed">{it.rationale}</p>
                        <div className="text-xs text-zinc-500 mt-2 flex items-center gap-1">
                          View listing <ArrowRight className="w-3 h-3" />
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            <Button variant="outline" onClick={() => setResults(null)} className="w-full" data-testid="ai-try-again">Try different filters</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
