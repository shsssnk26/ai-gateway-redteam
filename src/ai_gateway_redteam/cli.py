import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ai_gateway_redteam.catalog.build import build_cases
from ai_gateway_redteam.common.errors import RedteamError
from ai_gateway_redteam.execution.runner import DEFAULT_TIMEOUT, run_all
from ai_gateway_redteam.execution.target import Target
from ai_gateway_redteam.grading.graders import CaseGrader
from ai_gateway_redteam.grading.results import Verdict
from ai_gateway_redteam.reporting.report import Report
from ai_gateway_redteam.reporting.reporters import JsonReporter, Reporter, TextReporter

API_KEY_ENV = "AIGW_REDTEAM_API_KEY"

# 0: every case passed. 1: something leaked or was reachable. 2: something proved nothing, or the run could not start.
EXIT_CODES: dict[Verdict, int] = {"PASS": 0, "FAIL": 1, "ERROR": 2}
EXIT_BAD_INPUT = 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aigw-redteam",
        description="Run attack cases against an AI gateway and grade what comes back.",
        epilog=f"The gateway API key for chat cases is read from {API_KEY_ENV}, never from a flag.",
    )
    parser.add_argument("cases", help="YAML file or folder of attack cases")
    parser.add_argument("--target", required=True, help="gateway base URL, e.g. http://10.0.0.5:4000")
    parser.add_argument("--model-host", help="host the models run on (default: the gateway's host)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per request")
    parser.add_argument("--json", type=Path, metavar="PATH", help="also write the report as JSON to PATH")
    parser.add_argument("-v", "--verbose", action="store_true", help="show the reason for passing checks too")
    return parser.parse_args(argv)


def build_target(args: argparse.Namespace) -> Target:
    """The target comes from flags and the environment, never from case files"""
    gateway_url = args.target.rstrip("/")
    host = urlsplit(gateway_url).hostname
    if not host:
        raise RedteamError(f"--target {args.target} is not a URL with a host")
    return Target(gateway_url, args.model_host or host, os.environ.get(API_KEY_ENV) or None)


def build_reporters(args: argparse.Namespace) -> list[Reporter]:
    reporters: list[Reporter] = [TextReporter(sys.stdout, args.verbose)]
    if args.json is not None:
        reporters.append(JsonReporter(args.json))
    return reporters


def main(argv: list[str] | None = None, transport: httpx.BaseTransport | None = None) -> int:
    """Build, run, grade and report. transport replaces the network, so tests can pass a MockTransport."""
    args = parse_args(argv)
    try:
        target = build_target(args)
        cases = build_cases(args.cases)
        observations = run_all(cases, target, args.timeout, transport)
    except RedteamError as error:
        print(f"aigw-redteam: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    report = Report.from_results(target.gateway_url, cases, CaseGrader().grade_all(cases, observations))
    try:
        for reporter in build_reporters(args):
            reporter.write(report)
    except OSError as error:
        print(f"aigw-redteam: could not write report: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    return EXIT_CODES[report.verdict()]


if __name__ == "__main__":
    sys.exit(main())
