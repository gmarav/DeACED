"""Tests for the JSON and pretty renderers."""

import json
from pathlib import Path

import pytest

from deaced import dump

DATA = Path(__file__).parent / "data"
FIXTURES = sorted(p.stem for p in DATA.glob("*.ser"))

ABCD = bytes.fromhex("aced0005740004414243447071007e0000")


@pytest.mark.parametrize("name", FIXTURES)
def test_json_is_valid_for_every_fixture(name):
    out = dump((DATA / f"{name}.ser").read_bytes(), format="json")
    json.loads(out)  # must be parseable


@pytest.mark.parametrize("name", FIXTURES)
def test_pretty_is_nonempty_for_every_fixture(name):
    out = dump((DATA / f"{name}.ser").read_bytes(), format="pretty")
    assert out.strip()


def test_json_abcd_structure():
    obj = json.loads(dump(ABCD, format="json"))
    assert obj["streamMagicValid"] and obj["streamVersionValid"]
    contents = obj["contents"]
    assert contents[0] == {"type": "string", "handle": 0x7E0000, "value": "ABCD"}
    assert contents[1] is None  # TC_NULL
    assert contents[2] == {"type": "reference", "handle": 0x7E0000}


def test_json_prims_fields():
    obj = json.loads(dump((DATA / "prims.ser").read_bytes(), format="json"))
    o = obj["contents"][0]
    assert o["type"] == "object" and o["class"] == "Prims"
    fields = o["classData"][-1]["fields"]
    assert fields["b"] == -5
    assert fields["i"] == 1000000
    assert fields["l"] == -1
    assert fields["flag"] is True
    assert fields["d"] == 123.45
    assert fields["c"] == "Q"
    assert fields["name"] == {"type": "string", "handle": 0x7E0003, "value": "hello"}


def test_pretty_prims_contains_fields():
    out = dump((DATA / "prims.ser").read_bytes(), format="pretty")
    assert "Prims #2" in out  # object handle (relative)
    assert "b = -5" in out
    assert "d = 123.45" in out
    assert "flag = true" in out
    assert "c = 'Q'" in out
    assert 'name = "hello"' in out


def test_unknown_format_rejected():
    with pytest.raises(ValueError):
        dump(ABCD, format="xml")


# --- JSON renderer coverage for the less-common node types ---


def test_json_rmi_and_reset():
    obj = json.loads(dump(bytes.fromhex("51aced000579"), format="json"))
    assert obj["rmi"] == 0x51
    assert obj["contents"][0] == {"type": "reset"}


def test_json_exception():
    obj = json.loads(dump(bytes.fromhex("aced00057b74000158"), format="json"))
    exc = obj["contents"][0]
    assert exc["type"] == "exception"
    assert exc["throwable"]["value"] == "X"


def test_json_blockdatalong():
    obj = json.loads(dump(bytes.fromhex("aced00057a00000003414243"), format="json"))
    bd = obj["contents"][0]
    assert bd == {"type": "blockData", "hex": "414243", "long": True}


def test_json_proxy_object():
    obj = json.loads(dump((DATA / "proxy.ser").read_bytes(), format="json"))
    assert obj["contents"][0]["class"] == "<Dynamic Proxy Class>"


# --- pretty renderer coverage for exception / block data ---


def test_pretty_exception_and_blockdata():
    assert "exception" in dump(bytes.fromhex("aced00057b74000158"), format="pretty")
    out = dump(bytes.fromhex("aced00057a00000003414243"), format="pretty")
    assert "blockData(3 bytes)" in out


def test_long_field_label_is_spec_correct_j():
    # Deliberate divergence from NickstaDB upstream's "Long - L" typo: 'J' is the
    # JVM type code for long (JVMS 4.3.2); matches the patched reference jar.
    out = dump((DATA / "prims.ser").read_bytes())
    assert "Long - J - 0x4a" in out
    assert "Long - L" not in out


def test_json_class_object():
    obj = json.loads(dump((DATA / "classobj.ser").read_bytes(), format="json"))
    co = obj["contents"][0]
    assert co["type"] == "class"
    assert co["classDesc"]["name"] == "java.lang.String"


def test_json_class_of_proxy_desc():
    # A TC_CLASS whose classDesc is a TC_PROXYCLASSDESC -> exercises _desc(proxy).
    data = "aced0005767d000000007870"
    co = json.loads(dump(bytes.fromhex(data), format="json"))["contents"][0]
    assert co["type"] == "class"
    assert co["classDesc"] == {"proxy": True, "interfaces": [], "annotations": [], "super": None}


def test_json_classdesc_field_with_class_name():
    # TC_CLASS with a classDesc declaring one 'L' field -> exercises _field_desc's
    # className branch in the JSON renderer.
    data = "aced000576720001410000000000000000020001"
    data += "4c0001787400054c466f6f3b7870"
    co = json.loads(dump(bytes.fromhex(data), format="json"))["contents"][0]
    field = co["classDesc"]["fields"][0]
    assert field["name"] == "x" and field["type"] == "L"
    assert field["className"] == {"type": "string", "handle": 0x7E0001, "value": "LFoo;"}
