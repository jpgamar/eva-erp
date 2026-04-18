"""RESICO PF progressive ISR rate table.

Source: LISR Art. 113-E, vigente 2024-2026. If SAT publishes new rates
(typically in the January Resolución Miscelánea Fiscal), update this
table and bump the ``RESICO_PF_TABLE_VERSION`` string so audits can
spot which table was used for a given historical declaración.

Semantics: ``upper_limit`` is the *monthly* ingreso ceiling at which
each rate applies. Values > $3,500,000 MXN/month push the taxpayer
out of RESICO into the general regime — out of scope for this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


RESICO_PF_TABLE_VERSION = "2024-01"


@dataclass(frozen=True)
class ResicoPfBracket:
    upper_limit: Decimal  # inclusive upper bound in MXN, per month
    rate: Decimal  # applied to full ingreso (not marginal — RESICO is
                  # flat-within-bracket, not progressive-per-bracket)


# IMPORTANT: unlike most progressive tables, RESICO PF applies the rate
# to the *entire* ingreso of the month — not just the excess above the
# prior bracket. That's why "1.1%" on $26,000 is $286 (not
# "1.0% on $25,000 + 1.1% on $1,000").
RESICO_PF_MONTHLY_BRACKETS: tuple[ResicoPfBracket, ...] = (
    ResicoPfBracket(upper_limit=Decimal("25000.00"), rate=Decimal("0.0100")),
    ResicoPfBracket(upper_limit=Decimal("50000.00"), rate=Decimal("0.0110")),
    ResicoPfBracket(upper_limit=Decimal("83333.33"), rate=Decimal("0.0150")),
    ResicoPfBracket(upper_limit=Decimal("208333.33"), rate=Decimal("0.0200")),
    ResicoPfBracket(upper_limit=Decimal("3500000.00"), rate=Decimal("0.0250")),
)


def resico_pf_rate_for(ingreso_mensual: Decimal) -> Decimal:
    """Return the ISR rate (e.g. Decimal('0.0100')) for a monthly ingreso.

    Raises ``ValueError`` for ingresos over $3.5M MXN/month — at that
    point RESICO doesn't apply and the caller needs to compute ISR
    under the general regime (LISR Title IV).
    """
    for bracket in RESICO_PF_MONTHLY_BRACKETS:
        if ingreso_mensual <= bracket.upper_limit:
            return bracket.rate
    raise ValueError(
        f"Monthly ingreso {ingreso_mensual} exceeds RESICO PF ceiling "
        f"({RESICO_PF_MONTHLY_BRACKETS[-1].upper_limit}); taxpayer has "
        f"lost RESICO eligibility per LISR Art 113-E."
    )
