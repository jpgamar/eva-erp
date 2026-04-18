# Declaración mensual RESICO PF — calculadora

El endpoint `GET /api/v1/declaracion/{year}/{month}` devuelve los
números exactos que el operador debe capturar en el portal del SAT
para la declaración mensual. Lee facturas emitidas, complementos de
pago, y gastos recibidos; aplica la tabla RESICO PF; compara contra
retenciones recibidas; arroja el impuesto a pagar o saldo a favor.

## Qué calcula

### ISR simplificado de confianza

```
Ingresos = Σ subtotal de facturas PUE emitidas en el mes (por issued_at)
         + Σ (subtotal × payment_amount/total) de complementos P
           en el mes (por payment_date)

Tasa    = resico_pf_rate_for(Ingresos)   [tabla 1.0%–2.5%]

Impuesto_mensual = Ingresos × Tasa

ISR_retenido = Σ isr_retention de esas facturas y complementos

ISR_a_pagar   = max(Impuesto_mensual − ISR_retenido, 0)
Saldo_a_favor = max(ISR_retenido − Impuesto_mensual, 0)
```

Notas:

- **No hay deducciones** para ISR en RESICO PF. La base es ingreso bruto.
- La tasa aplica al total mensual completo, no por tramos.
- PUE: fecha del CFDI = fecha de cobro (SAT convention).
- PPD: el cobro se contabiliza en la fecha del complemento.

### IVA simplificado de confianza

```
Actividades_gravadas_16 = Ingresos
IVA_trasladado          = Σ tax (16%) de facturas cobradas en el mes
IVA_retenido            = Σ iva_retention de esas facturas
IVA_acreditable         = Σ tax_iva de gastos recibidos pagados en el mes
                          donde is_acreditable=true y cfdi_type='I'

IVA_a_pagar   = max(IVA_trasladado − IVA_retenido − IVA_acreditable, 0)
Saldo_a_favor = max(IVA_acreditable + IVA_retenido − IVA_trasladado, 0)
```

## Warnings que devuelve

| Severidad | Código | Significado |
|---|---|---|
| blocker | `pending_payment_complement` | Hay cobros del mes sin CFDI tipo P timbrado. Riesgo de multa SAT (regla del día 5). |
| warning | `stamp_failed_facturas` | Facturas que el outbox abandonó tras N retries. No aparecen en el prellenado del SAT hasta remediar. |

Arreglar cualquier `blocker` antes de presentar.

## Golden case (F-4)

Para verificar que un refactor no rompe el cálculo, el test
`test_declaracion_service.test_f4_march_2026_golden_case` replica la
declaración de marzo 2026 que Gustavo pagó el 2026-04-18. Los números
exactos:

| Campo | Valor |
|---|---|
| Ingresos | $3,999.00 |
| Tasa | 1.00% |
| ISR mensual | $39.99 |
| ISR retenido por Serviacero | $49.99 |
| ISR a pagar | $0.00 |
| ISR saldo a favor | $10.00 |
| IVA trasladado | $639.84 |
| IVA retenido por Serviacero | $426.56 |
| IVA acreditable | $0.00 |
| IVA a pagar | $213.28 |

Si este test cambia, algo importante cambió en el cálculo — valida con
un contador o revisa la regla.

## Mapeo SAT → backend

Cada campo del portal del SAT tiene un equivalente exacto en la response:

### ISR

| Portal SAT | Campo JSON |
|---|---|
| Total de ingresos efectivamente cobrados | `isr.ingresos` |
| Tasa aplicable | `isr.tasa` (decimal, multiplicar por 100 para %) |
| Impuesto mensual | `isr.impuesto_mensual` |
| ISR retenido por personas morales | `isr.isr_retenido_por_pms` |
| Impuesto a cargo | `isr.impuesto_a_pagar` |
| Impuesto a favor | `isr.saldo_a_favor` |

### IVA

| Portal SAT | Campo JSON |
|---|---|
| Actividades gravadas a la tasa del 16% | `iva.actividades_gravadas_16` |
| IVA a cargo a la tasa del 16% | `iva.iva_trasladado` |
| IVA retenido | `iva.iva_retenido_por_pms` |
| IVA acreditable del periodo | `iva.iva_acreditable` |
| Cantidad a cargo | `iva.impuesto_a_pagar` |
| Impuesto a favor | `iva.saldo_a_favor` |

## Extender este módulo

- Si SAT cambia las tasas RESICO: editar `backend/src/declaracion/tables.py`
  y bumpear `RESICO_PF_TABLE_VERSION`. Mantener la tabla vieja comentada
  por un trimestre para declaraciones extemporáneas.
- Si agregamos nuevos régimenes (PM, general, etc.): el `compute_monthly_declaration`
  debe ramificar por régimen y llamar a la tabla correspondiente.
  Hoy está hardcoded a RESICO PF.
- Si hacemos multi-tenant: el `_OPERATOR_RFC` del router se vuelve un
  parámetro derivado del user/empresa activo.
