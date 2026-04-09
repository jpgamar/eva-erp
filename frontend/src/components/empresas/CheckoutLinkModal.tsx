"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { empresasApi, type EmpresaListItem } from "@/lib/api/empresas";

interface CheckoutLinkModalProps {
  empresa: EmpresaListItem;
  open: boolean;
  onClose: () => void;
}

export function CheckoutLinkModal({ empresa, open, onClose }: CheckoutLinkModalProps) {
  const [amount, setAmount] = useState(empresa.monthly_amount?.toString() || "4000");
  const [description, setDescription] = useState(`Servicio EvaAI — ${empresa.name}`);
  const [interval, setInterval] = useState<"month" | "year">("month");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!amount || !email) {
      setError("Monto y correo son requeridos");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await empresasApi.createCheckoutLink(empresa.id, {
        amount_mxn: parseFloat(amount),
        description,
        interval,
        recipient_email: email,
      });
      setCheckoutUrl(result.checkout_url);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al crear el link");
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
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Crear link de cobro — {empresa.name}</DialogTitle>
        </DialogHeader>

        {checkoutUrl ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Link de pago creado. Comparte este link con el cliente para que realice su pago.
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
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Monto mensual (MXN)</Label>
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

            {error && <p className="text-sm text-red-500">{error}</p>}

            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={handleClose}>
                Cancelar
              </Button>
              <Button onClick={handleSubmit} disabled={loading}>
                {loading ? "Creando..." : "Crear link de cobro"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
