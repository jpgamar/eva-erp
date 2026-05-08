"use client";

import { useEffect, useState } from "react";
import { Settings2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  empresasApi,
  type EmpresaListItem,
  type PreviewCheckoutResponse,
} from "@/lib/api/empresas";

interface ConfigError {
  code: string;
  message: string;
  missingFields: string[];
}

interface CheckoutLinkModalProps {
  empresa: EmpresaListItem;
  open: boolean;
  onClose: () => void;
  onConfigure?: (missingFields: string[]) => void;
}

const FIELD_LABELS: Record<string, string> = {
  person_type: "Tipo de persona (moral o fisica)",
  rfc: "RFC",
  razon_social: "Razon Social",
  regimen_fiscal: "Regimen Fiscal",
  fiscal_postal_code: "CP Fiscal",
  cfdi_use: "Uso CFDI",
};

function humanizeField(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function parseConfigError(err: any): ConfigError | null {
  const detail = err?.response?.data?.detail;
  if (
    detail &&
    typeof detail === "object" &&
    Array.isArray(detail.missing_fields) &&
    detail.missing_fields.length > 0
  ) {
    return {
      code: typeof detail.code === "string" ? detail.code : "config_error",
      message:
        typeof detail.message === "string"
          ? detail.message
          : "Faltan datos de configuracion",
      missingFields: detail.missing_fields.filter(
        (f: unknown): f is string => typeof f === "string",
      ),
    };
  }
  return null;
}

function formatMXN(minorUnits: number): string {
  return `$${(minorUnits / 100).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function CheckoutLinkModal({ empresa, open, onClose, onConfigure }: CheckoutLinkModalProps) {
  const [amount, setAmount] = useState(empresa.monthly_amount?.toString() || "4000");
  const [description, setDescription] = useState(`Servicio EvaAI — ${empresa.name}`);
  const [interval, setInterval] = useState<"month" | "year">("month");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<PreviewCheckoutResponse | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [configError, setConfigError] = useState<ConfigError | null>(null);

  // Reset transient state whenever the modal is dismissed.
  useEffect(() => {
    if (!open) {
      setPreview(null);
      setCheckoutUrl(null);
      setError(null);
      setConfigError(null);
    }
  }, [open]);

  const handlePreview = async () => {
    if (!amount) {
      setError("Monto es requerido");
      return;
    }
    setLoading(true);
    setError(null);
    setConfigError(null);
    try {
      const result = await empresasApi.previewCheckout(empresa.id, {
        amount_mxn: parseFloat(amount),
      });
      setPreview(result);
    } catch (err: any) {
      const cfg = parseConfigError(err);
      if (cfg) {
        setConfigError(cfg);
      } else {
        const detail = err?.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Error al calcular desglose");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!amount || !email) {
      setError("Monto y correo son requeridos");
      return;
    }
    setLoading(true);
    setError(null);
    setConfigError(null);
    try {
      const result = await empresasApi.createCheckoutLink(empresa.id, {
        amount_mxn: parseFloat(amount),
        description,
        interval,
        recipient_email: email,
      });
      setCheckoutUrl(result.checkout_url);
    } catch (err: any) {
      const cfg = parseConfigError(err);
      if (cfg) {
        setConfigError(cfg);
        setPreview(null); // bounce user back to step 1 so the callout is visible
      } else {
        const detail = err?.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Error al crear el link");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (checkoutUrl) {
      navigator.clipboard.writeText(checkoutUrl);
    }
  };

  const handleClose = () => {
    setCheckoutUrl(null);
    setPreview(null);
    setError(null);
    setConfigError(null);
    onClose();
  };

  const handleBack = () => {
    setPreview(null);
    setError(null);
  };

  const handleConfigureClick = () => {
    if (configError && onConfigure) {
      onConfigure(configError.missingFields);
    }
  };

  const renderConfigCallout = () =>
    configError && (
      <div
        className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-2 dark:border-amber-700/60 dark:bg-amber-950/40"
        data-testid="checkout-config-error"
      >
        <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
          {configError.message}
        </p>
        <p className="text-xs text-amber-800 dark:text-amber-200">
          Faltan: {configError.missingFields.map(humanizeField).join(", ")}
        </p>
        {onConfigure && (
          <Button
            size="sm"
            variant="outline"
            className="border-amber-400 bg-white text-amber-900 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-100"
            onClick={handleConfigureClick}
          >
            <Settings2 className="mr-1 h-3.5 w-3.5" />
            Configurar empresa
          </Button>
        )}
      </div>
    );

  // Step 3: URL generated — show copy/open
  if (checkoutUrl) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Link de cobro creado — {empresa.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Comparte este link con el cliente para que realice su pago.
            </p>
            <div className="flex gap-2">
              <Input value={checkoutUrl} readOnly className="text-xs" />
              <Button onClick={handleCopy} variant="outline" size="sm">
                Copiar
              </Button>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => window.open(checkoutUrl, "_blank")} variant="outline" className="flex-1">
                Abrir link
              </Button>
              <Button onClick={handleClose} className="flex-1">
                Listo
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Step 2: Preview shown — confirm and create
  if (preview) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Desglose de cobro — {empresa.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-lg border p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Monto base</span>
                <span className="font-medium">{formatMXN(preview.base_subtotal_minor)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>IVA 16%</span>
                <span>
                  {preview.stripe_charges_tax
                    ? `~${formatMXN(preview.iva_minor)} (Stripe)`
                    : `+${formatMXN(preview.iva_minor)}`}
                </span>
              </div>
              {preview.retention_applicable && (
                <>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Ret. ISR 1.25%</span>
                    <span>-{formatMXN(preview.isr_retention_minor)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Ret. IVA 10.67%</span>
                    <span>-{formatMXN(preview.iva_retention_minor)}</span>
                  </div>
                </>
              )}
              <div className="border-t pt-2 flex justify-between font-semibold">
                <span>Total a cobrar</span>
                <span>{formatMXN(preview.payable_total_minor)}</span>
              </div>
              {preview.stripe_charges_tax && (
                <p className="text-xs text-muted-foreground">
                  Stripe calculara el IVA automaticamente cuando el cliente ingrese su direccion.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Correo del cliente</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="cliente@empresa.com"
              />
              <p className="text-xs text-muted-foreground">
                Este correo aparecera en Stripe y recibira las facturas.
              </p>
            </div>

            {renderConfigCallout()}
            {error && <p className="text-sm text-red-500">{error}</p>}

            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={handleBack}>
                Atras
              </Button>
              <Button onClick={handleCreate} disabled={loading || !email}>
                {loading ? "Creando..." : "Crear link de cobro"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Step 1: Enter amount and see preview
  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Crear link de cobro — {empresa.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Monto base antes de IVA (MXN)</Label>
            <Input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="2000"
              min="1"
            />
          </div>
          <div className="space-y-2">
            <Label>Descripcion</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Servicio EvaAI"
            />
          </div>
          <div className="space-y-2">
            <Label>Intervalo</Label>
            <div className="flex gap-2">
              <Button
                variant={interval === "month" ? "default" : "outline"}
                size="sm"
                onClick={() => setInterval("month")}
                type="button"
              >
                Mensual
              </Button>
              <Button
                variant={interval === "year" ? "default" : "outline"}
                size="sm"
                onClick={() => setInterval("year")}
                type="button"
              >
                Anual
              </Button>
            </div>
          </div>

          {renderConfigCallout()}
          {error && <p className="text-sm text-red-500">{error}</p>}

          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={handleClose}>
              Cancelar
            </Button>
            <Button onClick={handlePreview} disabled={loading || !amount}>
              {loading ? "Calculando..." : "Ver desglose"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
