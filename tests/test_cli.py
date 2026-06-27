"""Tests for the command-line interface."""

import io
import json
from types import SimpleNamespace

import pytest

from deaced.cli import main

ABCD_HEX = "aced0005740004414243447071007e0000"


def test_hex_to_stdout(capsys):
    assert main(["-x", ABCD_HEX]) == 0
    assert "STREAM_MAGIC - 0xac ed" in capsys.readouterr().out


def test_raw_file(tmp_path, capsys):
    p = tmp_path / "a.ser"
    p.write_bytes(bytes.fromhex(ABCD_HEX))
    assert main(["-r", str(p)]) == 0
    assert "TC_STRING - 0x74" in capsys.readouterr().out


def test_hex_file(tmp_path, capsys):
    p = tmp_path / "a.hex"
    p.write_text(ABCD_HEX)
    assert main(["-f", str(p)]) == 0
    assert "Value - ABCD" in capsys.readouterr().out


def test_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(bytes.fromhex(ABCD_HEX))))
    assert main(["-r", "-"]) == 0
    assert "STREAM_MAGIC" in capsys.readouterr().out


def test_output_file(tmp_path):
    out = tmp_path / "out.txt"
    assert main(["-x", ABCD_HEX, "-o", str(out)]) == 0
    assert "STREAM_MAGIC" in out.read_text(encoding="utf-8")


def test_format_json(capsys):
    assert main(["-x", ABCD_HEX, "-F", "json"]) == 0
    json.loads(capsys.readouterr().out)


def test_format_pretty(capsys):
    assert main(["-x", ABCD_HEX, "-F", "pretty"]) == 0
    assert capsys.readouterr().out.strip()


def test_offsets(capsys):
    assert main(["-x", ABCD_HEX, "--offsets"]) == 0
    assert "@2|STREAM_MAGIC" in capsys.readouterr().out


def test_missing_input_returns_2(capsys):
    assert main(["-r", "definitely_not_a_real_file.ser"]) == 2
    assert "cannot read input" in capsys.readouterr().err


def test_parse_error_returns_1(capsys):
    # valid header, then an illegal content tag
    assert main(["-x", "aced0005ff"]) == 1
    assert "parse error" in capsys.readouterr().err


def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "deaced" in capsys.readouterr().out


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-h"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: deaced" in out
    assert "examples:" in out


def test_offsets_with_json_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-x", ABCD_HEX, "-F", "json", "--offsets"])
    assert exc.value.code == 2
    assert "--offsets is only valid with -F text" in capsys.readouterr().err


def test_main_module_importable():
    import deaced.__main__  # noqa: F401  -- covers the `python -m deaced` entry
