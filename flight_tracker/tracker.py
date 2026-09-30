#!/usr/bin/env python3
"""MEL -> ELS flight price tracker.

  python tracker.py run [--dry-run] [--fixtures FILE]
  python tracker.py report [--html FILE]
  python tracker.py probe
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from fttracker.config import load_settings
from fttracker.report import to_html, to_text
from fttracker.runner import open_storage, run


def setup_logging(settings, verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_path = settings.paths.get("app_log")
    if log_path and not settings.env.get("VERCEL"):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def cmd_run(args, settings) -> int:
    report = run(settings, dry_run=args.dry_run, fixtures=Path(args.fixtures) if args.fixtures else None)
    if report.get("status") == "stopped":
        print(report["decision"]["reason"])
        return 0
    print(to_text(report))
    if args.dry_run:
        print("\n(dry run – nothing was saved)")
    return 1 if report["status"] == "failed" else 0


def cmd_report(args, settings) -> int:
    storage = open_storage(settings)
    try:
        report = storage.latest_report()
        if args.html:
            Path(args.html).write_text(to_html(report, storage.recent_runs(30), storage.log_lines(60)))
            print(f"wrote {args.html}")
            return 0
    finally:
        storage.close()
    if report is None:
        print("No runs yet – try `python tracker.py run`.")
        return 1
    print(to_text(report))
    return 0


def cmd_probe(args, settings) -> int:
    """One Ignav call on the primary dates, to check the response shape against the parser."""
    from fttracker.providers.ignav import IgnavProvider
    stored: dict = {}

    def keep(label, payload):
        stored[label] = payload
        return label

    p = IgnavProvider(settings, keep)
    ok, why = p.is_configured()
    if not ok:
        print(f"Ignav not configured: {why}")
        return 1
    res = p.search(settings.trip.date_pairs()[:1])
    out = Path("data/probe_ignav.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stored, indent=2, default=str))
    print(f"raw response saved to {out}")
    print(f"parsed {len(res.itineraries)} itineraries; problems: {res.errors or 'none'}")
    for it in res.itineraries[:3]:
        print(f"  AUD {it.price:,.0f}  {'-'.join(it.outbound.airports)} / {'-'.join(it.inbound.airports)}  "
              f"{it.outbound.hours:.1f}h / {it.inbound.hours:.1f}h  single_ticket={it.single_ticket}")
    return 0 if res.ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--config", help="path to config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="search, decide, store and print today's analysis")
    r.add_argument("--dry-run", action="store_true", help="search and print, but save nothing")
    r.add_argument("--fixtures", help="replay an Ignav-shaped JSON file instead of calling APIs (testing only)")
    rp = sub.add_parser("report", help="print the latest stored analysis (no API calls)")
    rp.add_argument("--html", help="write the dashboard HTML to this file")
    sub.add_parser("probe", help="one Ignav call to check the response format")
    args = ap.parse_args(argv)

    settings = load_settings(Path(args.config) if args.config else None)
    setup_logging(settings, args.verbose)
    return {"run": cmd_run, "report": cmd_report, "probe": cmd_probe}[args.cmd](args, settings)


if __name__ == "__main__":
    sys.exit(main())
