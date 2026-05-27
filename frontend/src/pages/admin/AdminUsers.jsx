import { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { UserX, UserCheck, KeyRound, Copy, Download } from "lucide-react";
import ExportMenu from "@/components/ExportMenu";

const ROLE_LABELS = {
  admin: "Admin", landlord: "Landlord", tenant: "Tenant",
  caretaker: "Caretaker", security: "Security", prospect: "Prospect",
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [role, setRole] = useState("all");
  const [loading, setLoading] = useState(true);
  const [resetTarget, setResetTarget] = useState(null); // user object
  const [resetForm, setResetForm] = useState({ new_email: "", new_password: "", reason: "" });
  const [resetResult, setResetResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

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

  const openReset = (u) => {
    setResetTarget(u);
    setResetForm({ new_email: "", new_password: "", reason: "" });
    setResetResult(null);
  };

  const submitReset = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const body = { reason: resetForm.reason };
      if (resetForm.new_email.trim()) body.new_email = resetForm.new_email.trim();
      if (resetForm.new_password.trim()) body.new_password = resetForm.new_password.trim();
      else if (!resetForm.new_email.trim()) body.generate_password = true; // explicit opt-in
      const r = await api.post(`/admin/users/${resetTarget.id}/reset-credentials`, body);
      setResetResult(r.data);
      // Auto-copy generated password to clipboard
      if (r.data?.new_password) {
        try { await navigator.clipboard.writeText(r.data.new_password); } catch { /* ignore */ }
        toast.success("Credentials reset — new password copied to clipboard");
      } else {
        toast.success("Email updated");
      }
      load();
    } catch (err) {
      toast.error(formatApiError(err, "Reset failed"));
    } finally {
      setSubmitting(false);
    }
  };

  const closeReset = () => {
    setResetTarget(null);
    setResetResult(null);
  };

  return (
    <div data-testid="admin-users-page">
      <PageHeader
        overline="Super Admin"
        title="All Platform Users"
        action={<ExportMenu resource="users" testIdPrefix="users-export" />}
      />
      <Tabs value={role} onValueChange={setRole}>
        <TabsList className="bg-zinc-100 rounded-md mb-6 flex-wrap h-auto">
          <TabsTrigger value="all" data-testid="tab-all">All</TabsTrigger>
          {Object.entries(ROLE_LABELS).map(([k, v]) => (
            <TabsTrigger key={k} value={k} data-testid={`tab-${k}`}>{v}s</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={role}>
          {loading ? <div className="text-zinc-500">Loading...</div> : (
            <div className="bg-white border border-zinc-200 rounded-md overflow-x-auto" data-testid="users-table">
              <table className="w-full text-sm min-w-[800px]">
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
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        {u.role !== "admin" && (
                          <div className="flex gap-2 justify-end">
                            <Button size="sm" variant="outline" className="text-xs h-8" onClick={() => openReset(u)} data-testid={`reset-credentials-${u.id}`}>
                              <KeyRound className="w-3.5 h-3.5 mr-1" /> Reset
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs h-8" onClick={() => toggleSuspend(u)} data-testid={`toggle-suspend-${u.id}`}>
                              {u.suspended ? (<><UserCheck className="w-3.5 h-3.5 mr-1" /> Reactivate</>) : (<><UserX className="w-3.5 h-3.5 mr-1" /> Suspend</>)}
                            </Button>
                          </div>
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

      {/* Reset credentials dialog */}
      <Dialog open={!!resetTarget} onOpenChange={(o) => !o && closeReset()}>
        <DialogContent className="rounded-md max-w-md" data-testid="reset-credentials-dialog">
          <DialogHeader>
            <DialogTitle className="font-display font-black text-2xl flex items-center gap-2">
              <KeyRound className="w-5 h-5" /> Reset credentials
            </DialogTitle>
            <DialogDescription>
              {resetTarget && `${resetTarget.full_name} · ${resetTarget.email} (${resetTarget.role})`}
            </DialogDescription>
          </DialogHeader>

          {resetResult ? (
            <div className="space-y-3" data-testid="reset-result">
              <div className="bg-emerald-50 border border-emerald-200 rounded-md p-4">
                <div className="font-display font-bold text-base mb-2">Reset successful</div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between bg-white rounded px-3 py-2 border border-emerald-200">
                    <div><div className="overline text-zinc-500 text-[10px]">New email</div><div className="font-mono-num">{resetResult.new_email}</div></div>
                    <button onClick={() => { navigator.clipboard.writeText(resetResult.new_email); toast.success("Copied"); }} className="text-zinc-400 hover:text-zinc-950">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {resetResult.new_password && (
                    <div className="flex items-center justify-between bg-white rounded px-3 py-2 border border-emerald-200">
                      <div><div className="overline text-zinc-500 text-[10px]">New password</div><div className="font-mono-num" data-testid="reset-new-password">{resetResult.new_password}</div></div>
                      <button onClick={() => { navigator.clipboard.writeText(resetResult.new_password); toast.success("Copied"); }} className="text-zinc-400 hover:text-zinc-950">
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
                <p className="text-xs text-zinc-600 mt-3">⚠️ This password is shown ONCE. Share it with the user securely (already auto-copied to your clipboard).</p>
              </div>
              <Button onClick={closeReset} className="w-full" data-testid="reset-close-button">Done</Button>
            </div>
          ) : (
            <form onSubmit={submitReset} className="space-y-4" data-testid="reset-form">
              <div>
                <Label className="overline">New email (optional)</Label>
                <Input type="email" value={resetForm.new_email} onChange={(e) => setResetForm({ ...resetForm, new_email: e.target.value })} placeholder={resetTarget?.email} className="mt-1" data-testid="reset-new-email" />
              </div>
              <div>
                <Label className="overline">New password (leave blank to auto-generate)</Label>
                <Input value={resetForm.new_password} onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })} placeholder="Leave blank → random 10-char password" className="mt-1 font-mono-num" data-testid="reset-new-password-input" />
              </div>
              <div>
                <Label className="overline">Reason (audit log)</Label>
                <Input value={resetForm.reason} onChange={(e) => setResetForm({ ...resetForm, reason: e.target.value })} placeholder="User forgot password" className="mt-1" data-testid="reset-reason" />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={closeReset} data-testid="reset-cancel">Cancel</Button>
                <Button type="submit" disabled={submitting} className="bg-zinc-950 hover:bg-zinc-800" data-testid="reset-submit">
                  {submitting ? "Resetting..." : "Reset credentials"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
