import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Tag, Sparkles, Trash2, Lock, Globe2, Building2 } from "lucide-react";
import CardImageCarousel from "@/components/CardImageCarousel";

const CATEGORIES = [
  { value: "all", label: "All" },
  { value: "electronics", label: "Electronics" },
  { value: "furniture", label: "Furniture" },
  { value: "appliances", label: "Appliances" },
  { value: "clothing", label: "Clothing" },
  { value: "books", label: "Books" },
  { value: "kitchen", label: "Kitchen" },
  { value: "sports", label: "Sports" },
  { value: "other", label: "Other" },
];

const FALLBACK = "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?crop=entropy&cs=srgb&fm=jpg&q=85&w=600";

export default function YardSalePage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", price: "", category: "other", phone_number: user?.phone || "" });
  const [images, setImages] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [pendingPayment, setPendingPayment] = useState(null); // { listing_id, payment_id }

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (category !== "all") params.category = category;
    const r = await api.get("/yard-sale/listings", { params });
    setItems(r.data || []);
    setLoading(false);
  }, [category]);

  useEffect(() => { load(); }, [load]);

  // Poll the seller's pending listing once submitted, so we know when STK confirms
  useEffect(() => {
    if (!pendingPayment) return;
    const start = Date.now();
    const interval = setInterval(async () => {
      // After 25s, force a real Safaricom status query for truth (no more false-positive demo callbacks)
      if (Date.now() - start > 25_000 && Date.now() - start < 28_000 && pendingPayment?.payment_id) {
        try { await api.post(`/payments/${pendingPayment.payment_id}/check`); } catch { /* ignore */ }
      }
      try {
        const r = await api.get(`/yard-sale/listings/${pendingPayment.listing_id}`);
        if (r.data?.status === "active" && r.data?.contact_unlocked) {
          clearInterval(interval);
          toast.success("Payment confirmed — your listing is now live with contact unlocked!");
          setPendingPayment(null);
          setOpen(false);
          setForm({ title: "", description: "", price: "", category: "other", phone_number: user?.phone || "" });
          setImages([]);
          load();
        }
      } catch { /* listing not visible yet */ }
      // If payment row tells us it failed, surface that
      if (pendingPayment?.payment_id) {
        try {
          const pr = await api.get(`/payments/${pendingPayment.payment_id}`);
          if (pr.data?.status === "failed") {
            clearInterval(interval);
            toast.error("Payment did not go through — " + (pr.data.result_desc || "no response"));
            setPendingPayment(null);
          }
        } catch { /* */ }
      }
    }, 2500);
    const stop = setTimeout(() => clearInterval(interval), 120000);
    return () => { clearInterval(interval); clearTimeout(stop); };
  }, [pendingPayment, load, user?.phone]);

  const create = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("title", form.title);
      fd.append("description", form.description);
      fd.append("price", form.price);
      fd.append("category", form.category);
      fd.append("scope", "property");
      fd.append("phone_number", form.phone_number);
      images.forEach((f) => fd.append("images", f));
      const r = await api.post("/yard-sale/listings", fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (r.data.payment) {
        toast.success("STK push sent — enter your M-Pesa PIN to publish the listing.");
        setPendingPayment({
          listing_id: r.data.listing?.id,
          payment_id: r.data.payment?.payment_id,
        });
      } else {
        // Sandbox glitch — listing saved as draft. Show retry option.
        toast.warning(r.data.message || "M-Pesa is unreachable. Open your listing to retry payment.");
        setPendingPayment({
          listing_id: r.data.listing?.id,
          payment_id: null,
          stk_error: r.data.stk_error || "Unknown error",
        });
      }
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete listing?")) return;
    await api.delete(`/yard-sale/listings/${id}`);
    toast.success("Deleted");
    load();
  };

  const markSold = async (id) => {
    await api.patch(`/yard-sale/listings/${id}`, { status: "sold" });
    toast.success("Marked sold");
    load();
  };

  const canPost = ["tenant", "landlord", "caretaker", "security"].includes(user.role);

  return (
    <div data-testid="yard-sale-page">
      <PageHeader
        overline="Community"
        title="Yard Sale Marketplace"
        action={canPost && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="new-yard-sale-button">
                <Plus className="w-4 h-4 mr-1.5" /> List Item
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-md max-w-lg">
              <DialogHeader>
                <DialogTitle className="font-display font-black text-2xl">Sell an item</DialogTitle>
                <DialogDescription>
                  Pay KES 35 once to publish + unlock your contact so buyers can reach you.
                </DialogDescription>
              </DialogHeader>
              {pendingPayment ? (
                <div className="space-y-4 py-2" data-testid="yard-sale-pending">
                  {pendingPayment.stk_error ? (
                    <div className="bg-red-50 border border-red-200 rounded-md p-4">
                      <div className="font-display font-bold text-base mb-1 text-red-900">M-Pesa unreachable</div>
                      <div className="text-xs text-red-800 mb-3">{pendingPayment.stk_error}</div>
                      <Button
                        type="button"
                        onClick={async () => {
                          try {
                            const r = await api.post(`/yard-sale/listings/${pendingPayment.listing_id}/retry-unlock`, { phone_number: form.phone_number || user.phone });
                            setPendingPayment({ listing_id: pendingPayment.listing_id, payment_id: r.data.payment_id });
                            toast.success("STK push re-sent — check your phone");
                          } catch (err) {
                            toast.error(formatApiError(err, "Retry failed"));
                          }
                        }}
                        className="w-full bg-mpesa hover:bg-mpesa text-white"
                        data-testid="yard-sale-retry-stk"
                      >
                        Retry STK push
                      </Button>
                    </div>
                  ) : (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-md p-4 text-center">
                      <div className="font-display font-bold text-lg mb-1">Awaiting M-Pesa confirmation</div>
                      <div className="text-sm text-zinc-700">Enter your PIN on the prompt that was just sent to your phone. We'll publish the listing as soon as Safaricom confirms.</div>
                    </div>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={async () => {
                      try { if (pendingPayment.payment_id) await api.post(`/payments/${pendingPayment.payment_id}/cancel`); } catch { /* */ }
                      setPendingPayment(null); setOpen(false);
                    }}
                    className="w-full"
                    data-testid="yard-sale-pending-close"
                  >
                    Cancel & close
                  </Button>
                </div>
              ) : (
              <form onSubmit={create} className="space-y-4" data-testid="yard-sale-form">
                <div>
                  <Label className="overline">Title</Label>
                  <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1" data-testid="yard-sale-title" />
                </div>
                <div>
                  <Label className="overline">Description</Label>
                  <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1" data-testid="yard-sale-description" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="overline">Price (KES)</Label>
                    <Input required type="number" min="0" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="mt-1" data-testid="yard-sale-price" />
                  </div>
                  <div>
                    <Label className="overline">Category</Label>
                    <select required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="yard-sale-category">
                      {CATEGORIES.filter((c) => c.value !== "all").map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <Label className="overline">M-Pesa Phone</Label>
                  <Input required value={form.phone_number} onChange={(e) => setForm({ ...form, phone_number: e.target.value })} className="mt-1 font-mono-num" placeholder="0712345678" data-testid="yard-sale-phone" />
                </div>
                <div>
                  <Label className="overline">Photos (up to 5)</Label>
                  <Input type="file" accept="image/*" multiple onChange={(e) => setImages(Array.from(e.target.files || []).slice(0, 5))} className="mt-1" data-testid="yard-sale-images" />
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-900" data-testid="yard-sale-fee-info">
                  <div className="font-semibold mb-1">KES 35 unlocks your listing</div>
                  <p className="leading-relaxed">
                    Once paid, buyers will see your <span className="font-semibold">name, phone, email, property + unit number</span>.
                    Without paying, the listing stays hidden. Optional: pay KES 50 later to broadcast to all NyumbaOS tenants (adds your property address), or KES 100 to feature for 7 days.
                  </p>
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={submitting} className="bg-mpesa hover:bg-mpesa text-white w-full h-11" data-testid="yard-sale-submit">
                    {submitting ? "Sending STK push..." : "Pay KES 35 & Publish"}
                  </Button>
                </DialogFooter>
              </form>
              )}
            </DialogContent>
          </Dialog>
        )}
      />

      <div className="flex flex-wrap gap-2 mb-6" data-testid="yard-sale-chips">
        {CATEGORIES.map((c) => {
          const active = category === c.value;
          return (
            <button
              key={c.value}
              onClick={() => setCategory(c.value)}
              className={`px-4 h-9 rounded-full border text-xs font-semibold transition-all ${
                active ? "bg-zinc-950 text-white border-zinc-950" : "bg-white border-zinc-300 text-zinc-700 hover:border-zinc-500"
              }`}
              data-testid={`yard-sale-chip-${c.value}`}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {loading ? <div className="text-zinc-500">Loading...</div>
        : items.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-2xl bg-white" data-testid="yard-sale-empty">
            <Tag className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No listings yet</div>
            <div className="text-sm text-zinc-500">Be the first to list an item.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="yard-sale-grid">
            {items.map((l) => {
              const isMine = l.seller_id === user.id;
              return (
                <Link
                  key={l.id}
                  to={`/yard-sale/${l.id}`}
                  className="group bg-white border border-zinc-200 rounded-2xl overflow-hidden block transition-all shadow-sm hover:-translate-y-1 hover:shadow-2xl"
                  data-testid={`yard-sale-card-${l.id}`}
                >
                  <div className="relative h-44">
                    <CardImageCarousel
                      imagesList={l.images || []}
                      fallback={FALLBACK}
                      className="absolute inset-0 w-full h-full"
                      rounded=""
                    />
                    <div className="absolute top-3 left-3 z-10 bg-white/95 backdrop-blur px-2.5 py-1 rounded-md font-mono-num text-sm font-bold shadow-sm">{formatKES(l.price)}</div>
                    {l.featured && (
                      <div className="absolute top-3 right-3 z-10 bg-amber-400 text-zinc-950 px-2 py-0.5 rounded-md overline text-[10px] shadow flex items-center gap-1" data-testid={`yard-sale-featured-${l.id}`}>
                        <Sparkles className="w-3 h-3" /> Featured
                      </div>
                    )}
                    <div className="absolute bottom-3 left-3 z-10 flex gap-1.5">
                      <span className={`px-2 py-0.5 rounded-md overline text-[10px] backdrop-blur ${l.scope === "all" ? "bg-emerald-500/90 text-white" : "bg-zinc-950/85 text-white"}`} data-testid={`yard-sale-scope-${l.id}`}>
                        {l.scope === "all" ? <span className="flex items-center gap-1"><Globe2 className="w-2.5 h-2.5" /> Platform</span> : <span className="flex items-center gap-1"><Building2 className="w-2.5 h-2.5" /> Property</span>}
                      </span>
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="font-display font-bold text-base mb-1">{l.title}</div>
                    <p className="text-sm text-zinc-600 line-clamp-2 mb-2">{l.description}</p>
                    <div className="overline text-zinc-500 text-[10px]">
                      <Tag className="w-3 h-3 inline mr-1" />{CATEGORIES.find((c) => c.value === l.category)?.label || l.category}
                    </div>
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-100">
                      <div>
                        <div className="text-xs font-semibold text-zinc-900">{l.seller_name}</div>
                        {l.seller_phone ? (
                          <div className="text-xs text-zinc-600 font-mono-num">{l.seller_phone}</div>
                        ) : (
                          <div className="text-[10px] text-zinc-400 flex items-center gap-1 mt-0.5"><Lock className="w-2.5 h-2.5" /> Contact locked</div>
                        )}
                      </div>
                      {isMine && (
                        <div className="flex items-center gap-1" onClick={(e) => e.preventDefault()}>
                          {l.status === "active" && (
                            <button onClick={() => markSold(l.id)} className="text-xs px-2 h-7 border border-zinc-200 rounded-md hover:bg-zinc-100" data-testid={`yard-sale-mark-sold-${l.id}`}>
                              Mark sold
                            </button>
                          )}
                          <button onClick={() => remove(l.id)} className="text-zinc-400 hover:text-red-600 p-1.5 rounded-md hover:bg-red-50" data-testid={`yard-sale-delete-${l.id}`}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
    </div>
  );
}
