# RESICO Personas Físicas — marco fiscal

Referencia autoritativa para cualquier feature que toque facturas,
cobros, gastos, o declaraciones. Si cambias la estructura de cálculo,
verifica contra este documento.

## Régimen

**Régimen Simplificado de Confianza — Personas Físicas (Régimen 626 en SAT).**

Quién aplica: personas físicas con ingresos anuales ≤ $3,500,000 MXN por
actividades empresariales, servicios profesionales, arrendamiento o
plataformas digitales (LISR Arts 113-E a 113-I).

## Base gravable

Pure flujo de efectivo:

- **ISR**: ingresos efectivamente cobrados en el mes. **No hay deducciones.**
  La base es el ingreso bruto.
- **IVA**: IVA trasladado cobrado menos IVA retenido por PMs menos IVA
  acreditable de gastos efectivamente pagados en el mes.

## Tabla ISR RESICO PF (vigente 2024-2026)

Aplicada al **total mensual**, no al excedente:

| Ingreso mensual (hasta) | Tasa ISR |
|---|---|
| $25,000.00         | 1.00% |
| $50,000.00         | 1.10% |
| $83,333.33         | 1.50% |
| $208,333.33        | 2.00% |
| $3,500,000.00      | 2.50% |

Codificada en `backend/src/declaracion/tables.py` con
`RESICO_PF_TABLE_VERSION`. Si SAT publica nuevas tasas (normalmente en
la Resolución Miscelánea Fiscal de enero), actualiza ambos.

## Retenciones que recibe el contribuyente

Cuando una **persona moral** le paga a una PF RESICO:

- **ISR federal**: 1.25% del subtotal (LISR Art 113-J).
- **IVA federal**: 10.6667% del subtotal (= 2/3 × 16%, LIVA Art 1-A).
- **Cedular estatal** (si aplica): depende del estado y régimen del PF.
  Para GTO + RESICO PF: 2% del subtotal (Ley de Hacienda del Estado de
  Guanajuato, Art 37-D). Se emite en el complemento "Impuestos Locales 1.0"
  del CFDI. Código: `backend/src/eva_billing/cedular.py`.

Cuando le paga una **persona física**: cero retenciones.

## Obligaciones

### Declaración mensual

Se presenta a más tardar el **día 17 del mes siguiente** al periodo declarado.
Se hacen **dos declaraciones** en la misma sesión:

1. ISR Simplificado de Confianza
2. IVA Simplificado de Confianza

### CFDIs emitidos

- Al cobrar (PUE) o al emitir (PPD), generar CFDI de Ingreso (tipo I).
- Si PPD → al cobrar cada parcialidad, emitir **Complemento de Pago
  (CFDI tipo P)** a más tardar el **día 5 del mes siguiente al pago**
  (SAT Anexo 20).
- Si hay cobros sin factura → emitir **Factura Global** al público en
  general (RFC `XAXX010101000`) antes del día 17.

### Retención de archivos

6 años mínimo (CFF Art 30). El ERP guarda el XML completo en
`facturas_recibidas.xml_content` para esto.

## IVA acreditable — reglas específicas

Un gasto genera IVA acreditable para RESICO PF **sí y sólo si**:

1. Hay CFDI válido con el RFC del contribuyente como receptor.
2. El gasto fue **efectivamente pagado** en el mes (flujo de efectivo).
3. El gasto está relacionado con la actividad gravada.
4. El CFDI es tipo Ingreso (no egreso ni complemento de pago).

Proveedores **extranjeros** (Koyeb, Vercel, Supabase, AWS, OpenAI, etc.)
**NO emiten CFDI mexicano** → IVA pagado a ellos NO es acreditable.

Proveedores **mexicanos** que sí emiten CFDI: FacturAPI, Stripe MX,
Telmex, Izzi, CFE, software SaaS local. Suben al /gastos del ERP y
entran al cálculo de IVA acreditable del mes.

## Datos fiscales actuales del operador

| Campo | Valor |
|---|---|
| RFC | `ZEPG070314VC1` |
| Régimen fiscal | 626 (RESICO PF) |
| Actividad | Procesamiento electrónico de información, hospedaje de páginas web |
| Dirección fiscal | León, Guanajuato |
| Cedular aplicable | GTO (2%) cuando el cliente también está en GTO |

Hardcoded en:

- `backend/src/eva_billing/service.py:43` (`PROVIDER_REGIME = "resico_pf"`)
- `backend/src/facturas_recibidas/router.py` (`_OPERATOR_RFC`)
- `backend/src/declaracion/router.py` (`_OPERATOR_RFC`)

Si GoEvaAI se incorpora como persona moral → todo el módulo de cálculo
cambia (tasas PM, no RESICO, Art 9 LISR). Migración futura — fuera de
scope de este documento pero ver `docs/plan-eva-erp.md`.
