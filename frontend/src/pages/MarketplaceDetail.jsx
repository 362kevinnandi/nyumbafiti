import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, formatApiError, formatKES, mediaUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Building2, MapPin, BedDouble, Smartphone, CheckCircle2,
  ArrowLeft, ShieldCheck, Calendar as CalendarIcon, Phone, User,
  Copy, Mail
} from "lucide-react";
import { Swiper, SwiperSlide } from "swiper/react";

import "swiper/css";
import "./swiper-overrides.css";
import "swiper/css/navigation";

import { Navigation } from "swiper/modules";
import { useRef } from "react";
import "swiper/css/pagination";

const FALLBACK_IMG = "https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200";

export default function MarketplaceDetailPage() {
  const { unitId } = useParams();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bookOpen, setBookOpen] = useState(false);
  const [activeImage, setActiveImage] = useState(0);
  const swiperRef = useRef(null);
  const load = useCallback(async () => {
    try {
      const r = await api.get(`/public/listings/${unitId}`);
      setListing(r.data);
    } catch {
      toast.error("Listing not found or no longer available");
      navigate("/marketplace");
    }
    setLoading(false);
  }, [unitId, navigate]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-12 text-zinc-500 text-center">Loading...</div>;
  if (!listing) return null;

  return (
    <div className="min-h-screen bg-[#FAFAFA]" data-testid="listing-detail-page">
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <Link to="/marketplace" className="flex items-center gap-2 text-sm font-semibold text-zinc-600 hover:text-zinc-950" data-testid="back-to-marketplace">
            <ArrowLeft className="w-4 h-4" /> All Listings
          </Link>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5" />
            <span className="font-display font-black text-base tracking-tight">NYUMBA OS</span>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
<div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-8 items-start">        
    {/* Main content */}
          <div>
  <div className="relative rounded-md overflow-hidden border border-zinc-200 bg-white w-full">

<Swiper
  modules={[Navigation]}
  navigation
  spaceBetween={0}
  slidesPerView={1}
  className="w-full h-[400px] rounded-md"
  onSwiper={(swiper) => {
    swiperRef.current = swiper;
  }}
  onSlideChange={(swiper) => {
    setActiveImage(swiper.activeIndex);
  }}
>

    {(listing.property.images?.length
      ? listing.property.images
      : [FALLBACK_IMG]
    ).map((img, index) => (

      <SwiperSlide key={index}>

        <img
          src={
            img.startsWith("http")
              ? img
              : mediaUrl(img)
          }
          alt={`Property ${index + 1}`}
         className="block w-full h-[400px] object-cover bg-zinc-100 transition-all duration-300"        />

      </SwiperSlide>

    ))}

  </Swiper>
  <div className="absolute bottom-3 right-3 z-20 bg-zinc-950/80 text-white text-xs px-2 py-1 rounded-md font-medium backdrop-blur-sm">
  {activeImage + 1} / {(listing.property.images?.length || 1)}
</div>

</div>
<div className="flex gap-3 mt-4 mb-6 overflow-x-auto pb-1">

  {listing.property.images?.map((img, index) => (

    <img
      key={index}
      src={mediaUrl(img)}
      alt=""
      onClick={() => {
  setActiveImage(index);
  swiperRef.current?.slideTo(index);
}}
      className={`w-28 h-20 shrink-0 object-cover rounded-md border cursor-pointer transition-all duration-200 ${
        activeImage === index
          ? "border-black ring-2 ring-black shadow-xl brightness-[1.02]"
          : "border-zinc-200 opacity-80 hover:opacity-100 hover:border-zinc-400"
      }`}
    />

  ))}

</div>
            <div className="overline text-zinc-500 mb-2">Verified Listing · Vacant</div>
            <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tight leading-none mb-3">
              {listing.property.name}
            </h1>
            <div className="flex items-center gap-1.5 text-zinc-600 mb-6">
              <MapPin className="w-4 h-4" /> <span>{listing.property.address}</span>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-8 max-w-md">
              <div className="bg-white border border-zinc-200 rounded-md p-4">
                <div className="overline text-zinc-500 mb-1">Monthly</div>
                <div className="font-display font-black text-xl font-mono-num">{formatKES(listing.rent_amount)}</div>
              </div>
              <div className="bg-white border border-zinc-200 rounded-md p-4">
                <div className="overline text-zinc-500 mb-1">Bedrooms</div>
                <div className="font-display font-black text-xl font-mono-num">{listing.bedrooms}</div>
              </div>
              <div className="bg-white border border-zinc-200 rounded-md p-4">
                <div className="overline text-zinc-500 mb-1">Unit</div>
                <div className="font-display font-black text-xl font-mono-num">{listing.unit_number}</div>
              </div>
            </div>

            <div className="overline text-zinc-500 mb-2">About this listing</div>
            <p className="text-zinc-700 leading-relaxed mb-6 whitespace-pre-wrap">
              {listing.description || listing.property.description || "Modern unit available in a well-managed property. Book a viewing to see it in person and confirm your interest."}
            </p>

            <div className="border border-zinc-200 bg-white rounded-md p-5 max-w-xl">
              <div className="flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-display font-bold mb-1">How viewings work</div>
                  <p className="text-sm text-zinc-600 leading-relaxed">
                    Pick a date/time, pay KES {listing.viewing_fee} via M-Pesa, and instantly receive the caretaker's phone number plus the exact property address. The fee secures your slot and screens out time-wasters.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Booking sidebar */}
<aside className="hidden lg:block lg:sticky lg:top-24 self-start">
              <div className="bg-white border border-zinc-200 rounded-md p-6">
              <div className="overline text-zinc-500 mb-2">Listed by</div>
              <div className="font-display font-bold text-lg mb-1">{listing.landlord_name}</div>
              <div className="text-xs text-zinc-500 mb-6">Verified landlord on Nyumba OS</div>

              <div className="border-t border-zinc-100 pt-5">
                <div className="overline text-zinc-500 mb-2">Viewing fee</div>
                <div className="flex items-baseline gap-2 mb-6">
                  <span className="font-display font-black text-4xl text-mpesa font-mono-num">{formatKES(listing.viewing_fee)}</span>
                  <span className="text-xs text-zinc-500">via M-Pesa</span>
                </div>

                <BookViewingDialog listing={listing} open={bookOpen} setOpen={setBookOpen} />
                <p className="text-xs text-zinc-500 mt-3 text-center leading-relaxed">
                  Refundable if landlord no-shows
                </p>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function BookViewingDialog({ listing, open, setOpen }) {
  const today = new Date().toISOString().split("T")[0];
  const [form, setForm] = useState({
    prospect_name: "", prospect_email: "", prospect_phone: "",
    scheduled_date: today, scheduled_time: "10:00", notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [viewingId, setViewingId] = useState(null);
  const [credentials, setCredentials] = useState(null);
  const [statusInfo, setStatusInfo] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const r = await api.post("/public/viewings", { ...form, unit_id: listing.id });
      setViewingId(r.data.viewing_id);
      if (r.data.prospect_password) {
        setCredentials({ email: r.data.prospect_email, password: r.data.prospect_password });
      }
      toast.success("STK push sent! Check your phone.");
      const start = Date.now();
      // poll
      const interval = setInterval(async () => {
        // After 25s, force a real Safaricom status query (truth, not assumption)
        if (Date.now() - start > 25_000 && Date.now() - start < 28_000 && r.data.payment_id) {
          try { await api.post(`/payments/${r.data.payment_id}/check`); } catch { /* ignore */ }
        }
        try {
          const sr = await api.get(`/public/viewings/${r.data.viewing_id}`);
          setStatusInfo(sr.data);
          if (sr.data.status === "scheduled") {
            clearInterval(interval);
            toast.success("Booking confirmed!");
          } else if (sr.data.payment_status === "failed") {
            clearInterval(interval);
            toast.error("Payment did not go through — " + (sr.data.payment_result_desc || "no response"));
          }
        } catch (err) {
          console.error("Poll error:", err);
        }
      }, 2000);
      setTimeout(() => clearInterval(interval), 120000);
    } catch (err) {
      toast.error(formatApiError(err, "Failed to initiate booking"));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setViewingId(null);
    setCredentials(null);
    setStatusInfo(null);
    setOpen(false);
  };

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success("Copied"); };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); else setOpen(true); }}>
      <DialogTrigger asChild>
        <Button className="w-full h-12 bg-mpesa hover:bg-mpesa text-white rounded-md font-semibold text-base" data-testid="book-viewing-button">
          <Smartphone className="w-4 h-4 mr-2" /> Book Viewing
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-md max-w-md" data-testid="booking-dialog">
        {!viewingId ? (
          <>
            <DialogHeader>
              <DialogTitle className="font-display font-black text-2xl">Book a Viewing</DialogTitle>
              <DialogDescription>
                Reserve your slot at {listing.property.name} · Unit {listing.unit_number}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={submit} className="space-y-4" data-testid="booking-form">
              <div>
                <Label className="overline">Full name</Label>
                <Input required value={form.prospect_name} onChange={(e) => setForm({...form, prospect_name: e.target.value})} className="mt-1" data-testid="booking-name-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="overline">Email</Label><Input required type="email" value={form.prospect_email} onChange={(e) => setForm({...form, prospect_email: e.target.value})} className="mt-1" data-testid="booking-email-input" /></div>
                <div><Label className="overline">M-Pesa phone</Label><Input required value={form.prospect_phone} onChange={(e) => setForm({...form, prospect_phone: e.target.value})} placeholder="0712345678" className="mt-1 font-mono-num" data-testid="booking-phone-input" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="overline">Date</Label><Input required type="date" min={today} value={form.scheduled_date} onChange={(e) => setForm({...form, scheduled_date: e.target.value})} className="mt-1" data-testid="booking-date-input" /></div>
                <div><Label className="overline">Time</Label><Input required type="time" value={form.scheduled_time} onChange={(e) => setForm({...form, scheduled_time: e.target.value})} className="mt-1" data-testid="booking-time-input" /></div>
              </div>
              <div>
                <Label className="overline">Notes (optional)</Label>
                <Textarea rows={2} value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="mt-1" placeholder="Anything the caretaker should know..." />
              </div>
              <div className="bg-zinc-50 border border-zinc-200 rounded-md p-3 text-sm">
                <div className="flex justify-between"><span className="text-zinc-600">Viewing fee</span><span className="font-mono-num font-semibold">{formatKES(listing.viewing_fee)}</span></div>
                <div className="flex justify-between text-xs text-zinc-500 mt-1"><span>Payment method</span><span>M-Pesa STK Push</span></div>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={submitting} className="bg-mpesa hover:bg-mpesa text-white w-full h-11" data-testid="booking-submit-button">
                  <Smartphone className="w-4 h-4 mr-1.5" />
                  {submitting ? "Sending STK push..." : `Pay ${formatKES(listing.viewing_fee)}`}
                </Button>
              </DialogFooter>
            </form>
          </>
        ) : (
          <div data-testid="booking-result">
            <DialogHeader>
              <DialogTitle className="font-display font-black text-2xl flex items-center gap-2">
                {statusInfo?.status === "scheduled" ? (
                  <><CheckCircle2 className="w-6 h-6 text-emerald-600" /> Confirmed!</>
                ) : (
                  <><Smartphone className="w-6 h-6 text-mpesa animate-pulse" /> Awaiting Payment...</>
                )}
              </DialogTitle>
              <DialogDescription>
                {statusInfo?.status === "scheduled"
                  ? "Your viewing is locked in. Save the details below."
                  : "Enter your M-Pesa PIN on your phone to confirm KES " + listing.viewing_fee + "."}
              </DialogDescription>
            </DialogHeader>

            {statusInfo?.status === "scheduled" ? (
              <div className="space-y-4 mt-4" data-testid="booking-confirmed">
                <div className="bg-emerald-50 border border-emerald-200 rounded-md p-4">
                  <div className="overline text-emerald-700 mb-1">Receipt</div>
                  <div className="font-mono-num font-bold text-emerald-900">{statusInfo.mpesa_receipt}</div>
                </div>

                <div className="border border-zinc-200 rounded-md divide-y divide-zinc-100">
                  <div className="p-3 flex items-start gap-3">
                    <CalendarIcon className="w-4 h-4 text-zinc-400 mt-0.5" />
                    <div>
                      <div className="overline text-zinc-500 text-[10px]">Appointment</div>
                      <div className="font-semibold text-sm">{statusInfo.scheduled_date} at {statusInfo.scheduled_time}</div>
                    </div>
                  </div>
                  <div className="p-3 flex items-start gap-3">
                    <MapPin className="w-4 h-4 text-zinc-400 mt-0.5" />
                    <div>
                      <div className="overline text-zinc-500 text-[10px]">Address</div>
                      <div className="font-semibold text-sm">{statusInfo.property_name} · Unit {statusInfo.unit_number}</div>
                      <div className="text-xs text-zinc-600">{statusInfo.property_address}</div>
                    </div>
                  </div>
                  {statusInfo.caretaker_contact && (
                    <div className="p-3 flex items-start gap-3">
                      <User className="w-4 h-4 text-zinc-400 mt-0.5" />
                      <div>
                        <div className="overline text-zinc-500 text-[10px]">Caretaker</div>
                        <div className="font-semibold text-sm">{statusInfo.caretaker_contact.full_name}</div>
                        <a href={`tel:${statusInfo.caretaker_contact.phone}`} className="text-xs text-zinc-700 font-mono-num flex items-center gap-1">
                          <Phone className="w-3 h-3" /> {statusInfo.caretaker_contact.phone}
                        </a>
                      </div>
                    </div>
                  )}
                  {statusInfo.landlord_contact && (
                    <div className="p-3 flex items-start gap-3">
                      <User className="w-4 h-4 text-zinc-400 mt-0.5" />
                      <div>
                        <div className="overline text-zinc-500 text-[10px]">Landlord</div>
                        <div className="font-semibold text-sm">{statusInfo.landlord_contact.full_name}</div>
                        <a href={`tel:${statusInfo.landlord_contact.phone}`} className="text-xs text-zinc-700 font-mono-num flex items-center gap-1">
                          <Phone className="w-3 h-3" /> {statusInfo.landlord_contact.phone}
                        </a>
                      </div>
                    </div>
                  )}
                </div>

                {credentials && (
                  <div className="border-2 border-amber-200 bg-amber-50 rounded-md p-4">
                    <div className="overline text-amber-800 mb-2 flex items-center gap-1.5"><Mail className="w-3 h-3" /> Save your login</div>
                    <p className="text-xs text-amber-800 mb-3">An account was created so you can track this and future viewings. Save these credentials:</p>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between bg-white rounded px-3 py-2 border border-amber-200">
                        <div><div className="overline text-zinc-500 text-[10px]">Email</div><div className="font-mono-num">{credentials.email}</div></div>
                        <button onClick={() => copy(credentials.email)} className="text-zinc-400 hover:text-zinc-950"><Copy className="w-3.5 h-3.5" /></button>
                      </div>
                      <div className="flex items-center justify-between bg-white rounded px-3 py-2 border border-amber-200">
                        <div><div className="overline text-zinc-500 text-[10px]">Password</div><div className="font-mono-num">{credentials.password}</div></div>
                        <button onClick={() => copy(credentials.password)} className="text-zinc-400 hover:text-zinc-950"><Copy className="w-3.5 h-3.5" /></button>
                      </div>
                    </div>
                  </div>
                )}

                <Link to="/login">
                  <Button className="w-full bg-zinc-950 hover:bg-zinc-800 h-11" data-testid="login-to-track-button">Sign in to track your viewings</Button>
                </Link>
              </div>
            ) : (
              <div className="py-8 text-center space-y-3" data-testid="booking-pending">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 flex items-center justify-center">
                  <Smartphone className="w-6 h-6 text-mpesa animate-pulse" />
                </div>
                <div className="font-display font-bold">
                  {statusInfo?.payment_status === "failed" ? "Payment failed" : "Check your phone for the M-Pesa prompt"}
                </div>
                <div className="text-xs text-zinc-500">Booking ref: <span className="font-mono-num">{viewingId.slice(0, 8)}</span></div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
