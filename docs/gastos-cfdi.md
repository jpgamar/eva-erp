# Gastos — facturas recibidas y IVA acreditable

El módulo `backend/src/facturas_recibidas/` permite subir los CFDIs que
los proveedores nos emiten, para que el IVA trasladado en esos gastos
entre al cálculo de IVA acreditable de la declaración mensual.

Sin este módulo, la declaración calculaba IVA acreditable = $0 cada mes
y pagábamos IVA de más al SAT.

## Flujo del operador

1. **Descargar XMLs del visor SAT** (`https://portalcfdi.facturaelectronica.sat.gob.mx`):
   - Login con RFC + CIEC.
   - Filtro: emitidas por el proveedor, receptor = nosotros, mes deseado.
   - Descargar ZIP con XMLs.
2. **Subir al ERP** en `/gastos`:
   - Drag & drop los XMLs al modal "Subir XMLs".
   - El parser valida: CFDI 3.3/4.0 válido, UUID timbrado, receptor = nuestro RFC.
   - Dedupe automático por UUID — re-subir el mismo batch es seguro.
3. **Categorizar/editar** si aplica:
   - `category`: infrastructure, ai_apis, software_tools, etc.
   - `is_acreditable = false` para gastos mezclados (e.g. gastos personales pagados con la misma tarjeta).
   - `payment_date` para PPD: actualizar cuando realmente pagues (flujo de efectivo).
4. **Ver el total en `/declaracion/{year}/{month}`**: el cálculo de IVA
   acreditable jala automáticamente desde aquí.

## Reglas fiscales (RESICO PF)

IVA es **acreditable** para el receptor sí y sólo si:

- CFDI válido con RFC receptor = nuestro RFC.
- Pagado efectivamente en el mes (flujo de efectivo → `payment_date`).
- Relacionado con la actividad gravada.
- Tipo I (Ingreso). Egresos (E) y Complementos (P) no generan IVA
  acreditable nuevo — ya se contabilizaron en su CFDI padre.

Proveedores extranjeros (Koyeb, Vercel, Supabase, AWS, OpenAI,
Anthropic, Stripe non-MX) **NO emiten CFDI mexicano**. Su IVA pagado no
es acreditable y esos gastos no deben subirse — no hay XML válido.

Proveedores mexicanos típicos que sí emiten CFDI:

- FacturAPI (su suscripción de timbrado)
- Stripe MX (comisiones 3.6% + $3 MXN)
- Telmex / Izzi / CFE (servicios básicos a nombre del RFC)
- Cualquier SaaS mexicano (Contpaq, Aspel, Heru, etc.)

## Parser interno

`backend/src/facturas_recibidas/xml_parser.py`. Pure stdlib (sin lxml).
Soporta CFDI 3.3 y 4.0 detectando namespace. Extrae:

- UUID (del `TimbreFiscalDigital`)
- Emisor (RFC, nombre, régimen)
- Receptor (RFC, nombre, UsoCFDI)
- Fechas (emisión, pago si es PUE)
- Subtotal, total, moneda, tipo de cambio
- Impuestos trasladados (IVA 16%, IEPS) y retenciones
- Tipo de comprobante (I / E / P / N / T)
- Forma y método de pago (PUE / PPD)

Si el XML es inválido o le falta TFD, lanza `CfdiParseError`. El router
convierte esto en `UploadRejected` y lo reporta en el resultado del
batch sin abortar todo el upload.

## Endpoints

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/api/v1/gastos/upload` | multipart XMLs, devuelve `{imported, duplicates, rejected, errors}` |
| `GET`  | `/api/v1/gastos?year=X&month=Y&category=Z&acreditable_only=bool` | lista con filtros |
| `GET`  | `/api/v1/gastos/iva-acreditable?year=X&month=Y` | total IVA del mes + row count |
| `PATCH`| `/api/v1/gastos/{id}` | editar campos operables (category, notes, is_acreditable, payment_date) |

## Storage

- XML completo se guarda en `facturas_recibidas.xml_content` (Text).
  Retención mínima: 6 años (CFF Art 30).
- Volúmenes típicos: <100 CFDIs/mes, <50KB por XML → <5 MB/mes.
  DB storage es más barato que S3 a este volumen.

## Futuro (no en este plan)

- **Descarga masiva vía WebService SAT con e.firma**: automatiza el
  paso 1, gratis, oficial. Requiere certificado e.firma activo y un
  worker SOAP. Nice-to-have cuando el volumen lo justifique.
- **Validación con SAT**: query a
  `https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc`
  para confirmar `sat_status='valid'` por CFDI. Útil para detectar que
  un proveedor canceló un CFDI que ya acreditamos.
