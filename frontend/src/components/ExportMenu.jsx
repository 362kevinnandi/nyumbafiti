import { useState } from "react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Download, FileText, FileSpreadsheet, FileType2, Loader2 } from "lucide-react";
import { toast } from "sonner";

/**
 * Reusable Admin Export Menu — CSV / XLSX / PDF for a given resource.
 * resource ∈ users | payments | payouts | properties | bills | issues | viewings | leases
 * Calls /api/admin/export/{resource}.{ext} (admin-only) and triggers a browser download.
 */
export default function ExportMenu({ resource, testIdPrefix = "export" }) {
  const [busy, setBusy] = useState(false);

  const download = async (ext) => {
    if (busy) return;
    setBusy(true);
    try {
      const base = process.env.REACT_APP_BACKEND_URL;
      const token = localStorage.getItem("nrm_token");
      const res = await fetch(`${base}/api/admin/export/${resource}.${ext}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nyumbaos_${resource}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${ext.toUpperCase()} downloaded`);
    } catch (err) {
      toast.error("Export failed — check your admin session");
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="h-9 rounded-md" data-testid={`${testIdPrefix}-trigger`} disabled={busy}>
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Download className="w-4 h-4 mr-1.5" />}
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44" data-testid={`${testIdPrefix}-menu`}>
        <DropdownMenuItem onClick={() => download("csv")} data-testid={`${testIdPrefix}-csv`}>
          <FileText className="w-4 h-4 mr-2" /> CSV
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => download("xlsx")} data-testid={`${testIdPrefix}-xlsx`}>
          <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel (XLSX)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => download("pdf")} data-testid={`${testIdPrefix}-pdf`}>
          <FileType2 className="w-4 h-4 mr-2" /> PDF
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
