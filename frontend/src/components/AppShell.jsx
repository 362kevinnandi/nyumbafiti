import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import NotificationBell from "@/components/NotificationBell";
import {
  Building2, LayoutDashboard, Home, Users, FileText,
  CreditCard, Wrench, HardHat, LogOut, ChevronRight, Calendar,
  ShieldCheck, Wallet, Settings, ClipboardCheck, MessageSquare,
  Megaphone, Tag, FileSignature, QrCode, Shield, ShieldAlert,
} from "lucide-react";

const NAV_BY_ROLE = {
  landlord: [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/properties", label: "Properties", icon: Home },
    { to: "/tenants", label: "Tenants", icon: Users },
    { to: "/caretakers", label: "Caretakers", icon: HardHat },
    { to: "/security", label: "Security", icon: Shield },
    { to: "/bills", label: "Bills", icon: FileText },
    { to: "/payments", label: "Payments", icon: CreditCard },
    { to: "/issues", label: "Issues", icon: Wrench },
    { to: "/viewings", label: "Viewings", icon: Calendar },
    { to: "/leases", label: "Agreements", icon: FileSignature },
    { to: "/community", label: "Community", icon: Megaphone },
    { to: "/yard-sale", label: "Yard Sale", icon: Tag },
    { to: "/visitors", label: "Visitors", icon: QrCode },
  ],
  tenant: [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/bills", label: "My Bills", icon: FileText },
    { to: "/payments", label: "Payment History", icon: CreditCard },
    { to: "/issues", label: "Report Issues", icon: Wrench },
    { to: "/leases", label: "My Agreement", icon: FileSignature },
    { to: "/community", label: "Community", icon: Megaphone },
    { to: "/yard-sale", label: "Yard Sale", icon: Tag },
    { to: "/visitors", label: "Visitors", icon: QrCode },
  ],
  caretaker: [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/issues", label: "Tickets", icon: Wrench },
    { to: "/visitors", label: "Visitor Entry", icon: QrCode },
    { to: "/community", label: "Community", icon: Megaphone },
  ],
  security: [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/visitors", label: "Visitor Entry", icon: QrCode },
    { to: "/issues", label: "Security Tickets", icon: Wrench },
    { to: "/community", label: "Community", icon: Megaphone },
  ],
  prospect: [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/viewings", label: "My Viewings", icon: Calendar },
    { to: "/visitors", label: "My Visitor Pass", icon: QrCode },
  ],
  admin: [
    { to: "/admin", label: "Platform Overview", icon: ShieldCheck },
    { to: "/admin/approvals", label: "Approvals", icon: ClipboardCheck },
    { to: "/admin/properties", label: "Properties", icon: Home },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/bills", label: "All Bills", icon: FileText },
    { to: "/admin/issues", label: "All Issues", icon: MessageSquare },
    { to: "/admin/payments", label: "All Payments", icon: CreditCard },
    { to: "/admin/payouts", label: "Payouts", icon: Wallet },
    { to: "/admin/disbursements", label: "Disbursements", icon: Wallet },
    { to: "/admin/moderation", label: "Moderation", icon: ShieldAlert },
    { to: "/leases", label: "All Agreements", icon: FileSignature },
    { to: "/community", label: "Community", icon: Megaphone },
    { to: "/yard-sale", label: "Yard Sale", icon: Tag },
    { to: "/visitors", label: "Visitor Passes", icon: QrCode },
    { to: "/admin/settings", label: "Settings", icon: Settings },
  ],
};

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) {
    navigate("/login");
    return null;
  }
  // Tenant sidebar label adapts to their tenancy type (lease vs rental)
  const navRaw = NAV_BY_ROLE[user.role] || [];
  const nav = navRaw.map((item) => {
    if (user.role === "tenant" && item.to === "/leases") {
      return {
        ...item,
        label: user.tenancy_type === "lease" ? "Lease Agreement" : "Rental Agreement",
      };
    }
    return item;
  });

  return (
    <div className="min-h-screen flex bg-warm">
      {/* Sidebar */}
      <aside className="hidden md:flex w-64 bg-zinc-50 border-r border-zinc-200 flex-col" data-testid="app-sidebar">
        <div className="px-5 py-5 border-b border-zinc-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-zinc-950 rounded-md flex items-center justify-center">
              <Building2 className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display font-black text-base tracking-tight leading-none">
                NYUMBA FITI
              </div>
              <div className="overline text-zinc-500 mt-0.5">
                {user.role}
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {nav.map((n) => (
            <NavLink
              key={n.to} to={n.to}
              className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
              data-testid={`nav-${n.label.toLowerCase().replace(/ /g, "-")}`}
            >
              <n.icon className="w-4 h-4" strokeWidth={1.8} />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-zinc-200 space-y-2">
          <div className="px-2 py-2">
            <div className="text-sm font-semibold text-zinc-900 truncate">{user.full_name}</div>
            <div className="text-xs text-zinc-500 truncate">{user.email}</div>
          </div>
          <button
            onClick={logout}
            className="sidebar-link w-full text-left"
            data-testid="logout-button"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 bg-white border-b border-zinc-200 px-4 py-3 z-40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-5 h-5" />
          <span className="font-display font-black text-base">NYUMBA FITI</span>
        </div>
        <div className="flex items-center gap-2">
          <NotificationBell />
          <button onClick={logout} className="text-xs font-semibold text-zinc-700">
            Sign out
          </button>
        </div>
      </div>

      <main className="flex-1 md:ml-0 mt-14 md:mt-0 overflow-x-hidden">
        {/* Desktop top-right bell */}
        <div className="hidden md:flex justify-end items-center px-6 pt-4">
          <NotificationBell />
        </div>
        {/* Mobile nav scroller */}
        <div className="md:hidden border-b border-zinc-200 bg-white overflow-x-auto px-2 py-2 flex gap-1">
          {nav.map((n) => (
            <NavLink
              key={n.to} to={n.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap ${
                  isActive ? "bg-zinc-950 text-white" : "text-zinc-600 hover:bg-zinc-100"
                }`
              }
            >
              <n.icon className="w-3.5 h-3.5" />
              {n.label}
            </NavLink>
          ))}
        </div>

        <div className="px-4 pb-4 sm:px-8 sm:pb-8 pt-2 max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export function PageHeader({ overline, title, action }) {
  return (
    <header className="mb-8 flex items-end justify-between gap-4 flex-wrap" data-testid="page-header">
      <div>
        <div className="overline text-zinc-500 mb-2 flex items-center gap-1">
          {overline} <ChevronRight className="w-3 h-3" />
        </div>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tight leading-none">
          {title}
        </h1>
      </div>
      {action}
    </header>
  );
}
