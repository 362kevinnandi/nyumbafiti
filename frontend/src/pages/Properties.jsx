import { useCallback, useEffect, useState } from "react";
import { api, formatApiError, formatKES } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Plus, Building, Home as HomeIcon, Trash2, MapPin, Pencil } from "lucide-react";
import CardImageCarousel from "@/components/CardImageCarousel";

const HERO_IMG = "https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=800";

export const PROPERTY_CATEGORIES = [
  { value: "apartment", label: "Apartment" },
  { value: "own_compound", label: "Own Compound" },
];
export const SUB_TYPES = [
  { value: "bedsitter", label: "Bedsitter" },
  { value: "single_room", label: "Single Room" },
  { value: "1br", label: "1 Bedroom" },
  { value: "2br", label: "2 Bedrooms" },
  { value: "3br", label: "3 Bedrooms" },
  { value: "4br", label: "4 Bedrooms" },
  { value: "5br_plus", label: "5+ Bedrooms" },
];
export const TENANCY_OPTIONS = [
  { value: "rental", label: "Rental" },
  { value: "lease", label: "Lease" },
];

const categoryLabel = (v) =>
  PROPERTY_CATEGORIES.find((c) => c.value === v)?.label || "Apartment";
const subTypeLabel = (v) =>
  SUB_TYPES.find((c) => c.value === v)?.label || "";

export default function PropertiesPage() {
  const [properties, setProperties] = useState([]);
  const [units, setUnits] = useState([]);
  const [tab, setTab] = useState("properties");
  const [open, setOpen] = useState(false);
  const [unitOpen, setUnitOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    address: "",
    description: "",
    category: "apartment",
    sub_type: "",
    tenancy_types: ["rental"],
  });
  const [editId, setEditId] = useState(null);

  const [images, setImages] = useState([]);
  const [unitForm, setUnitForm] = useState({ property_id: "", unit_number: "", rent_amount: 0, bedrooms: 1, description: "" });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [p, u] = await Promise.all([api.get("/properties"), api.get("/units")]);
    setProperties(p.data);
    setUnits(u.data);
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const resetForm = () => {
    setForm({ name: "", address: "", description: "", category: "apartment", sub_type: "", tenancy_types: ["rental"] });
    setImages([]);
    setEditId(null);
  };

  const openEdit = (p) => {
    setEditId(p.id);
    setForm({
      name: p.name || "",
      address: p.address || "",
      description: p.description || "",
      category: p.category || "apartment",
      sub_type: p.sub_type || "",
      tenancy_types: (p.tenancy_types && p.tenancy_types.length) ? p.tenancy_types : ["rental"],
    });
    setImages([]);
    setOpen(true);
  };

  const toggleTenancy = (v) => {
    setForm((f) => {
      const has = f.tenancy_types.includes(v);
      if (has && f.tenancy_types.length === 1) return f; // must keep at least one
      return {
        ...f,
        tenancy_types: has
          ? f.tenancy_types.filter((x) => x !== v)
          : [...f.tenancy_types, v],
      };
    });
  };

  const createOrUpdateProperty = async (e) => {
    e.preventDefault();
    try {
      if (editId) {
        await api.patch(`/properties/${editId}`, {
          name: form.name,
          address: form.address,
          description: form.description,
          category: form.category,
          sub_type: form.sub_type || null,
          tenancy_types: form.tenancy_types,
        });
        toast.success("Property updated");
      } else {
        const formData = new FormData();
        formData.append("name", form.name);
        formData.append("address", form.address);
        formData.append("description", form.description);
        formData.append("category", form.category);
        if (form.sub_type) formData.append("sub_type", form.sub_type);
        formData.append("tenancy_types", form.tenancy_types.join(","));
        images.forEach((image) => formData.append("images", image));
        await api.post("/properties", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success("Property created");
      }
      setOpen(false);
      resetForm();
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const createUnit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/units", { ...unitForm, rent_amount: Number(unitForm.rent_amount), bedrooms: Number(unitForm.bedrooms) });
      toast.success("Unit added");
      setUnitOpen(false);
      setUnitForm({ property_id: "", unit_number: "", rent_amount: 0, bedrooms: 1, description: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  const deleteProperty = async (id) => {
    if (!window.confirm("Delete property and all its units?")) return;
    await api.delete(`/properties/${id}`);
    toast.success("Property deleted");
    load();
  };

  const deleteUnit = async (id) => {
    if (!window.confirm("Delete unit?")) return;
    try {
      await api.delete(`/units/${id}`);
      toast.success("Unit deleted");
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  return (
    <div data-testid="properties-page">
      <PageHeader
        overline="Portfolio"
        title="Properties & Units"
        action={
          <div className="flex gap-2">
            <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetForm(); }}>
              <DialogTrigger asChild>
                <Button className="bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="add-property-button">
                  <Plus className="w-4 h-4 mr-1.5" /> Add Property
                </Button>
              </DialogTrigger>
              <DialogContent className="rounded-md">
                <DialogHeader>
                  <DialogTitle className="font-display font-black text-2xl">
                    {editId ? "Edit Property" : "New Property"}
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={createOrUpdateProperty} className="space-y-4 mt-2" data-testid="property-form">
                  <div><Label className="overline">Name</Label><Input required value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="mt-1" data-testid="property-name-input" /></div>
                  <div><Label className="overline">Address</Label><Input required value={form.address} onChange={(e) => setForm({...form, address: e.target.value})} placeholder="e.g. Westlands, Nairobi" className="mt-1" data-testid="property-address-input" /></div>
                  <div>
                    <Label className="overline">Category</Label>
                    <select
                      required
                      value={form.category}
                      onChange={(e) => setForm({ ...form, category: e.target.value })}
                      className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                      data-testid="property-category-select"
                    >
                      {PROPERTY_CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label className="overline">Unit / Sub-type (optional)</Label>
                    <select
                      value={form.sub_type}
                      onChange={(e) => setForm({ ...form, sub_type: e.target.value })}
                      className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm"
                      data-testid="property-subtype-select"
                    >
                      <option value="">— None —</option>
                      {SUB_TYPES.map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label className="overline">Tenancy types (pick one or both)</Label>
                    <div className="flex gap-2 mt-2" data-testid="property-tenancy-toggle">
                      {TENANCY_OPTIONS.map((t) => {
                        const active = form.tenancy_types.includes(t.value);
                        return (
                          <button
                            type="button"
                            key={t.value}
                            onClick={() => toggleTenancy(t.value)}
                            className={`px-4 h-10 rounded-full border text-sm font-semibold transition-all ${
                              active
                                ? "bg-zinc-950 text-white border-zinc-950"
                                : "bg-white border-zinc-300 text-zinc-700 hover:border-zinc-500"
                            }`}
                            data-testid={`property-tenancy-${t.value}`}
                          >
                            {t.label}
                          </button>
                        );
                      })}
                    </div>
                    <div className="text-[10px] text-zinc-500 mt-1.5">
                      Tenants assigned will only see the agreement type(s) you enable here.
                    </div>
                  </div>
                  <div><Label className="overline">Description</Label><Input value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} className="mt-1" /></div>
                  {!editId && (
                    <div>
                      <Label className="overline">Property Images (Max 5)</Label>
                      <Input
                        type="file"
                        accept="image/*"
                        multiple
                        className="mt-1"
                        data-testid="property-images-input"
                        onChange={(e) => {
                          const files = Array.from(e.target.files || []);
                          if (files.length > 5) {
                            toast.error("Maximum 5 images allowed");
                            return;
                          }
                          setImages(files);
                        }}
                      />
                      <div className="flex gap-2 flex-wrap mt-3">
                        {images.map((file, index) => (
                          <img
                            key={index}
                            src={URL.createObjectURL(file)}
                            alt=""
                            className="w-20 h-20 object-cover rounded-md border"
                          />
                        ))}
                      </div>
                    </div>
                  )}
                  <DialogFooter>
                    <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="property-submit-button">
                      {editId ? "Save changes" : "Create"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>

            <Dialog open={unitOpen} onOpenChange={setUnitOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="rounded-md" data-testid="add-unit-button">
                  <Plus className="w-4 h-4 mr-1.5" /> Add Unit
                </Button>
              </DialogTrigger>
              <DialogContent className="rounded-md">
                <DialogHeader>
                  <DialogTitle className="font-display font-black text-2xl">New Unit</DialogTitle>
                </DialogHeader>
                <form onSubmit={createUnit} className="space-y-4 mt-2" data-testid="unit-form">
                  <div>
                    <Label className="overline">Property</Label>
                    <select required value={unitForm.property_id} onChange={(e) => setUnitForm({...unitForm, property_id: e.target.value})} className="mt-1 w-full h-10 border border-zinc-300 rounded-md px-3 bg-white text-sm" data-testid="unit-property-select">
                      <option value="">Select property...</option>
                      {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <div><Label className="overline">Unit number</Label><Input required value={unitForm.unit_number} onChange={(e) => setUnitForm({...unitForm, unit_number: e.target.value})} placeholder="e.g. A-101" className="mt-1" data-testid="unit-number-input" /></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label className="overline">Rent (KES)</Label><Input required type="number" value={unitForm.rent_amount} onChange={(e) => setUnitForm({...unitForm, rent_amount: e.target.value})} className="mt-1" data-testid="unit-rent-input" /></div>
                    <div><Label className="overline">Bedrooms</Label><Input required type="number" value={unitForm.bedrooms} onChange={(e) => setUnitForm({...unitForm, bedrooms: e.target.value})} className="mt-1" /></div>
                  </div>
                  <DialogFooter>
                    <Button type="submit" className="bg-zinc-950 hover:bg-zinc-800" data-testid="unit-submit-button">Create</Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-zinc-100 rounded-md mb-6">
          <TabsTrigger value="properties" className="rounded-sm" data-testid="tab-properties">Properties ({properties.length})</TabsTrigger>
          <TabsTrigger value="units" className="rounded-sm" data-testid="tab-units">Units ({units.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="properties">
          {loading ? <div className="text-zinc-500">Loading...</div> : properties.length === 0 ? (
            <EmptyState title="No properties yet" body="Create your first property to start managing rentals." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="properties-grid">
              {properties.map((p) => (
                
                <div key={p.id} className="group bg-white border border-zinc-200 rounded-2xl overflow-hidden card-hover shadow-sm hover:shadow-xl transition-all" data-testid={`property-card-${p.id}`}>
                  <div className="relative h-44 bg-zinc-100">
                    <CardImageCarousel
                      imagesList={p.images || []}
                      fallback={HERO_IMG}
                      className="absolute inset-0 w-full h-full"
                      rounded=""
                    />
                    <div className="absolute top-3 right-3 bg-white/95 backdrop-blur px-2 py-0.5 rounded-sm text-xs font-mono-num font-semibold z-10">{p.units_count} units</div>
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
                    {p.approval_status === "pending" && (
                      <div className="absolute top-3 left-3 bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider z-10">Awaiting admin approval</div>
                    )}
                    {p.approval_status === "rejected" && (
                      <div className="absolute top-3 left-3 bg-red-100 text-red-800 border border-red-200 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider z-10">Rejected</div>
                    )}
                    {p.featured && (
                      <div className="absolute top-3 left-3 bg-amber-400 text-zinc-950 border border-amber-500 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider shadow z-10">Featured</div>
                    )}
                  </div>
                  <div className="p-5">
                    <div className="font-display font-bold text-lg mb-1 tracking-tight">{p.name}</div>
                    <div className="flex items-start gap-1.5 text-xs text-zinc-500 mb-2">
                      <MapPin className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{p.address}</span>
                    </div>
                    <div className="flex gap-1.5 mb-2 flex-wrap">
                      {(p.tenancy_types || ["rental"]).map((t) => (
                        <span key={t} className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700">
                          {t}
                        </span>
                      ))}
                    </div>
                    {p.description && <div className="text-sm text-zinc-600 mb-3 line-clamp-2">{p.description}</div>}
                    <div className="flex justify-between items-center pt-3 border-t border-zinc-100">
                      <div className="overline text-zinc-500">Created {new Date(p.created_at).toLocaleDateString()}</div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => openEdit(p)} className="text-zinc-400 hover:text-zinc-900 p-1" data-testid={`edit-property-${p.id}`} title="Edit">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => deleteProperty(p.id)} className="text-zinc-400 hover:text-red-600 p-1" data-testid={`delete-property-${p.id}`} title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="units">
          {loading ? <div className="text-zinc-500">Loading...</div> : units.length === 0 ? (
            <EmptyState title="No units" body="Add your first unit to a property." />
          ) : (
            <div className="bg-white border border-zinc-200 rounded-md overflow-hidden" data-testid="units-table">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Unit</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Property</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Tenant</th>
                    <th className="text-right px-4 py-3 overline text-zinc-500">Rent</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {units.map((u) => {
                    const prop = properties.find((p) => p.id === u.property_id);
                    return (
                      <tr key={u.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`unit-row-${u.id}`}>
                        <td className="px-4 py-3 font-semibold">{u.unit_number}</td>
                        <td className="px-4 py-3 text-zinc-600">{prop?.name || "—"}</td>
                        <td className="px-4 py-3 text-zinc-600">{u.tenant_name || <span className="text-zinc-400">vacant</span>}</td>
                        <td className="px-4 py-3 text-right font-mono-num">{formatKES(u.rent_amount)}</td>
                        <td className="px-4 py-3">
                          <span className={`badge-status ${u.occupied ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-600"}`}>
                            {u.occupied ? "Occupied" : "Vacant"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!u.occupied && (
                            <button onClick={() => deleteUnit(u.id)} className="text-zinc-400 hover:text-red-600">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EmptyState({ title, body }) {
  return (
    <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
      <Building className="w-10 h-10 mx-auto text-zinc-300 mb-3" strokeWidth={1.5} />
      <div className="font-display font-bold text-lg mb-1">{title}</div>
      <div className="text-sm text-zinc-500">{body}</div>
    </div>
  );
}
