import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Toaster } from "@/components/ui/sonner";
import ErrorBoundary from "@/components/ErrorBoundary";

import LoginPage from "@/pages/Login";
import RegisterPage from "@/pages/Register";
import MarketplacePage from "@/pages/Marketplace";
import MarketplaceDetailPage from "@/pages/MarketplaceDetail";
import AppShell from "@/components/AppShell";
import DashboardPage from "@/pages/Dashboard";
import PropertiesPage from "@/pages/Properties";
import TenantsPage from "@/pages/Tenants";
import CaretakersPage from "@/pages/Caretakers";
import BillsPage from "@/pages/Bills";
import PaymentsPage from "@/pages/Payments";
import IssuesPage from "@/pages/Issues";
import ViewingsPage from "@/pages/Viewings";
import AdminDashboardPage from "@/pages/admin/AdminDashboard";
import AdminUsersPage from "@/pages/admin/AdminUsers";
import AdminPaymentsPage from "@/pages/admin/AdminPayments";
import AdminPayoutsPage from "@/pages/admin/AdminPayouts";
import AdminSettingsPage from "@/pages/admin/AdminSettings";
import AdminApprovalsPage from "@/pages/admin/AdminApprovals";
import AdminBillsPage from "@/pages/admin/AdminBills";
import AdminIssuesPage from "@/pages/admin/AdminIssues";
import AdminPropertiesPage from "@/pages/admin/AdminProperties";
import AdminModerationPage from "@/pages/admin/AdminModeration";
import CommunityPage from "@/pages/Community";
import YardSalePage from "@/pages/YardSale";
import YardSaleDetailPage from "@/pages/YardSaleDetail";
import LeasesPage from "@/pages/Leases";
import VisitorsPage from "@/pages/Visitors";
import SecurityPage from "@/pages/Security";

function RequireAuth({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-zinc-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role))
    return <Navigate to="/dashboard" replace />;
  return children;
}

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-zinc-500">Loading...</div>;
  if (!user) return <Navigate to="/marketplace" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Toaster richColors position="top-right" />
          <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/marketplace/:unitId" element={<MarketplaceDetailPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<RequireAuth><AppShell /></RequireAuth>}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/properties" element={<RequireAuth roles={["landlord"]}><PropertiesPage /></RequireAuth>} />
            <Route path="/tenants" element={<RequireAuth roles={["landlord"]}><TenantsPage /></RequireAuth>} />
            <Route path="/caretakers" element={<RequireAuth roles={["landlord"]}><CaretakersPage /></RequireAuth>} />
            <Route path="/bills" element={<RequireAuth roles={["landlord", "tenant"]}><BillsPage /></RequireAuth>} />
            <Route path="/payments" element={<RequireAuth roles={["landlord", "tenant"]}><PaymentsPage /></RequireAuth>} />
            <Route path="/issues" element={<RequireAuth roles={["landlord", "tenant", "caretaker", "security", "admin"]}><IssuesPage /></RequireAuth>} />
            <Route path="/viewings" element={<RequireAuth roles={["landlord", "prospect"]}><ViewingsPage /></RequireAuth>} />
            <Route path="/admin" element={<RequireAuth roles={["admin"]}><AdminDashboardPage /></RequireAuth>} />
            <Route path="/admin/users" element={<RequireAuth roles={["admin"]}><AdminUsersPage /></RequireAuth>} />
            <Route path="/admin/payments" element={<RequireAuth roles={["admin"]}><AdminPaymentsPage /></RequireAuth>} />
            <Route path="/admin/payouts" element={<RequireAuth roles={["admin"]}><AdminPayoutsPage /></RequireAuth>} />
            <Route path="/admin/settings" element={<RequireAuth roles={["admin"]}><AdminSettingsPage /></RequireAuth>} />
            <Route path="/admin/approvals" element={<RequireAuth roles={["admin"]}><AdminApprovalsPage /></RequireAuth>} />
            <Route path="/admin/bills" element={<RequireAuth roles={["admin"]}><AdminBillsPage /></RequireAuth>} />
            <Route path="/admin/issues" element={<RequireAuth roles={["admin"]}><AdminIssuesPage /></RequireAuth>} />
            <Route path="/admin/properties" element={<RequireAuth roles={["admin"]}><AdminPropertiesPage /></RequireAuth>} />
            <Route path="/admin/moderation" element={<RequireAuth roles={["admin"]}><AdminModerationPage /></RequireAuth>} />
            <Route path="/community" element={<RequireAuth roles={["landlord", "tenant", "caretaker", "security", "admin"]}><CommunityPage /></RequireAuth>} />
            <Route path="/yard-sale" element={<RequireAuth roles={["landlord", "tenant", "caretaker", "security", "admin"]}><YardSalePage /></RequireAuth>} />
            <Route path="/yard-sale/:id" element={<RequireAuth roles={["landlord", "tenant", "caretaker", "security", "admin"]}><YardSaleDetailPage /></RequireAuth>} />
            <Route path="/leases" element={<RequireAuth roles={["landlord", "tenant", "admin"]}><LeasesPage /></RequireAuth>} />
            <Route path="/visitors" element={<RequireAuth roles={["landlord", "tenant", "caretaker", "security", "admin", "prospect"]}><VisitorsPage /></RequireAuth>} />
            <Route path="/security" element={<RequireAuth roles={["landlord"]}><SecurityPage /></RequireAuth>} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ErrorBoundary>
  );
}
