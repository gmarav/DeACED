"""Command-line interface for DeACED."""

from __future__ import annotations

import argparse
import sys

from . import __version__, dump


def _read_input(args: argparse.Namespace) -> bytes:
    if args.hex is not None:
        return bytes.fromhex("".join(args.hex.split()))
    if args.hex_file is not None:
        with open(args.hex_file, "rb") as f:
            txt = f.read().decode("latin-1")
        return bytes.fromhex("".join(c for c in txt if c in "0123456789abcdefABCDEF"))
    # raw bytes ('-' = stdin)
    if args.raw == "-":
        return sys.stdin.buffer.read()
    with open(args.raw, "rb") as f:
        return f.read()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="deaced",
        description="Dump and inspect Java Object Serialization (0xAC 0xED) streams "
        "and RMI packets in human-readable form.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  deaced -r dump.bin                 dump a raw serialized file\n"
            "  cat dump.bin | deaced -r -         read from stdin\n"
            "  deaced -x aced0005740004414243...  decode hex from the command line\n"
            "  deaced -f hexdump.txt              read a file of hex-ascii bytes\n"
            "  deaced -r dump.bin -F json         emit structured JSON\n"
            "  deaced -r dump.bin -F pretty       emit a compact data tree\n"
            "  deaced -r dump.bin --offsets       annotate each line with its byte offset\n"
            "  deaced -r dump.bin -o out.txt      write the dump to a file"
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "-r", "--raw", metavar="FILE", help="raw binary serialization file ('-' for stdin)"
    )
    src.add_argument(
        "-f", "--hex-file", metavar="FILE", dest="hex_file", help="file of hex-ascii bytes"
    )
    src.add_argument("-x", "--hex", metavar="HEX", help="hex-ascii bytes on the command line")
    p.add_argument("-o", "--output", metavar="FILE", help="write the dump to FILE (default stdout)")
    p.add_argument(
        "-F",
        "--format",
        choices=["text", "json", "pretty"],
        default="text",
        help="output format (default: text)",
    )
    p.add_argument(
        "--offsets",
        action="store_true",
        help="prefix each line with '@<byte-offset>|' (text format only)",
    )
    p.add_argument("-V", "--version", action="version", version=f"deaced {__version__}")
    args = p.parse_args(argv)

    if args.offsets and args.format != "text":
        p.error("--offsets is only valid with -F text")

    try:
        data = _read_input(args)
    except (OSError, ValueError) as e:
        print(f"deaced: cannot read input: {e}", file=sys.stderr)
        return 2

    try:
        text = dump(data, format=args.format, offsets=args.offsets)
    except Exception as e:  # parser errors carry an offset in the message
        print(f"deaced: parse error: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
