#!/usr/bin/env python3
"""Prune stale `ufw` allow rules for a single TCP port, keeping only the
rule whose source matches the currently resolved address.

Used by roles/agmsg_server/tasks/firewall.yml (R2 / AC2). The role resolves
the `quory` hostname to an IPv4 address at every run (ufw does not resolve
hostnames itself) and only ever *adds* a rule for the freshly resolved
address. If that address ever changes, a script that only adds rules would
leave the old address allowed forever -- this one removes any rule for the
same port whose source does not match the current resolution.

Two failure classes this script exists to make loud instead of silent
(2026-08-16, independent review round 3):

1. **ufw itself not enforcing anything.** If `ufw` is inactive, or its
   default incoming policy is not `deny`, then adding or pruning an
   "allow from <ip>" rule is theater -- the port stays reachable from
   anywhere regardless of what this script does. Refuses to proceed past
   this point (exit 5).
2. **A `ufw status numbered` line for the target port that this script
   does not recognize.** Treating "could not parse this" the same as
   "nothing to prune" would let an unrecognized -- possibly genuinely
   stale, possibly IPv6, possibly a different action/direction entirely
   -- rule sit unnoticed while the script still reports success. Any such
   line is a hard failure (exit 3), never folded into "0 stale".

Usage: prune-stale-ufw-rule.py <port> <keep_ip>
Prints the source address of each deleted rule (one per line) to stdout.
Finding zero stale rules is success, not an error -- this script only
fails on the two conditions above, an unexpected `ufw` invocation error,
or a delete that `ufw` itself refuses (exit 4).

Deletion is by rule *specification* (`ufw delete allow from <ip> to any
port <port> proto tcp`), not by the bracketed number `ufw status numbered`
prints. Numbers shift if anything else changes the ruleset between reading
the snapshot and issuing the delete (round3 Suggestion, TOCTOU); the
specification does not depend on position and cannot be shifted out from
under a concurrent change the way a number can.
"""
import argparse
import re
import subprocess
import sys

UFW = "/usr/sbin/ufw"


def ufw_status_verbose():
    return subprocess.run(
        [UFW, "status", "verbose"], check=True, capture_output=True, text=True
    ).stdout


def ufw_status_numbered():
    return subprocess.run(
        [UFW, "status", "numbered"], check=True, capture_output=True, text=True
    ).stdout


def is_active_default_deny(status_verbose_text):
    """True only if ufw is active AND its default incoming policy is deny.

    Anything else means an "allow from <ip>" rule this script manages
    restricts nothing: either nothing is enforced at all (inactive), or
    everything is already allowed by default regardless of this rule.
    """
    active = re.search(r"(?m)^Status:\s*active\s*$", status_verbose_text) is not None
    default_deny_incoming = (
        re.search(r"(?m)^Default:\s*deny\s*\(incoming\)", status_verbose_text)
        is not None
    )
    return active and default_deny_incoming


def _candidate_pattern(port):
    # Any numbered rule that mentions this port at all, in any shape ufw
    # might print it (including the "(v6)" family, or a direction/action
    # this script was not written for) -- broad on purpose, so nothing
    # for this port can silently fall outside of what gets classified.
    return re.compile(r"^\[\s*\d+\]\s+" + re.escape(port) + r"/")


def _strict_pattern(port):
    # The one exact shape this script knows how to act on: a plain IPv4
    # ALLOW IN rule for this TCP port, nothing else appended beyond an
    # optional trailing comment.
    return re.compile(
        r"^\[\s*\d+\]\s+" + re.escape(port) + r"/tcp\s+ALLOW IN\s+(?P<src>\S+)\s*(?:#.*)?$"
    )


def classify(status_numbered_text, port, keep_ip):
    """Split the numbered rule table into (stale_sources, unrecognized_lines).

    stale_sources: source IPs of recognized ALLOW IN rules for `port`
        whose source is not `keep_ip` -- safe to delete by specification.
    unrecognized_lines: raw lines that mention `port` but do not match
        the one recognized shape. Non-empty means "cannot classify",
        which the caller must treat as a hard failure -- never silently
        folded into "0 stale, nothing to do".
    """
    candidate = _candidate_pattern(port)
    strict = _strict_pattern(port)
    stale = []
    unrecognized = []
    for line in status_numbered_text.splitlines():
        if not candidate.match(line):
            continue
        m = strict.match(line)
        if not m:
            unrecognized.append(line)
            continue
        src = m.group("src")
        if src != keep_ip:
            stale.append(src)
    return stale, unrecognized


def delete_by_spec(src, port):
    """Delete a single `allow from <src> to any port <port> proto tcp` rule
    by specification. Raises subprocess.CalledProcessError if `ufw`
    refuses (e.g. the rule no longer exists -- a concurrent change already
    removed it)."""
    subprocess.run(
        [UFW, "--force", "delete", "allow", "from", src, "to", "any", "port", port, "proto", "tcp"],
        check=True,
        capture_output=True,
        text=True,
    )


def perform_prune(stale, port, delete=None):
    """Delete every source in `stale` by specification. Returns
    (deleted, failures) -- failures is a list of (src, error message)
    for deletes `ufw` itself refused; a failure never raises past this
    function so a partial failure still reports every source it did and
    did not manage to remove, instead of stopping partway with no record
    of what succeeded.

    `delete` defaults to None and is resolved to the module-level
    `delete_by_spec` inside the function body (not as a parameter default)
    so that tests can monkeypatch the module attribute and have callers
    that do not pass `delete` explicitly -- including main() -- observe
    the replacement. A parameter default binds to the function object
    that exists at definition time and would not see a later
    reassignment."""
    if delete is None:
        delete = delete_by_spec
    deleted = []
    failures = []
    for src in stale:
        try:
            delete(src, port)
            deleted.append(src)
        except subprocess.CalledProcessError as exc:
            failures.append((src, (exc.stderr or str(exc)).strip()))
    return deleted, failures


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("keep_ip")
    args = parser.parse_args(argv)

    if not is_active_default_deny(ufw_status_verbose()):
        print(
            "prune-stale-ufw-rule.py: ufw is not active with a default-deny "
            "incoming policy -- refusing to manage rules for port {} (an "
            "allow rule would restrict nothing).".format(args.port),
            file=sys.stderr,
        )
        return 5

    stale, unrecognized = classify(ufw_status_numbered(), args.port, args.keep_ip)

    if unrecognized:
        print(
            "prune-stale-ufw-rule.py: found rule(s) for port {} that do not "
            "match the expected `ufw status numbered` shape -- refusing to "
            "guess whether they are stale. Resolve manually:\n{}".format(
                args.port, "\n".join(unrecognized)
            ),
            file=sys.stderr,
        )
        return 3

    deleted, failures = perform_prune(stale, args.port)
    for src in deleted:
        print(src)

    if failures:
        print(
            "prune-stale-ufw-rule.py: failed to delete rule(s) for: {}".format(failures),
            file=sys.stderr,
        )
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
