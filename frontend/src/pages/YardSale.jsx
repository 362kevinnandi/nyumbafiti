import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES, mediaUrl } from "@/lib/api";
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
import { Plus, Tag, Sparkles, Trash2, Phone, Smartphone } from "lucide-react";

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
  const [form, setForm] = useState({ title: "", description: "", price: "", category: "other" });
  const [images, setImages] = useState([]);
  const [featureOpen, setFeatureOpen] = useState(null);
  const [phone, setPhone] = useState(user?.phone || "");
  const [featuring, setFeaturing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (category !== "all") params.category = category;
    const r = await api.get("/yard-sale/listings", { params });
    setItems(r.data || []);
    setLoading(false);
  }, [category]);

  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const fd = new FormData();
      fd.append("title", form.title);
      fd.append("description", form.description);
      fd.append("price", form.price);
      fd.append("category", form.category);
      images.forEach((f) => fd.append("images", f));
      await api.post("/yard-sale/listings", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Listing posted");
      setOpen(false);
      setForm({ title: "", description: "", price: "", category: "other" });
      setImages([]);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
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

  const requestFeature = async (e) => {
    e.preventDefault();
    setFeaturing(true);
    try {
      const fd = new FormData();
      fd.append("phone_number", phone);
      const r = await api.post(`/yard-sale/listings/${featureOpen}/feature`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(r.data.message || "STK push sent. Check your phone.");
      setFeatureOpen(null);
      // poll briefly
      const interval = setInterval(async () => {
        const lr = await api.get(`/yard-sale/listings/${featureOpen}`);
        if (lr.data?.featured) {
          clearInterval(interval);
          toast.success("Listing featured for 7 days!");
          load();
        }
      }, 2000);
      setTimeout(() => clearInterval(interval), 60000);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to feature"));
    } finally {
      setFeaturing(false);
    }
  };

  const canPost = ["tenant", "landlord", "caretaker"].includes(user.role);

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
                <DialogDescription>Quick post for fellow tenants. KES 100 to feature for 7 days.</DialogDescription>
              </DialogHeader>
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
                  <Label className="overline">Photos (up to 5)</Label>
                  <Input type="file" accept="image/*" multiple onChange={(e) => setImages(Array.from(e.target.files || []).slice(0, 5))} className="mt-1" data-testid="yard-sale-images" />
                </div>
                <DialogFooter>
                  <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="yard-sale-submit">Post Listing</Button>
                </DialogFooter>
              </form>
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
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="yard-sale-empty">
            <Tag className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg">No listings yet</div>
            <div className="text-sm text-zinc-500">Be the first to list an item.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="yard-sale-grid">
            {items.map((l) => {
              const imgSrc = l.images?.[0] ? mediaUrl(l.images[0]) : FALLBACK;
              const isMine = l.seller_id === user.id;
              return (
                <div key={l.id} className="bg-white border border-zinc-200 rounded-md overflow-hidden card-hover" data-testid={`yard-sale-card-${l.id}`}>
                  <div className="relative h-40 bg-zinc-100" style={{ backgroundImage: `url(${imgSrc})`, backgroundSize: "cover", backgroundPosition: "center" }}>
                    <div className="absolute top-3 right-3 bg-white/95 backdrop-blur px-2 py-0.5 rounded-sm font-mono-num text-xs font-semibold">{formatKES(l.price)}</div>
                    {l.featured && (
                      <div className="absolute top-3 left-3 bg-amber-400 text-zinc-950 px-2 py-0.5 rounded-sm overline text-[10px] shadow flex items-center gap-1" data-testid={`yard-sale-featured-${l.id}`}>
                        <Sparkles className="w-3 h-3" /> Featured
                      </div>
                    )}
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
                        {l.seller_phone && <a href={`tel:${l.seller_phone}`} className="text-xs text-zinc-600 font-mono-num flex items-center gap-1"><Phone className="w-3 h-3" />{l.seller_phone}</a>}
                      </div>
                      {isMine && (
                        <div className="flex items-center gap-1">
                          {!l.featured && (
                            <button onClick={() => setFeatureOpen(l.id)} className="text-amber-600 hover:text-amber-700 p-1.5 rounded-md hover:bg-amber-50" title="Feature" data-testid={`yard-sale-feature-${l.id}`}>
                              <Sparkles className="w-4 h-4" />
                            </button>
                          )}
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
                </div>
              );
            })}
          </div>
        )}

      <Dialog open={!!featureOpen} onOpenChange={(o) => !o && setFeatureOpen(null)}>
        <DialogContent className="rounded-md max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-display font-black text-2xl">Feature this listing</DialogTitle>
            <DialogDescription>Pay KES 100 via M-Pesa to boost it to the top for 7 days.</DialogDescription>
          </DialogHeader>
          <form onSubmit={requestFeature} className="space-y-4" data-testid="yard-sale-feature-form">
            <div>
              <Label className="overline">M-Pesa phone</Label>
              <Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712345678" className="mt-1 font-mono-num" data-testid="yard-sale-feature-phone" />
            </div>
            <div className="bg-zinc-50 border border-zinc-200 rounded-md p-3 text-sm flex justify-between">
              <span className="text-zinc-600">Boost fee</span>
              <span className="font-mono-num font-semibold">KES 100</span>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={featuring} className="bg-mpesa hover:bg-mpesa text-white w-full h-11" data-testid="yard-sale-feature-submit">
                <Smartphone className="w-4 h-4 mr-1.5" /> {featuring ? "Sending STK..." : "Pay KES 100"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
