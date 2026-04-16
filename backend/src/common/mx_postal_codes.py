"""Mexican postal code → state (ISO 3166-2:MX) lookup.

Deterministic first-two-digits mapping derived from SAT's postal code catalog.
We only care about states that levy a cedular tax on professional services;
everything else returns ``None`` (we don't need the state for non-cedular ZIPs).

Used by ``eva_billing.cedular`` to decide whether a customer's ZIP triggers a
state-level retention alongside the federal ISR + IVA retentions.
"""

from __future__ import annotations

# SAT assigns each state a stable range of two-digit ZIP prefixes.
# Only the seven states with a cedular tax on servicios profesionales are
# present below — for all other prefixes ``state_from_zip`` returns ``None``.
_CEDULAR_STATE_PREFIXES: dict[str, str] = {
    # Chihuahua (CHH) — 31xxx, 32xxx, 33xxx
    "31": "CHH", "32": "CHH", "33": "CHH",
    # Guanajuato (GTO) — 36xxx, 37xxx, 38xxx
    "36": "GTO", "37": "GTO", "38": "GTO",
    # Guerrero (GRO) — 39xxx, 40xxx, 41xxx
    "39": "GRO", "40": "GRO", "41": "GRO",
    # Nayarit (NAY) — 63xxx
    "63": "NAY",
    # Oaxaca (OAX) — 68xxx, 69xxx, 70xxx, 71xxx
    "68": "OAX", "69": "OAX", "70": "OAX", "71": "OAX",
    # Quintana Roo (ROO) — 77xxx
    "77": "ROO",
    # Yucatán (YUC) — 97xxx
    "97": "YUC",
}


def state_from_zip(zip_code: str | None) -> str | None:
    """Return ISO state code for a Mexican ZIP, or ``None`` for non-cedular/invalid input.

    >>> state_from_zip("37160")
    'GTO'
    >>> state_from_zip("06600")  # CDMX — no cedular
    >>> state_from_zip(None)
    >>> state_from_zip("abc")
    """
    if not zip_code:
        return None
    # Tolerate whitespace + ensure length and first two chars are digits
    zip_trimmed = zip_code.strip()
    if len(zip_trimmed) < 2 or not zip_trimmed[:2].isdigit():
        return None
    return _CEDULAR_STATE_PREFIXES.get(zip_trimmed[:2])
