"""Cedular tax (local retention) rules per Mexican state.

When a **RESICO persona física** (Gustavo/EvaAI) invoices a **persona moral**
domiciled in the same state, the state may require an additional retention
on top of the two federal ones (ISR 1.25% + IVA 2/3). The classic example
is Guanajuato's Art. 37-D LHEG (2% for RESICO-PF → PM).

Rate matrix by state (verified where possible, ``None`` = pending legal review):

+-------+-----------------+----------------+----------------------+
| State | General rate PF | RESICO-PF rate | Legal article        |
+=======+=================+================+======================+
| GTO   | 5%              | 2% ✓ verified  | Art. 37-D LHEG       |
| CHH   | 5%              | None           | LH Chihuahua         |
| GRO   | 5%              | None           | LH Guerrero          |
| NAY   | 3%              | None           | LH Nayarit           |
| OAX   | 5%              | None           | LH Oaxaca            |
| ROO   | 5%              | None           | LH Quintana Roo      |
| YUC   | 5%              | None           | LH Yucatán           |
+-------+-----------------+----------------+----------------------+

``None`` means "state taxes cedular on services but we haven't verified the
specific RESICO rate with a tax professional yet" — ``resolve_cedular``
returns ``None`` for those, so no retention is applied automatically. To
enable a state, fill ``rate_resico_pf`` after confirming with the state's
Ley de Hacienda.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.common.mx_postal_codes import state_from_zip


@dataclass(frozen=True)
class CedularRule:
    state_code: str
    label: str
    rate_resico_pf: Decimal | None
    rate_general_pf: Decimal | None
    legal_article: str
    # Facturapi's ``local_taxes`` entries use ``type`` as a free-form string
    # that flows into the CFDI's ``implocal:ImpLocRetenido`` attribute. We
    # standardize it per state for readability on the printed PDF.
    facturapi_type: str


CEDULAR_RULES: dict[str, CedularRule] = {
    "GTO": CedularRule(
        state_code="GTO",
        label="Guanajuato",
        rate_resico_pf=Decimal("0.02"),
        rate_general_pf=Decimal("0.05"),
        legal_article="Art. 37-D LHEG",
        facturapi_type="Cedular GTO",
    ),
    "CHH": CedularRule(
        state_code="CHH",
        label="Chihuahua",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.05"),
        legal_article="LH Chihuahua",
        facturapi_type="Cedular CHH",
    ),
    "GRO": CedularRule(
        state_code="GRO",
        label="Guerrero",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.05"),
        legal_article="LH Guerrero",
        facturapi_type="Cedular GRO",
    ),
    "NAY": CedularRule(
        state_code="NAY",
        label="Nayarit",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.03"),
        legal_article="LH Nayarit",
        facturapi_type="Cedular NAY",
    ),
    "OAX": CedularRule(
        state_code="OAX",
        label="Oaxaca",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.05"),
        legal_article="LH Oaxaca",
        facturapi_type="Cedular OAX",
    ),
    "ROO": CedularRule(
        state_code="ROO",
        label="Quintana Roo",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.05"),
        legal_article="LH Quintana Roo",
        facturapi_type="Cedular ROO",
    ),
    "YUC": CedularRule(
        state_code="YUC",
        label="Yucatán",
        rate_resico_pf=None,
        rate_general_pf=Decimal("0.05"),
        legal_article="LH Yucatán",
        facturapi_type="Cedular YUC",
    ),
}

ProviderRegime = str  # "resico_pf" | "general_pf" | other (future)


def resolve_cedular(customer_zip: str | None, provider_regime: ProviderRegime) -> CedularRule | None:
    """Return the active cedular rule for a (customer_zip, provider_regime) pair, else None.

    Returns ``None`` when:
      * the ZIP isn't in a cedular state,
      * the state's rate for the given provider regime hasn't been verified yet,
      * the provider regime is unknown.
    """
    state = state_from_zip(customer_zip)
    if not state:
        return None
    rule = CEDULAR_RULES.get(state)
    if rule is None:
        return None
    rate = cedular_rate(rule, provider_regime)
    return rule if rate is not None else None


def cedular_rate(rule: CedularRule, provider_regime: ProviderRegime) -> Decimal | None:
    """Return the verified rate for a rule + regime, or None if not enabled."""
    if provider_regime == "resico_pf":
        return rule.rate_resico_pf
    if provider_regime == "general_pf":
        return rule.rate_general_pf
    return None
