"""Tests for Java-accurate float/double formatting (deaced.jfloat).

Expected strings are what Java 19+ Double.toString / Float.toString produce.
"""

import struct

from deaced.jfloat import double_to_string, float_to_string


def f32(x: float) -> float:
    """Round ``x`` to the nearest 32-bit float value (as a Python float)."""
    return struct.unpack(">f", struct.pack(">f", x))[0]


def test_double_special_values():
    assert double_to_string(0.0) == "0.0"
    assert double_to_string(-0.0) == "-0.0"
    assert double_to_string(float("nan")) == "NaN"
    assert double_to_string(float("inf")) == "Infinity"
    assert double_to_string(float("-inf")) == "-Infinity"


def test_double_decimal_range():
    assert double_to_string(1.0) == "1.0"
    assert double_to_string(100.0) == "100.0"
    assert double_to_string(1000000.0) == "1000000.0"  # 1e6 stays decimal
    assert double_to_string(123.45) == "123.45"
    assert double_to_string(0.001) == "0.001"
    assert double_to_string(0.1) == "0.1"
    assert double_to_string(-2.5) == "-2.5"
    assert double_to_string(1.0 / 3.0) == "0.3333333333333333"


def test_double_scientific_range():
    assert double_to_string(1e7) == "1.0E7"  # boundary -> scientific
    assert double_to_string(1e-4) == "1.0E-4"
    assert double_to_string(1e20) == "1.0E20"
    assert double_to_string(1.5e-10) == "1.5E-10"
    assert double_to_string(1.7976931348623157e308) == "1.7976931348623157E308"


def test_float_values():
    assert float_to_string(f32(0.0)) == "0.0"
    assert float_to_string(f32(-0.0)) == "-0.0"
    assert float_to_string(f32(1.5)) == "1.5"
    assert float_to_string(f32(0.1)) == "0.1"
    assert float_to_string(f32(1e8)) == "1.0E8"
    assert float_to_string(f32(1e-5)) == "1.0E-5"
    assert float_to_string(f32(1.0 / 3.0)) == "0.33333334"
    assert float_to_string(f32(3.4028235e38)) == "3.4028235E38"  # Float.MAX_VALUE
    assert float_to_string(float("nan")) == "NaN"
    assert float_to_string(float("inf")) == "Infinity"


def test_outputs_round_trip():
    # every produced string must parse back to the same value
    for v in [0.1, 123.45, 1e20, 1e-4, 1.0 / 3.0, 1.7976931348623157e308]:
        assert float(double_to_string(v)) == v


def test_smallest_subnormals_diverge_from_java_but_round_trip():
    # Documented limitation (see NOTICE / jfloat docstring): Java's Double/Float
    # .toString does not emit shortest digits for the smallest subnormals, so
    # DeACED -- which always emits shortest round-tripping digits -- diverges
    # there. The values still round-trip exactly.
    d_min = struct.unpack(">d", (1).to_bytes(8, "big"))[0]
    assert double_to_string(d_min) == "5.0E-324"  # Java prints 4.9E-324
    assert float(double_to_string(d_min)) == d_min

    f_min = struct.unpack(">f", (1).to_bytes(4, "big"))[0]
    assert float_to_string(f_min) == "1.0E-45"  # Java prints 1.4E-45
    assert f32(float(float_to_string(f_min))) == f_min
