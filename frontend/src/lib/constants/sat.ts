export const TAX_SYSTEMS: { value: string; label: string }[] = [
  { value: "601", label: "601 - General de Ley PM" },
  { value: "603", label: "603 - Personas Morales sin fines de lucro" },
  { value: "605", label: "605 - Sueldos y Salarios" },
  { value: "606", label: "606 - Arrendamiento" },
  { value: "612", label: "612 - Personas Fisicas con Actividad Empresarial" },
  { value: "616", label: "616 - Sin obligaciones fiscales" },
  { value: "621", label: "621 - Incorporacion Fiscal" },
  { value: "625", label: "625 - Regimen de las Actividades Empresariales (RESICO)" },
  { value: "626", label: "626 - Regimen Simplificado de Confianza" },
];

export const CFDI_USES: { value: string; label: string }[] = [
  { value: "G01", label: "G01 - Adquisicion de mercancias" },
  { value: "G02", label: "G02 - Devoluciones, descuentos o bonificaciones" },
  { value: "G03", label: "G03 - Gastos en general" },
  { value: "I01", label: "I01 - Construcciones" },
  { value: "I02", label: "I02 - Mobiliario y equipo de oficina" },
  { value: "I04", label: "I04 - Equipo de computo y accesorios" },
  { value: "I08", label: "I08 - Otra maquinaria y equipo" },
  { value: "P01", label: "P01 - Por definir" },
  { value: "S01", label: "S01 - Sin efectos fiscales" },
  { value: "CP01", label: "CP01 - Pagos" },
];

export const PAYMENT_FORMS: { value: string; label: string }[] = [
  { value: "01", label: "01 - Efectivo" },
  { value: "02", label: "02 - Cheque nominativo" },
  { value: "03", label: "03 - Transferencia electronica" },
  { value: "04", label: "04 - Tarjeta de credito" },
  { value: "28", label: "28 - Tarjeta de debito" },
  { value: "99", label: "99 - Por definir" },
];
