import api from "./client";

export interface FacturaRecibida {
  id: string;
  cfdi_uuid: string;
  issuer_rfc: string;
  issuer_legal_name: string;
  issuer_tax_system: string | null;
  receiver_rfc: string;
  receiver_legal_name: string | null;
  issue_date: string;
  payment_date: string | null;
  currency: string;
  exchange_rate: string | null;
  subtotal: string;
  tax_iva: string;
  tax_ieps: string;
  iva_retention: string;
  isr_retention: string;
  total: string;
  cfdi_type: string;
  cfdi_use: string | null;
  payment_form: string | null;
  payment_method: string | null;
  category: string | null;
  notes: string | null;
  sat_status: string;
  is_acreditable: boolean;
  acreditacion_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface GastosUploadResult {
  imported: number;
  duplicates: number;
  rejected: number;
  errors: string[];
}

export interface IvaAcreditableSummary {
  year: number;
  month: number;
  iva_acreditable: string;
  row_count: number;
}

export const gastosApi = {
  list: (params?: {
    year?: number;
    month?: number;
    category?: string;
    acreditable_only?: boolean;
  }) => api.get<FacturaRecibida[]>("/gastos", { params }).then(r => r.data),

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach(f => form.append("files", f));
    return api
      .post<GastosUploadResult>("/gastos/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then(r => r.data);
  },

  ivaAcreditable: (year: number, month: number) =>
    api
      .get<IvaAcreditableSummary>("/gastos/iva-acreditable", {
        params: { year, month },
      })
      .then(r => r.data),

  update: (
    id: string,
    patch: {
      category?: string | null;
      notes?: string | null;
      is_acreditable?: boolean;
      acreditacion_notes?: string | null;
      payment_date?: string | null;
    },
  ) => api.patch<FacturaRecibida>(`/gastos/${id}`, patch).then(r => r.data),
};
