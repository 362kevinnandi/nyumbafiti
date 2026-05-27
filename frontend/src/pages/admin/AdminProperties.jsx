import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Pencil, Trash2, Star, StarOff, MapPin, Building2, Search } from "lucide-react";
import CardImageCarousel from "@/components/CardImageCarousel";

const CATEGORIES = [
  { value: "apartment", label: "Apartment" },
  { value: "own_compound", label: "Own Compound" },
];
const SUB_TYPES = [
  { value: "bedsitter", label: "Bedsitter" },
  { value: "single_room", label: "Single Room" },
  { value: "1br", label: "1 Bedroom" },
  { value: "2br", label: "2 Bedrooms" },
  { value: "3br", label: "3 Bedrooms" },
  { value: "4br", label: "4 Bedrooms" },
  { value: "5br_plus", label: "5+ Bedrooms" },
];

const HERO_IMG = "https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=600";
const categoryLabel = (v) => CATEGORIES.find((c) => c.value === v)?.label || "Apartment";
const subTypeLabel = (v) => SUB_TYPES.find((c) => c.value === v)?.label || "";

export default function AdminPropertiesPage() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", address: "", description: "", category: "apartment", sub_type: "", tenancy_types: ["rental"] });

  const load = useCallback(async () => {
    setLoading(true);
    const r = await api.get("/admin/properties");
    setProperties(r.data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return properties;
    return properties.filter(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.address?.toLowerCase().includes(q) ||
        p.landlord_name?.toLowerCase().includes(q)
    );
  }, [search, properties]);

  const startEdit = (p) => {
    setEditing(p);
    setForm({
      name: p.name || "",
      address: p.address || "",
      description: p.description || "",
      category: p.category || "apartment",
      sub_type: p.sub_type || "",
      tenancy_types: (p.tenancy_types && p.tenancy_types.length) ? p.tenancy_types : ["rental"],
    });
    setOpen(true);
  };

  const saveEdit = async (e) => {
    e.preventDefault();
    try {
      await api.patch(`/properties/${editing.id}`, {
        ...form,
        sub_type: form.sub_type || null,
      });
      toast.success("Property updated");
      setOpen(false);
      setEditing(null);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to update"));
    }
  };

  const toggleTenancy = (v) => {
    setForm((f) => {
      const has = f.tenancy_types.includes(v);
      if (has && f.tenancy_types.length === 1) return f;
      return { ...f, tenancy_types: has ? f.tenancy_types.filter((x) => x !== v) : [...f.tenancy_types, v] };
    });
  };

  const removeProp = async (p) => {
    if (!window.confirm(`Delete "${p.name}"? This will also delete all units under it.`)) return;
    try {
      await api.delete(`/properties/${p.id}`);
      toast.success("Property deleted");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed to delete"));
    }
  };

  const toggleFeatured = async (p) => {
    try {
      await api.patch(`/properties/${p.id}`, { featured: !p.featured });
      toast.success(!p.featured ? "Marked as featured" : "Removed from featured");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  return (
    <div data-testid="admin-properties-page">
      <PageHeader
        overline="Oversight"
        title="All Properties"
        action={
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <Input
              placeholder="Search by name, address, landlord..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 pl-9 w-80"
              data-testid="admin-properties-search"
            />
          </div>
        }
      />

      {loading ? (
        <div className="text-zinc-500">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="admin-properties-empty">
          <Building2 className="w-11 h-11 mx-auto text-zinc-300 mb-3" />
          <div className="font-display font-bold text-lg mb-1">No properties found</div>
          <div className="text-sm text-zinc-500">Try a different search.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="admin-properties-grid">
          {filtered.map((p) => (
            <div key={p.id} className="bg-white border border-zinc-200 rounded-md overflow-hidden" data-testid={`admin-property-card-${p.id}`}>
              <div className="relative h-40">
                <CardImageCarousel
                  imagesList={p.images || []}
                  fallback={HERO_IMG}
                  className="absolute inset-0 w-full h-full"
                  rounded=""
                />
                <div className="absolute top-3 right-3 z-10 bg-white/95 backdrop-blur px-2 py-0.5 rounded-sm text-xs font-mono-num font-semibold">
                  {p.units_count} units
                </div>
                <div className="absolute bottom-3 left-3 z-10 flex gap-1.5">
                  <span className="bg-zinc-950/90 text-white px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider backdrop-blur">
                    {categoryLabel(p.category)}
                  </span>
                  {p.sub_type && (
                    <span className="bg-white/95 text-zinc-900 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider backdrop-blur">
                      {subTypeLabel(p.sub_type)}
                    </span>
                  )}
                </div>
                {p.featured && (
                  <div className="absolute top-3 left-3 z-10 bg-amber-400 text-zinc-950 border border-amber-500 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider shadow flex items-center gap-1" data-testid={`featured-flag-${p.id}`}>
                    <Star className="w-3 h-3 fill-current" /> Featured
                  </div>
                )}
                {p.approval_status === "pending" && !p.featured && (
                  <div className="absolute top-3 left-3 z-10 bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider">Pending</div>
                )}
                {p.approval_status === "rejected" && !p.featured && (
                  <div className="absolute top-3 left-3 z-10 bg-red-100 text-red-800 border border-red-200 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider">Rejected</div>
                )}
              </div>
              <div className="p-4">
                <div className="font-display font-bold text-lg mb-1 tracking-tight">{p.name}</div>
                <div className="flex items-start gap-1.5 text-xs text-zinc-500 mb-2">
                  <MapPin className="w-3 h-3 mt-0.5 shrink-0" />
                  <span>{p.address}</span>
                </div>
                <div className="overline text-zinc-500 text-[10px]">
                  Landlord: <span className="text-zinc-900 font-semibold">{p.landlord_name || "—"}</span>
                </div>
                <div className="flex items-center justify-between pt-3 mt-3 border-t border-zinc-100">
                  <button
                    onClick={() => toggleFeatured(p)}
                    className={`text-xs font-semibold flex items-center gap-1 px-2 h-8 rounded-md border ${
                      p.featured
                        ? "bg-amber-50 border-amber-300 text-amber-800"
                        : "bg-white border-zinc-200 text-zinc-600 hover:border-zinc-400"
                    }`}
                    data-testid={`toggle-featured-${p.id}`}
                  >
                    {p.featured ? <><StarOff className="w-3.5 h-3.5" /> Unfeature</> : <><Star className="w-3.5 h-3.5" /> Feature</>}
                  </button>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(p)}
                      className="text-zinc-400 hover:text-zinc-900 p-1.5 rounded-md hover:bg-zinc-100"
                      data-testid={`edit-property-${p.id}`}
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => removeProp(p)}
                      className="text-zinc-400 hover:text-red-600 p-1.5 rounded-md hover:bg-red-50"
                      data-testid={`delete-property-${p.id}`}
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
        <DialogContent className="rounded-md">
          <DialogHeader>
            <DialogTitle className="font-display font-black text-2xl">Edit Property</DialogTitle>
          </DialogHeader>
          <form onSubmit={saveEdit} className="space-y-4 mt-2" data-testid="admin-edit-property-form">
            <div>
              <Label className="overline">Name</Label>
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" data-testid="admin-edit-property-name" />
            </div>
            <div>
              <Label className="overline">Address</Label>
              <Input required value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="mt-1" data-testid="admin-edit-property-address" />
            </div>
            <div>
              <Label className="overline">Category</Label>
              <select
                required
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                data-testid="admin-edit-property-category"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="overline">Sub-type</Label>
              <select
                value={form.sub_type}
                onChange={(e) => setForm({ ...form, sub_type: e.target.value })}
                className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                data-testid="admin-edit-property-subtype"
              >
                <option value="">— None —</option>
                {SUB_TYPES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="overline">Tenancy types</Label>
              <div className="flex gap-2 mt-2" data-testid="admin-edit-tenancy">
                {[{value:"rental",label:"Rental"},{value:"lease",label:"Lease"}].map((t) => {
                  const active = form.tenancy_types.includes(t.value);
                  return (
                    <button type="button" key={t.value} onClick={() => toggleTenancy(t.value)}
                      className={`px-4 h-10 rounded-full border text-sm font-semibold transition-all ${active ? "bg-zinc-950 text-white border-zinc-950" : "bg-white border-zinc-300 text-zinc-700"}`}>
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <Label className="overline">Description</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1" />
            </div>
            <DialogFooter>
              <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="admin-edit-property-submit">Save changes</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
