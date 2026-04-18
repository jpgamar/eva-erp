"""Monthly tax declaration calculator + API.

For RESICO Personas Físicas:
  * ISR = progressive rate (1%–2.5%) on ingresos cobrados. No deductions.
  * IVA = 16% trasladado cobrado − IVA retenido − IVA acreditable
    from gastos with CFDI paid in the month.

See ``docs/declaracion-mensual.md`` for the user-facing walkthrough and
``docs/fiscal-resico-pf.md`` for the legal framework.
"""
