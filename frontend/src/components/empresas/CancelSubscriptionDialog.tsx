"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api/client";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  empresaId: string;
  /** Called with the response on success. */
  onCanceled: (result: {
    cancel_at_period_end: boolean;
    cancellation_scheduled_at: number | null;
    subscription_status: string;
  }) => void;
}

export function CancelSubscriptionDialog({ open, onOpenChange, empresaId, onCanceled }: Props) {
  const [atPeriodEnd, setAtPeriodEnd] = useState(true);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const idem = crypto.randomUUID();
      const { data } = await api.post(
        `/empresas/${empresaId}/subscription/cancel`,
        { at_period_end: atPeriodEnd, cancel_reason: reason.trim() || null },
        { headers: { "X-Empresa-Idempotency-Key": idem } }
      );
      onCanceled(data);
      onOpenChange(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "No se pudo cancelar la suscripción.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancelar suscripción</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <fieldset className="space-y-2">
            <legend className="font-medium">Cuándo</legend>
            <label className="flex items-start gap-2">
              <input
                type="radio"
                name="at-period-end"
                checked={atPeriodEnd}
                onChange={() => setAtPeriodEnd(true)}
              />
              <span>
                <strong>Al final del periodo actual</strong> (recomendado) — el cliente sigue con
                acceso hasta que termine el periodo pagado.
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="radio"
                name="at-period-end"
                checked={!atPeriodEnd}
                onChange={() => setAtPeriodEnd(false)}
              />
              <span>
                <strong>Inmediatamente</strong> — accesos se cortan ahora y se emite una factura
                final.
              </span>
            </label>
          </fieldset>
          <div className="space-y-1">
            <label className="text-sm font-medium">Razón (opcional)</label>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ej. implementación completada"
              maxLength={500}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
              Mantener
            </Button>
            <Button onClick={submit} disabled={submitting} type="button">
              {submitting ? "Cancelando…" : "Cancelar suscripción"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
