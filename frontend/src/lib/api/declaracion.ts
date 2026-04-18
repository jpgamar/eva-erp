import api from "./client";

export interface IsrResicoPf {
  ingresos: string;
  tasa: string;
  impuesto_mensual: string;
  isr_retenido_por_pms: string;
  impuesto_a_pagar: string;
  saldo_a_favor: string;
}

export interface IvaSimplificado {
  actividades_gravadas_16: string;
  iva_trasladado: string;
  iva_retenido_por_pms: string;
  iva_acreditable: string;
  impuesto_a_pagar: string;
  saldo_a_favor: string;
}

export interface DeclaracionWarning {
  severity: "blocker" | "warning" | "info";
  code: string;
  message: string;
}

export interface DeclaracionResponse {
  year: number;
  month: number;
  rfc: string;
  isr: IsrResicoPf;
  iva: IvaSimplificado;
  warnings: DeclaracionWarning[];
}

export interface DeclaracionAlert {
  severity: "blocker" | "warning" | "info";
  code: string;
  message: string;
  deep_link: string | null;
}

export interface DeclaracionAlertsResponse {
  today: string;
  alerts: DeclaracionAlert[];
}

export const declaracionApi = {
  get: (year: number, month: number) =>
    api
      .get<DeclaracionResponse>(`/declaracion/${year}/${month}`)
      .then(r => r.data),

  alerts: () =>
    api.get<DeclaracionAlertsResponse>("/declaracion/alerts").then(r => r.data),
};
