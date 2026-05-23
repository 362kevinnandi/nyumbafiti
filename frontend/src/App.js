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
  return user ? <Navigate to="/dashboard" replace /> : <Navigate to="/marketplace" replace />;
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
            <Route path="/issues" element={<RequireAuth roles={["landlord", "tenant", "caretaker"]}><IssuesPage /></RequireAuth>} />
            <Route path="/viewings" element={<RequireAuth roles={["landlord", "prospect"]}><ViewingsPage /></RequireAuth>} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ErrorBoundary>
  );
}
