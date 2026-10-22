"""CLI files contain bounded JSON; '-' reads standard input."""
import argparse
import json
import sys
from pathlib import Path

from .core import build_report, export_xosc, generate, validate
from .reporting import render_html


def read_json(path):
    if path == "-":
        text = sys.stdin.read(64_001)
    else:
        with Path(path).open(encoding="utf-8") as stream:
            text = stream.read(64_001)
    if len(text.encode("utf-8")) > 64_000:
        raise ValueError("JSON input exceeds 64000 bytes")
    return json.loads(text)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sek", description="Local-first scenario evidence workbench")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "validate", "export", "report"):
        sub = commands.add_parser(command)
        sub.add_argument("input", nargs="?", default="-", help="JSON file or '-' for standard input")
        sub.add_argument("-o", "--output", help="Output file; defaults to stdout")
        if command == "report":
            sub.add_argument("--html", action="store_true", help="Render standalone HTML")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", choices=["127.0.0.1", "::1", "localhost"], default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            if not 1 <= args.port <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            import uvicorn

            from .api import create_app
            uvicorn.run(create_app(), host=args.host, port=args.port)
            return 0
        payload = read_json(args.input)
        if args.command == "generate":
            if type(payload) is not dict:
                raise ValueError("Generation input must be a JSON object")
            result = generate(**payload)
        elif args.command == "validate":
            result = validate(payload)
        elif args.command == "export":
            result = export_xosc(payload)
        else:
            result = build_report(payload)
            if args.html:
                result = render_html(result)
        output = result if type(result) is str else json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 1 if args.command == "validate" and result["status"] != "PASS" else 0
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f"sek: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
