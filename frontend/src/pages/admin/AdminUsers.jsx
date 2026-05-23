import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { UserX, UserCheck } from "lucide-react";

const ROLE_LABELS = {
  admin: "Admin", landlord: "Landlord", tenant: "Tenant",
  caretaker: "Caretaker", prospect: "Prospect",
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [role, setRole] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const params = role === "all" ? {} : { role };
    const r = await api.get("/admin/users", { params });
    setUsers(r.data);
    setLoading(false);
  }, [role]);

  useEffect(() => { load(); }, [load]);

  const toggleSuspend = async (u) => {
    const action = u.suspended ? "reactivate" : "suspend";
    if (!window.confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} ${u.full_name}?`)) return;
    try {
      await api.patch(`/admin/users/${u.id}/suspend`, { suspended: !u.suspended });
      toast.success(`User ${action}d`);
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Failed"));
    }
  };

  return (
    <div data-testid="admin-users-page">
      <PageHeader overline="Super Admin" title="All Platform Users" />
      <Tabs value={role} onValueChange={setRole}>
        <TabsList className="bg-zinc-100 rounded-md mb-6">
          <TabsTrigger value="all" data-testid="tab-all">All ({users.length})</TabsTrigger>
          {Object.entries(ROLE_LABELS).map(([k, v]) => (
            <TabsTrigger key={k} value={k} data-testid={`tab-${k}`}>{v}s</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={role}>
          {loading ? <div className="text-zinc-500">Loading...</div> : (
            <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="users-table">
              <table className="w-full text-sm min-w-[700px]">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Name</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Email</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Role</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Phone</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Joined</th>
                    <th className="text-left px-4 py-3 overline text-zinc-500">Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-zinc-100 hover:bg-zinc-50" data-testid={`user-row-${u.id}`}>
                      <td className="px-4 py-3 font-semibold">{u.full_name}</td>
                      <td className="px-4 py-3 text-zinc-600">{u.email}</td>
                      <td className="px-4 py-3"><span className="badge-status bg-zinc-100 text-zinc-700">{u.role}</span></td>
                      <td className="px-4 py-3 text-zinc-600 font-mono-num text-xs">{u.phone}</td>
                      <td className="px-4 py-3 text-zinc-500 text-xs font-mono-num">{new Date(u.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <span className={`badge-status ${u.suspended ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                          {u.suspended ? "Suspended" : "Active"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {u.role !== "admin" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-xs h-8"
                            onClick={() => toggleSuspend(u)}
                            data-testid={`toggle-suspend-${u.id}`}
                          >
                            {u.suspended ? (<><UserCheck className="w-3.5 h-3.5 mr-1" /> Reactivate</>) : (<><UserX className="w-3.5 h-3.5 mr-1" /> Suspend</>)}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
