"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api/client";

interface PreviewPayload {
  plan_tier: "standard" | "pro";
  billing_interval: "monthly" | "annual";
  base_subtotal_minor: number;
  erp_description?: string | null;
}

export interface SubscriptionPreview {
  subscription_id: string | null;
  base_subtotal_minor: number;
  payable_total_minor: number;
  retention_applicable: boolean;
  person_type: string | null;
  preview?: {
    amount_due_minor: number;
    subtotal_minor: number;
    currency: string;
    period_end: number | null;
  } | null;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  empresaId: string;
  payload: PreviewPayload;
  onConfirmed: (result: SubscriptionPreview) => void;
  /** Banner text shown above the numbers (e.g., past-due warning). */
  warning?: string | null;
}

function formatMxn(centavos: number): string {
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(
    centavos / 100
  );
}

export function StripePreviewDialog({
  open,
  onOpenChange,
  empresaId,
  payload,
  onConfirmed,
  warning,
}: Props) {
  const [preview, setPreview] = useState<SubscriptionPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    setError(null);
    setLoading(true);
    api
      .post<SubscriptionPreview>(`/empresas/${empresaId}/subscription/preview`, payload)
      .then((r) => setPreview(r.data))
      .catch((err) => setError(err?.response?.data?.detail ?? "No se pudo generar el preview"))
      .finally(() => setLoading(false));
  }, [open, empresaId, payload]);

  async function confirm() {
    if (!preview) return;
    setApplying(true);
    setError(null);
    try {
      const idem = crypto.randomUUID();
      const { data } = await api.post<SubscriptionPreview>(
        `/empresas/${empresaId}/subscription/apply`,
        payload,
        { headers: { "X-Empresa-Idempotency-Key": idem } }
      );
      onConfirmed(data);
      onOpenChange(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Error al aplicar el cambio en Stripe");
    } finally {
      setApplying(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Vista previa del cambio</DialogTitle>
        </DialogHeader>
        {warning ? (
          <div className="rounded-md border border-yellow-200 bg-yellow-50 p-2 text-xs text-yellow-900">
            {warning}
          </div>
        ) : null}
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Calculando…
          </div>
        ) : error ? (
          <div className="space-y-2">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
              Cerrar
            </Button>
          </div>
        ) : preview ? (
          <div className="space-y-3 text-sm">
            <Row label="Subtotal" value={formatMxn(preview.base_subtotal_minor)} />
            {preview.retention_applicable ? (
              <>
                <Row label="IVA 16%" value={`+${formatMxn(preview.payable_total_minor - preview.base_subtotal_minor + _retentionsFromPreview(preview))}`} muted />
              </>
            ) : null}
            <Row
              label="Total a cobrar"
              value={formatMxn(preview.payable_total_minor)}
              highlight
            />
            {preview.preview ? (
              <>
                <div className="mt-2 border-t border-border pt-2" />
                <Row
                  label="Cargo prorrateado hoy"
                  value={formatMxn(preview.preview.amount_due_minor)}
                />
                <p className="text-xs text-muted-foreground">
                  Incluye crédito por días no usados del precio anterior.
                </p>
              </>
            ) : null}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
                Cancelar
              </Button>
              <Button onClick={confirm} disabled={applying} type="button">
                {applying ? "Aplicando…" : "Confirmar y cobrar"}
              </Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

// Very small helper — preview only shows aggregate payable_total_minor. For
// persona moral we approximate the retention slice so operators see the
// breakdown order-of-magnitude. Exact numbers live on the CFDI side.
function _retentionsFromPreview(preview: SubscriptionPreview): number {
  if (!preview.retention_applicable) return 0;
  // retention_ratio ≈ 0.119167 (ISR 1.25% + IVA ret 10.6667%).
  return Math.round(preview.base_subtotal_minor * 0.119167);
}

function Row({
  label,
  value,
  highlight,
  muted,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between ${
        highlight ? "border-t border-border pt-2 text-base font-semibold" : ""
      } ${muted ? "text-muted-foreground" : ""}`}
    >
      <span>{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
