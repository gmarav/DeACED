"""Format floats/doubles exactly as Java's ``Double.toString`` / ``Float.toString``.

The reference dumper is Java, so to reproduce its output we must match Java's
notation: decimal form when ``1e-3 <= |x| < 1e7`` and "computerized scientific
notation" (``d.dddEexp``) otherwise, always with at least one fractional digit,
an uppercase ``E`` and no ``+`` on the exponent.

The shortest round-tripping digits are found by formatting with increasing
precision until the value reparses to the identical bit pattern (checked via
:mod:`struct`), which matches the shortest-representation algorithm Java uses
(JDK 19+). Java itself does not emit the shortest digits for the smallest
subnormals (a small cluster near ``Double``/``Float.MIN_VALUE``), so DeACED
diverges from Java there; every value it prints still round-trips exactly.
"""

from __future__ import annotations

import math
import struct


def _shortest_sci(m: float, fmt: str, max_prec: int) -> str:
    """Return Python scientific notation with the fewest digits that round-trips."""
    target = struct.pack(fmt, m)
    for prec in range(max_prec + 1):
        s = f"{m:.{prec}e}"
        try:
            packed = struct.pack(fmt, float(s))
        except OverflowError:
            # rounding pushed the value just past the type's max; try more digits
            continue
        if packed == target:
            return s
    return f"{m:.{max_prec}e}"


def _parts(sci: str) -> tuple[str, int]:
    """Split Python scientific notation into (significant digits, exponent-of-first-digit)."""
    mant, _, exp = sci.partition("e")
    sci_exp = int(exp)
    digits = mant.lstrip("+-").replace(".", "").rstrip("0") or "0"
    return digits, sci_exp


def _format(neg: bool, digits: str, sci_exp: int) -> str:
    sign = "-" if neg else ""
    n = len(digits)
    if -3 <= sci_exp <= 6:
        if sci_exp >= 0:
            int_len = sci_exp + 1
            if n <= int_len:
                int_part = digits + "0" * (int_len - n)
                frac = "0"
            else:
                int_part = digits[:int_len]
                frac = digits[int_len:]
        else:
            int_part = "0"
            frac = "0" * (-sci_exp - 1) + digits
        return f"{sign}{int_part}.{frac}"
    mant = digits + ".0" if n == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mant}E{sci_exp}"


def _to_string(v: float, fmt: str, max_prec: int) -> str:
    if v != v:
        return "NaN"
    if v == math.inf:
        return "Infinity"
    if v == -math.inf:
        return "-Infinity"
    neg = math.copysign(1.0, v) < 0
    if v == 0.0:
        return "-0.0" if neg else "0.0"
    digits, sci_exp = _parts(_shortest_sci(abs(v), fmt, max_prec))
    return _format(neg, digits, sci_exp)


def double_to_string(v: float) -> str:
    """Format ``v`` as Java ``Double.toString`` would."""
    return _to_string(v, ">d", 16)


def float_to_string(v: float) -> str:
    """Format a 32-bit float value ``v`` as Java ``Float.toString`` would."""
    return _to_string(v, ">f", 8)
