import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api, formatApiError, formatKES, mediaUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  ArrowLeft, Phone, Mail, Sparkles, Lock, Globe2, Smartphone, Tag, MapPin,
} from "lucide-react";
import { Swiper, SwiperSlide } from "swiper/react";
import { Navigation, Pagination, Thumbs } from "swiper/modules";
import "swiper/css";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "swiper/css/thumbs";
import "./swiper-overrides.css";

const FALLBACK = "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?crop=entropy&cs=srgb&fm=jpg&q=85&w=900";

const CATEGORIES_LABELS = {
  electronics: "Electronics", furniture: "Furniture", appliances: "Appliances",
  clothing: "Clothing", books: "Books", kitchen: "Kitchen", sports: "Sports", other: "Other",
};

export default function YardSaleDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [thumbsSwiper, setThumbsSwiper] = useState(null);
  const [dialog, setDialog] = useState(null); // 'contact' | 'broadcast' | 'feature'
  const [phone, setPhone] = useState(user?.phone || "");
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/yard-sale/listings/${id}`);
      setItem(r.data);
    } catch (err) {
      toast.error(formatApiError(err, "Could not load listing"));
      navigate("/yard-sale");
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => { load(); }, [load]);

  const submitPay = async (e) => {
    e.preventDefault();
    setPending(true);
    const endpoints = {
      contact: { path: `/yard-sale/listings/${id}/unlock-contact`, amount: 35, label: "Unlock contact" },
      broadcast: { path: `/yard-sale/listings/${id}/broadcast`, amount: 50, label: "Broadcast platform-wide" },
      feature: { path: `/yard-sale/listings/${id}/feature`, amount: 100, label: "Feature for 7 days" },
    };
    const ep = endpoints[dialog];
    try {
      const fd = new FormData();
      fd.append("phone_number", phone);
      const r = await api.post(ep.path, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(r.data.message || "STK push sent. Check your phone.");
      setDialog(null);
      // Poll briefly for update (demo mode confirms in ~4s)
      const t0 = Date.now();
      const poll = setInterval(async () => {
        if (Date.now() - t0 > 30000) { clearInterval(poll); return; }
        await load();
      }, 2500);
      setTimeout(() => clearInterval(poll), 30000);
    } catch (err) {
      toast.error(formatApiError(err, "Payment failed"));
    } finally {
      setPending(false);
    }
  };

  if (loading || !item) return <div className="p-8 text-zinc-500">Loading...</div>;

  const isOwner = item.seller_id === user.id;
  const contactHidden = !item.contact_unlocked && !isOwner && user.role !== "admin";
  const images = (item.images || []);

  return (
    <div className="min-h-screen bg-warm" data-testid="yard-sale-detail-page">
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <button onClick={() => navigate("/yard-sale")} className="text-sm font-semibold text-zinc-700 flex items-center gap-1.5 hover:text-zinc-950" data-testid="yard-sale-detail-back">
            <ArrowLeft className="w-4 h-4" /> Back to Yard Sale
          </button>
          <div className="flex gap-1.5">
            {item.featured && <span className="badge-status bg-amber-400 text-zinc-950 flex items-center gap-1"><Sparkles className="w-3 h-3" /> FEATURED</span>}
            <span className={`badge-status ${item.scope === "all" ? "bg-emerald-50 text-emerald-800" : "bg-zinc-100 text-zinc-700"}`}>
              {item.scope === "all" ? "PLATFORM-WIDE" : "PROPERTY ONLY"}
            </span>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Image gallery */}
        <div className="lg:col-span-3 space-y-3">
          <div className="bg-white rounded-2xl overflow-hidden border border-zinc-200 shadow-sm" data-testid="yard-sale-detail-gallery">
            <Swiper
              modules={[Navigation, Pagination, Thumbs]}
              thumbs={{ swiper: thumbsSwiper && !thumbsSwiper.destroyed ? thumbsSwiper : null }}
              navigation
              pagination={{ clickable: true }}
              spaceBetween={0}
              className="aspect-[4/3]"
            >
              {(images.length ? images : [FALLBACK]).map((img, idx) => (
                <SwiperSlide key={idx}>
                  <img
                    src={img.startsWith("http") ? img : mediaUrl(img)}
                    alt={`${item.title} ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                </SwiperSlide>
              ))}
            </Swiper>
          </div>
          {images.length > 1 && (
            <Swiper
              modules={[Thumbs]}
              watchSlidesProgress
              onSwiper={setThumbsSwiper}
              slidesPerView={Math.min(images.length, 5)}
              spaceBetween={8}
              className="!h-20"
            >
              {images.map((img, idx) => (
                <SwiperSlide key={idx} className="rounded-md overflow-hidden cursor-pointer">
                  <img
                    src={mediaUrl(img)}
                    alt=""
                    className="w-full h-20 object-cover hover:opacity-80"
                  />
                </SwiperSlide>
              ))}
            </Swiper>
          )}
        </div>

        {/* Details */}
        <div className="lg:col-span-2 space-y-5">
          <div>
            <div className="overline text-zinc-500 mb-2">
              <Tag className="w-3 h-3 inline mr-1" />
              {CATEGORIES_LABELS[item.category] || item.category}
            </div>
            <h1 className="font-display font-black text-3xl tracking-tight mb-1" data-testid="yard-sale-detail-title">{item.title}</h1>
            <div className="font-mono-num text-3xl font-bold text-zinc-950 mt-2" data-testid="yard-sale-detail-price">{formatKES(item.price)}</div>
          </div>

          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <div className="overline text-zinc-500 mb-1">Description</div>
            <p className="text-sm text-zinc-700 whitespace-pre-wrap leading-relaxed">{item.description || "No description provided."}</p>
          </div>

          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <div className="overline text-zinc-500 mb-2">Seller</div>
            <div className="font-display font-bold text-lg">{item.seller_name}</div>
            <div className="mt-3 space-y-2">
              {contactHidden ? (
                <div className="border border-dashed border-zinc-300 rounded-md p-3 text-sm text-zinc-500 flex items-center gap-2" data-testid="yard-sale-contact-locked">
                  <Lock className="w-4 h-4" />
                  Contact hidden — seller hasn't unlocked direct contact yet.
                </div>
              ) : (
                <>
                  {item.seller_phone && (
                    <a href={`tel:${item.seller_phone}`} className="flex items-center gap-2 text-sm font-mono-num text-zinc-900 hover:text-emerald-600" data-testid="yard-sale-contact-phone">
                      <Phone className="w-4 h-4" /> {item.seller_phone}
                    </a>
                  )}
                  {item.seller_email && (
                    <a href={`mailto:${item.seller_email}?subject=Interested in ${encodeURIComponent(item.title)}`} className="flex items-center gap-2 text-sm text-zinc-900 hover:text-emerald-600" data-testid="yard-sale-contact-email">
                      <Mail className="w-4 h-4" /> {item.seller_email}
                    </a>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Owner monetization actions */}
          {isOwner && (
            <div className="bg-white border border-zinc-200 rounded-xl p-5 space-y-3" data-testid="yard-sale-owner-actions">
              <div className="overline text-zinc-500">Boosts</div>
              {!item.contact_unlocked && (
                <Button onClick={() => setDialog("contact")} variant="outline" className="w-full justify-between h-12" data-testid="yard-sale-action-contact">
                  <span className="flex items-center gap-2"><Lock className="w-4 h-4" /> Unlock contact details</span>
                  <span className="font-mono-num text-mpesa font-bold">KES 35</span>
                </Button>
              )}
              {item.scope !== "all" && (
                <Button onClick={() => setDialog("broadcast")} variant="outline" className="w-full justify-between h-12" data-testid="yard-sale-action-broadcast">
                  <span className="flex items-center gap-2"><Globe2 className="w-4 h-4" /> Broadcast to all NyumbaOS tenants</span>
                  <span className="font-mono-num text-mpesa font-bold">KES 50</span>
                </Button>
              )}
              {!item.featured && (
                <Button onClick={() => setDialog("feature")} className="w-full justify-between h-12 bg-amber-400 hover:bg-amber-500 text-zinc-950" data-testid="yard-sale-action-feature">
                  <span className="flex items-center gap-2"><Sparkles className="w-4 h-4" /> Feature for 7 days</span>
                  <span className="font-mono-num font-bold">KES 100</span>
                </Button>
              )}
              {item.contact_unlocked && item.scope === "all" && item.featured && (
                <div className="text-xs text-emerald-700 text-center py-2">✨ All boosts active</div>
              )}
            </div>
          )}
        </div>
      </div>

      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="rounded-md max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-display font-black text-2xl">
              {dialog === "contact" && "Unlock contact details"}
              {dialog === "broadcast" && "Broadcast to all tenants"}
              {dialog === "feature" && "Feature listing"}
            </DialogTitle>
            <DialogDescription>
              {dialog === "contact" && "KES 35 — phone & email become visible to buyers and they can post directly on your listing."}
              {dialog === "broadcast" && "KES 50 — your listing shows to every tenant across NyumbaOS, not just your property."}
              {dialog === "feature" && "KES 100 — pinned at the top of the marketplace for 7 days."}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitPay} className="space-y-4" data-testid="yard-sale-pay-form">
            <div>
              <Label className="overline">M-Pesa phone</Label>
              <Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712345678" className="mt-1 font-mono-num" data-testid="yard-sale-pay-phone" />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={pending} className="bg-mpesa hover:bg-mpesa text-white w-full h-11" data-testid="yard-sale-pay-submit">
                <Smartphone className="w-4 h-4 mr-1.5" />
                {pending ? "Sending..." : (dialog === "contact" ? "Pay KES 35" : dialog === "broadcast" ? "Pay KES 50" : "Pay KES 100")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
