#!/usr/bin/env python3
"""Probe unauthenticated external HTTP reachability within a fixed budget."""

import argparse
import ipaddress
import json
import math
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirects as HTTPError so any HTTP response proves reachability."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


def build_unauthenticated_opener():
    """Build a direct opener without proxy, netrc, or authentication handlers."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
        NoRedirectHandler(),
    )


def validate_inputs(url, request_timeout, poll_interval, overall_timeout):
    """Reject unsafe endpoints and invalid timing budgets."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL must use HTTP(S) and include a DNS hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are forbidden")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal URLs are forbidden")
    timings = (request_timeout, poll_interval, overall_timeout)
    if not all(math.isfinite(value) and value > 0 for value in timings):
        raise ValueError("timing values must be finite and positive")
    if overall_timeout < request_timeout:
        raise ValueError("overall timeout must be >= request timeout")


def probe_external(
    url,
    request_timeout,
    poll_interval,
    overall_timeout,
    opener=None,
    clock=time.monotonic,
    sleeper=time.sleep,
):
    """Return reachability, actual HTTP attempts, and monotonic elapsed time."""
    validate_inputs(url, request_timeout, poll_interval, overall_timeout)
    opener = opener or build_unauthenticated_opener()
    started = clock()
    deadline = started + overall_timeout
    attempts = 0

    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return {
                "status": "UNCONFIRMED",
                "attempts": attempts,
                "elapsed_seconds": round(clock() - started, 3),
            }

        attempts += 1
        request = urllib.request.Request(url, method="HEAD")
        attempt_timeout = min(request_timeout, remaining)
        try:
            with opener.open(request, timeout=attempt_timeout):
                pass
            status = "REACHABLE"
        except urllib.error.HTTPError:
            status = "REACHABLE"
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            status = "UNCONFIRMED"
        if status == "REACHABLE":
            return {
                "status": status,
                "attempts": attempts,
                "elapsed_seconds": round(clock() - started, 3),
            }

        remaining = deadline - clock()
        if remaining > 0:
            sleeper(min(poll_interval, remaining))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--request-timeout", required=True, type=float)
    parser.add_argument("--poll-interval", required=True, type=float)
    parser.add_argument("--overall-timeout", required=True, type=float)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = probe_external(
            args.url,
            args.request_timeout,
            args.poll_interval,
            args.overall_timeout,
        )
    except Exception as exc:  # Unexpected helper/configuration failure.
        error = {"status": "ERROR", "error_type": type(exc).__name__}
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
