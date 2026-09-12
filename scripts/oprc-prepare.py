#!/usr/bin/env python3
"""Build or validate an OPREQ locally; never submit or print its body."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / 'roles/operator_request_channel/files'
sys.path.insert(0, str(LIB))
from oprc import dlp, ids, schema  # noqa: E402


class DlpBlocked(Exception):
    """Contains only rule IDs and JSON pointers, never matched values."""


def validate(raw):
    if not isinstance(raw, dict) or raw.get('type') != 'OPREQ':
        raise ValueError('type must be OPREQ')
    schema.reject_server_assigned_fields(raw)
    candidate = dict(raw)
    candidate.update(conversation_id=ids.generate_conversation_id(),
                     request_id=ids.generate_request_id(), source='coordinator')
    # Stored-envelope fields are validation-only; the receiving server assigns them.
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M:%S%z')
    candidate['created_at'] = stamp
    candidate.setdefault('expires_at', stamp)
    schema.validate(candidate, json.loads((LIB / 'request-schema-v1.json').read_text()))
    schema.validate_local_relationships(candidate)
    result = dlp.scan(raw, dlp.load_ruleset(str(LIB / 'dlp-rules.json')), 5)
    if result.blocked:
        raise DlpBlocked('DLP: ' + ', '.join(f.rule_id + ' at ' + f.pointer for f in result.findings))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON containing request content')
    parser.add_argument('--output', type=Path, help='Create a new OPREQ file; refuses overwrite')
    args = parser.parse_args()
    try:
        raw = json.loads(args.input.read_text())
        if args.output:
            if not isinstance(raw, dict):
                raise ValueError('request must be an object')
            raw.setdefault('schema_version', 1)
            raw.setdefault('type', 'OPREQ')
        validate(raw)
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(raw, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        print('OPREQ schema/DLP: PASS')
        return 0
    except DlpBlocked as exc:
        print(str(exc), file=sys.stderr)
    except schema.ValidationError as exc:
        print('OPREQ schema invalid: ' + str(len(exc.errors)) + ' field(s)', file=sys.stderr)
    except (OSError, ValueError, dlp.DlpError) as exc:
        # JSON decoding and OS errors can contain input snippets or sensitive paths.
        print('OPREQ preparation failed: ' + type(exc).__name__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
