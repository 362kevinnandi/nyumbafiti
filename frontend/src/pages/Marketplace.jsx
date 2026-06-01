import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Building2, MapPin, BedDouble, Search, ArrowRight, LogIn, Sparkles } from "lucide-react";
import { Swiper, SwiperSlide } from "swiper/react";
import { Navigation, Pagination, Autoplay } from "swiper/modules";
import "swiper/css";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "./swiper-overrides.css";
import AiChatButton from "@/components/AiChatButton";
import CardImageCarousel from "@/components/CardImageCarousel";

const FALLBACK_IMG = "https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=800";

const TYPE_FILTERS = [
  { value: "all", label: "All Types" },
  { value: "apartment", label: "Apartment" },
  { value: "own_compound", label: "Own Compound" },
];
const SUB_TYPE_FILTERS = [
  { value: "all", label: "Any Size" },
  { value: "bedsitter", label: "Bedsitter" },
  { value: "single_room", label: "Single Room" },
  { value: "1br", label: "1 BR" },
  { value: "2br", label: "2 BR" },
  { value: "3br", label: "3 BR" },
  { value: "4br", label: "4 BR" },
  { value: "5br_plus", label: "5+ BR" },
];

const TENANCY_FILTERS = [
  { value: "all", label: "Any" },
  { value: "rental", label: "For Rental" },
  { value: "lease", label: "For Lease" },
];

const subTypeLabel = (v) => SUB_TYPE_FILTERS.find((c) => c.value === v)?.label || "";
const typeLabel = (v) => TYPE_FILTERS.find((c) => c.value === v)?.label || "Apartment";

// 8 cards per slide (4 columns × 2 rows on desktop)
const CARDS_PER_SLIDE = 8;

function chunk(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

export default function MarketplacePage() {
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [maxRent, setMaxRent] = useState("");
  const [category, setCategory] = useState("all");
  const [subType, setSubType] = useState("all");
  const [tenancy, setTenancy] = useState("all");
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (maxRent) params.max_rent = maxRent;
    if (category && category !== "all") params.category = category;
    if (tenancy && tenancy !== "all") params.tenancy_type = tenancy;
    const r = await api.get("/public/listings", { params });
    setListings(r.data);
    setLoading(false);
  }, [maxRent, category, tenancy]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    let items = listings;
    if (subType !== "all") {
      items = items.filter((l) => (l.sub_type || l.property?.sub_type) === subType);
    }
    if (!q) return items;
    return items.filter(
      (l) =>
        l.property.name.toLowerCase().includes(q) ||
        l.property.address.toLowerCase().includes(q) ||
        l.unit_number.toLowerCase().includes(q)
    );
  }, [search, listings, subType]);

  const slides = useMemo(() => chunk(filtered, CARDS_PER_SLIDE), [filtered]);

  return (
    <div className="min-h-screen bg-warm" data-testid="marketplace-page">
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <Link to="/marketplace" className="flex items-center gap-2" data-testid="marketplace-logo">
            <div className="w-8 h-8 bg-zinc-950 rounded-md flex items-center justify-center">
              <Building2 className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display font-black text-base tracking-tight leading-none">NYUMBA FITI</div>
              <div className="overline text-zinc-500 text-[10px] mt-0.5">Listings · Nairobi</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <AiChatButton />
            {user ? (
              <Button onClick={() => navigate("/dashboard")} className="bg-zinc-950 hover:bg-zinc-800 h-9 rounded-md text-sm" data-testid="dashboard-link">
                Dashboard <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="outline" className="h-9 rounded-md text-sm" data-testid="marketplace-login-link"><LogIn className="w-4 h-4 mr-1" /> Sign in</Button>
                </Link>
                <Link to="/register">
                  <Button className="bg-zinc-950 hover:bg-zinc-800 h-9 rounded-md text-sm" data-testid="marketplace-register-link">List property</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-zinc-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 md:py-16">
          <div className="overline text-zinc-500 mb-3">Verified Nairobi Listings</div>
          <h1 className="font-display font-black text-4xl sm:text-5xl md:text-6xl tracking-tight leading-none max-w-3xl">
            Find your next home.<br />
            <span className="text-zinc-400">Book a viewing in seconds.</span>
          </h1>
          <p className="text-zinc-600 mt-5 max-w-xl text-base leading-relaxed">
            Every unit listed is verified, vacant, and managed by accountable landlords.
            Pay a one-time <span className="text-mpesa font-semibold">KES 200</span> viewing fee via M-Pesa to confirm your appointment and reveal caretaker contact details.
          </p>

          <div className="mt-8 grid grid-cols-1 sm:grid-cols-[1fr_180px_auto] gap-2 max-w-2xl">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <Input
                placeholder="e.g. Westlands 2 bedroom · or building name"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-11 pl-9 border-zinc-300"
                data-testid="marketplace-search"
              />
            </div>
            <Input
              placeholder="Max rent KES"
              type="number"
              value={maxRent}
              onChange={(e) => setMaxRent(e.target.value)}
              className="h-11 border-zinc-300"
              data-testid="marketplace-max-rent"
            />
            <Button onClick={load} className="h-11 bg-zinc-950 hover:bg-zinc-800 rounded-md" data-testid="marketplace-search-button">
              Search
            </Button>
          </div>

          {/* Category chips */}
          <div className="mt-6 space-y-3" data-testid="category-chips">
            <div className="flex flex-wrap gap-2">
              <span className="overline text-zinc-500 self-center mr-2">Type</span>
              {TYPE_FILTERS.map((c) => {
                const active = category === c.value;
                return (
                  <button
                    key={c.value}
                    onClick={() => setCategory(c.value)}
                    className={`px-4 h-9 rounded-full border text-xs font-semibold transition-all ${
                      active
                        ? "bg-zinc-950 text-white border-zinc-950 shadow-sm"
                        : "bg-white text-zinc-700 border-zinc-300 hover:border-zinc-500"
                    }`}
                    data-testid={`category-chip-${c.value}`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="overline text-zinc-500 self-center mr-2">Size</span>
              {SUB_TYPE_FILTERS.map((c) => {
                const active = subType === c.value;
                return (
                  <button
                    key={c.value}
                    onClick={() => setSubType(c.value)}
                    className={`px-3.5 h-8 rounded-full border text-xs font-semibold transition-all ${
                      active
                        ? "bg-zinc-950 text-white border-zinc-950"
                        : "bg-white text-zinc-700 border-zinc-300 hover:border-zinc-500"
                    }`}
                    data-testid={`subtype-chip-${c.value}`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="overline text-zinc-500 self-center mr-2">Tenancy</span>
              {TENANCY_FILTERS.map((c) => {
                const active = tenancy === c.value;
                return (
                  <button
                    key={c.value}
                    onClick={() => setTenancy(c.value)}
                    className={`px-4 h-8 rounded-full border text-xs font-semibold transition-all ${
                      active
                        ? "bg-amber-500 text-zinc-950 border-amber-500"
                        : "bg-white text-zinc-700 border-zinc-300 hover:border-amber-400"
                    }`}
                    data-testid={`tenancy-chip-${c.value}`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* Listings carousel */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-2">
          <div>
            <div className="uppercase tracking-[0.22em] text-[11px] text-zinc-500 border-t border-zinc-300 pt-2 w-fit">
              Available Now
            </div>
            <h2 className="font-display font-black text-4xl tracking-tight mt-3">
              {loading
                ? "Loading listings..."
                : `${filtered.length} Verified Vacant ${filtered.length === 1 ? "Unit" : "Units"}`}
            </h2>
            <div className="text-sm text-zinc-500 mt-2">
              {slides.length > 1
                ? `Swipe through ${slides.length} pages of listings`
                : "Click any unit to book a viewing"}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-7">
            {[1, 2, 3, 4].map((i) => <div key={i} className="bg-white border border-zinc-200 rounded-md h-72 animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white" data-testid="marketplace-empty">
            <Building2 className="w-11 h-11 shadow-sm mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg mb-1">No listings match</div>
            <div className="text-sm text-zinc-500">Try adjusting your filters or check back soon.</div>
          </div>
        ) : (
          <div className="marketplace-carousel" data-testid="listings-carousel">
            <Swiper
              modules={[Navigation, Pagination, Autoplay]}
              navigation
              pagination={{ clickable: true }}
              autoplay={{ delay: 5000, disableOnInteraction: false, pauseOnMouseEnter: true }}
              loop={slides.length > 1}
              spaceBetween={24}
              slidesPerView={1}
              className="rounded-md"
            >
              {slides.map((group, slideIdx) => (
                <SwiperSlide key={slideIdx}>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 px-1 pb-12" data-testid={`listings-slide-${slideIdx}`}>
                    {group.map((l) => (
                      <ListingCard key={l.id} l={l} />
                    ))}
                  </div>
                </SwiperSlide>
              ))}
            </Swiper>
          </div>
        )}
      </section>

      <footer className="border-t border-zinc-200 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-wrap items-center justify-between gap-4 text-sm text-zinc-500">
          <div>© 2026 Nyumba FitI · Built for landlords</div>
          <div className="flex gap-6">
            <Link to="/login" className="hover:text-zinc-950">Tenant / Landlord Login</Link>
            <Link to="/register" className="hover:text-zinc-950">List your property</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ListingCard({ l }) {
  return (
    <Link
      to={`/marketplace/${l.id}`}
      className="bg-white border border-zinc-200 rounded-2xl overflow-hidden block group transition-all duration-300 shadow-sm hover:-translate-y-1 hover:shadow-2xl hover:border-zinc-300"
      data-testid={`listing-card-${l.id}`}
    >
      <div className="relative h-44 overflow-hidden">
        <CardImageCarousel
          imagesList={l.property.images || []}
          fallback={FALLBACK_IMG}
          className="absolute inset-0 w-full h-full"
          rounded=""
        />
        <div className="absolute top-3 left-3 z-10 bg-white/95 backdrop-blur px-2 py-0.5 rounded-sm text-xs font-mono-num font-semibold">
          {formatKES(l.rent_amount)}/mo
        </div>
        {l.featured ? (
          <div className="absolute top-3 right-3 z-10 bg-amber-400 text-zinc-950 border border-amber-500 px-2 py-0.5 rounded-sm overline text-[10px] shadow flex items-center gap-1" data-testid={`featured-badge-${l.id}`}>
            <Sparkles className="w-3 h-3" /> Featured
          </div>
        ) : (
          <div className="absolute top-3 right-3 z-10 bg-zinc-950/90 text-white px-2 py-0.5 rounded-sm overline text-[10px]">
            Verified
          </div>
        )}
        <div className="absolute bottom-3 left-3 z-10 flex gap-1.5">
          <span className="bg-zinc-950/85 text-white px-2 py-0.5 rounded-sm overline text-[10px] backdrop-blur">
            {typeLabel(l.category)}
          </span>
          {(l.sub_type || l.property?.sub_type) && (
            <span className="bg-white/95 text-zinc-900 px-2 py-0.5 rounded-sm overline text-[10px] backdrop-blur">
              {subTypeLabel(l.sub_type || l.property?.sub_type)}
            </span>
          )}
          {(l.tenancy_types || []).map((tt) => (
            <span key={tt} className={`px-2 py-0.5 rounded-sm overline text-[10px] backdrop-blur ${tt === "lease" ? "bg-amber-400 text-zinc-950" : "bg-emerald-500/90 text-white"}`} data-testid={`tenancy-badge-${l.id}-${tt}`}>
              {tt === "lease" ? "FOR LEASE" : "FOR RENT"}
            </span>
          ))}
        </div>
      </div>
      <div className="p-4">
        <div className="font-display font-bold text-base leading-tight mb-1 group-hover:text-zinc-700 line-clamp-1">{l.property.name}</div>
        <div className="flex items-start gap-1.5 text-xs text-zinc-500 mb-3">
          <MapPin className="w-3 h-3 mt-0.5 shrink-0" />
          <span className="line-clamp-1">{l.property.address}</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-zinc-700 mb-3">
          <span className="flex items-center gap-1"><BedDouble className="w-3.5 h-3.5" /> {l.bedrooms} bed</span>
          <span className="text-zinc-300">·</span>
          <span className="font-mono-num">Unit {l.unit_number}</span>
        </div>
        <div className="flex items-center justify-between pt-3 border-t border-zinc-100">
          <div className="uppercase tracking-[0.18em] text-zinc-500 text-[10px] truncate max-w-[60%]">By {l.landlord_name}</div>
          <div className="text-xs font-semibold text-zinc-950 flex items-center gap-1 group-hover:gap-2 transition-all">
            View <ArrowRight className="w-3 h-3" />
          </div>
        </div>
      </div>
    </Link>
  );
}
