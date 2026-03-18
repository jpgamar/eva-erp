# Propuesta: Control de Anticipos y Tipo de Cambio

## El problema actual

Hoy, cuando haces una compra en dolares, el ERP convierte todo a pesos al momento de registrarlo y se pierde el rastro del tipo de cambio que se uso. Esto causa tres problemas concretos:

1. **Anticipos sin control** — Cuando das un anticipo en dolares, no queda registrado a que tipo de cambio se pago. Al llegar la factura (dias o semanas despues, con otro tipo de cambio), no hay forma de saber cuanto ganaste o perdiste por la diferencia cambiaria.

2. **No sabes cuanto ganas o pierdes por tipo de cambio** — Si pagaste a 17.50 y la factura llego a 18.00, esa diferencia es dinero real que hoy no se esta rastreando.

3. **Todo se mezcla** — Los anticipos, los pagos parciales y los pagos completos se registran igual, sin distinguir que tipo de cambio aplico a cada uno.

---

## Que se va a agregar

### 1. Registro de anticipos

Un nuevo apartado donde puedes registrar un anticipo y el sistema automaticamente guarda:
- A que proveedor se le pago
- Cuanto se pago en dolares
- El tipo de cambio del dia que se pago
- El equivalente en pesos de ese dia

**Ejemplo:** Das un anticipo de $5,000 USD el 1 de marzo cuando el dolar esta a $17.50. El sistema registra: $5,000 USD = $87,500 MXN a tipo de cambio 17.50.

### 2. Aplicacion del anticipo a la factura

Cuando llega la factura del proveedor, aplicas el anticipo contra ella. El sistema calcula automaticamente:
- Cuanto del anticipo se aplica (al tipo de cambio original del anticipo)
- Cuanto queda pendiente de pago (al tipo de cambio del dia de la factura)
- La diferencia cambiaria generada

**Ejemplo:** Llega la factura por $20,000 USD el 15 de marzo, cuando el dolar esta a $18.00.

| Concepto | USD | Tipo de cambio | MXN |
|---|---|---|---|
| Anticipo aplicado | $5,000 | 17.50 (el del dia que se pago) | $87,500 |
| Saldo pendiente | $15,000 | 18.00 (el de hoy) | $270,000 |
| **Total factura** | **$20,000** | | **$357,500** |

### 3. Diferencias cambiarias automaticas

Cada vez que se hace un pago, el sistema calcula si hubo ganancia o perdida por tipo de cambio y lo muestra claramente.

**Ejemplo:** Pagas los $15,000 USD pendientes el 30 de marzo, cuando el dolar esta a $17.80.

- La factura registro esos $15,000 a $18.00 = $270,000 MXN
- Pero pagaste a $17.80 = $267,000 MXN
- **Ganancia cambiaria: $3,000 MXN** (pagaste menos pesos de lo que decias)

El sistema te muestra un resumen de cuanto has ganado o perdido por diferencias cambiarias en el periodo que quieras.

### 4. Tipo de cambio automatico

El sistema obtiene automaticamente el tipo de cambio oficial (FIX de Banxico) todos los dias, para que no tengas que buscarlo ni capturarlo manualmente. Tambien puedes poner un tipo de cambio manual si necesitas usar uno diferente para alguna operacion.

---

## Como se ve en el dia a dia

**Cuando das un anticipo:**
1. Vas al modulo de anticipos
2. Seleccionas el proveedor, pones el monto en dolares
3. El sistema jala el tipo de cambio del dia automaticamente
4. Guardas y listo — queda registrado con su tipo de cambio fijo

**Cuando llega la factura:**
1. Registras la factura del proveedor
2. Seleccionas que anticipos quieres aplicar
3. El sistema te muestra el desglose: cuanto del anticipo (a su tipo de cambio original) y cuanto queda pendiente (al tipo de cambio de hoy)

**Cuando pagas:**
1. Registras el pago
2. El sistema compara el tipo de cambio de la factura vs el del pago
3. Te muestra si hubo ganancia o perdida cambiaria

**En cualquier momento:**
- Puedes ver un reporte de todas tus diferencias cambiarias del mes/trimestre/anio
- Puedes ver los anticipos pendientes de aplicar y en que tipo de cambio estan

---

## Que NO cambia

- La forma en que facturas a tus clientes sigue igual
- Los gastos y egresos que ya estan registrados no se modifican
- El flujo de facturacion CFDI no se altera
- Todo lo que ya funciona en el ERP sigue funcionando exactamente igual

---

## Resumen

| Hoy | Con esta mejora |
|---|---|
| Todo se convierte a pesos y se pierde el tipo de cambio | Cada operacion guarda su tipo de cambio |
| No hay control de anticipos en dolares | Anticipos registrados con tipo de cambio fijo |
| No se sabe cuanto se gana/pierde por tipo de cambio | Reporte automatico de diferencias cambiarias |
| Hay que buscar el tipo de cambio manualmente | El sistema lo obtiene automaticamente de Banxico |
