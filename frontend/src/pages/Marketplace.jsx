import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatKES } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Building2, MapPin, BedDouble, Search, ArrowRight, LogIn } from "lucide-react";

const FALLBACK_IMG = "https://images.unsplash.com/photo-1630241466166-22e43156d8c0?crop=entropy&cs=srgb&fm=jpg&q=85&w=800";

export default function MarketplacePage() {
  const [listings, setListings] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [maxRent, setMaxRent] = useState("");
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (maxRent) params.max_rent = maxRent;
    const r = await api.get("/public/listings", { params });
    setListings(r.data);
    setLoading(false);
  }, [maxRent]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const q = search.toLowerCase().trim();
    if (!q) { setFiltered(listings); return; }
    setFiltered(
      listings.filter(
        (l) =>
          l.property.name.toLowerCase().includes(q) ||
          l.property.address.toLowerCase().includes(q) ||
          l.unit_number.toLowerCase().includes(q)
      )
    );
  }, [search, listings]);

  return (
    <div className="min-h-screen bg-[#FAFAFA]" data-testid="marketplace-page">
      {/* Public top nav */}
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <Link to="/marketplace" className="flex items-center gap-2" data-testid="marketplace-logo">
            <div className="w-8 h-8 bg-zinc-950 rounded-md flex items-center justify-center">
              <Building2 className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display font-black text-base tracking-tight leading-none">NYUMBA OS</div>
              <div className="overline text-zinc-500 text-[10px] mt-0.5">Listings · Nairobi</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
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
            Find your next home.<br/>
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
                placeholder="Search by area, building, unit..."
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
        </div>
      </section>

      {/* Listings */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-2">
          <div>
            <div className="overline text-zinc-500 mb-1">Available now</div>
            <h2 className="font-display font-black text-2xl tracking-tight">
              {loading ? "Loading listings..." : `${filtered.length} vacant ${filtered.length === 1 ? "unit" : "units"}`}
            </h2>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1,2,3].map(i => <div key={i} className="bg-white border border-zinc-200 rounded-md h-72 animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 border border-dashed border-zinc-200 rounded-md bg-white">
            <Building2 className="w-10 h-10 mx-auto text-zinc-300 mb-3" />
            <div className="font-display font-bold text-lg mb-1">No listings match</div>
            <div className="text-sm text-zinc-500">Try adjusting your search or check back soon.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="listings-grid">
            {filtered.map((l) => (
              <Link key={l.id} to={`/marketplace/${l.id}`} className="bg-white border border-zinc-200 rounded-md overflow-hidden card-hover block group" data-testid={`listing-card-${l.id}`}>
                <div
                  className="relative h-48 bg-zinc-100"
                  style={{ backgroundImage: `url(${l.property.image_url || FALLBACK_IMG})`, backgroundSize: "cover", backgroundPosition: "center" }}
                >
                  <div className="absolute top-3 left-3 bg-white/95 backdrop-blur px-2 py-0.5 rounded-sm text-xs font-mono-num font-semibold">
                    {formatKES(l.rent_amount)}/mo
                  </div>
                  <div className="absolute top-3 right-3 bg-zinc-950/90 text-white px-2 py-0.5 rounded-sm overline text-[10px]">
                    Verified
                  </div>
                </div>
                <div className="p-5">
                  <div className="font-display font-bold text-lg leading-tight mb-1 group-hover:text-zinc-700">{l.property.name}</div>
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
                    <div className="overline text-zinc-500 text-[10px]">By {l.landlord_name}</div>
                    <div className="text-xs font-semibold text-zinc-950 flex items-center gap-1 group-hover:gap-2 transition-all">
                      View <ArrowRight className="w-3 h-3" />
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <footer className="border-t border-zinc-200 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-wrap items-center justify-between gap-4 text-sm text-zinc-500">
          <div>© 2026 Nyumba OS · Built for Nairobi landlords</div>
          <div className="flex gap-6">
            <Link to="/login" className="hover:text-zinc-950">Tenant / Landlord Login</Link>
            <Link to="/register" className="hover:text-zinc-950">List your property</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
