#!/usr/bin/python
"""Persist observations independently of publication."""
import uuid
import copy
from pathlib import Path
from datetime import datetime

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.storage_files import locked, read_json, save_json, atomic, REPORT_ID, report_path
from ansible.module_utils.storage_monthly import JST, build_report, markdown, short_summary


def freeze_devices(baseline, reports):
    """Fill missing device baselines, never replace a device already frozen."""
    for previous in sorted(reports, key=lambda r: r['collected_at'], reverse=True):
        for host, entry in previous['hosts'].items():
            target = baseline['hosts'].setdefault(host, {'devices': []})
            known = {d['id'] for d in target['devices']}
            for device in entry['devices']:
                if device['id'] not in known:
                    item = copy.deepcopy(device)
                    item['comparison_source'] = {k: previous[k] for k in ('report_id', 'collected_at')}
                    target['devices'].append(item)
                    known.add(item['id'])


def prune(root, history, month):
    """Only remove published history older than 13 months, preserving all baselines."""
    protected = set()
    for path in root.glob('*.baseline.json'):
        baseline = read_json(path)
        for host in baseline['hosts'].values():
            protected.update(d.get('comparison_source', {}).get('report_id') for d in host['devices'])
    year, number = map(int, month.split('-'))
    cutoff = year * 12 + number - 13
    for previous in history:
        old_year, old_month = map(int, previous['month'].split('-'))
        report_id = previous['report_id']
        receipt = root / (report_id + '.published.json')
        if old_year * 12 + old_month >= cutoff or report_id in protected or not receipt.is_file():
            continue
        if read_json(receipt).get('report_id') != report_id:
            continue
        paths = [root / (report_id + suffix) for suffix in ('.json', '.md', '.published.json')]
        if any(p.is_symlink() or not p.is_file() for p in paths):
            continue
        for path in paths:
            path.unlink()


def archive(directory, observations, thresholds):
    with locked(directory) as root:
        now = datetime.now(JST)
        month = now.strftime("%Y-%m")
        report_id = now.strftime("%Y%m%dT%H%M%S%f%z") + "-" + uuid.uuid4().hex
        history, corrupt = [], False
        for path in root.glob("*.json"):
            if not REPORT_ID.fullmatch(path.stem):
                continue
            try:
                previous = read_json(path)
                if previous["schema_version"] != 1 or previous["report_id"] != path.stem:
                    raise ValueError("bad history schema")
                datetime.fromisoformat(previous["collected_at"])
                if not isinstance(previous["hosts"], dict) or previous['collection'] not in ('ok', 'error'):
                    raise ValueError("bad history hosts")
                for entry in previous['hosts'].values():
                    for device in entry['devices']:
                        if not isinstance(device['id'], str) or not isinstance(device['values'], dict):
                            raise ValueError('bad historical device')
                history.append(previous)
            except (ValueError, KeyError, TypeError, OSError):
                corrupt = True
        state_path = root / (month + ".baseline.json")
        if state_path.exists() or state_path.is_symlink():
            # A broken fixed baseline must never be silently replaced.
            try:
                baseline = read_json(state_path)
                if baseline["schema_version"] != 1 or not isinstance(baseline["hosts"], dict):
                    raise ValueError("bad baseline")
            except (ValueError, KeyError, TypeError, OSError):
                baseline, corrupt = None, True
        else:
            baseline = {'schema_version': 1, 'report_id': 'monthly-baseline-' + month,
                        'collected_at': now.isoformat(), 'hosts': {}}
            freeze_devices(baseline, [r for r in history if r['month'] < month])
        report = build_report(observations, report_id, now.isoformat(), baseline,
                              history_error=corrupt, **thresholds)
        save_json(root / (report_id + ".json"), report)
        body = markdown(report)
        atomic(root / (report_id + ".md"), body)
        if baseline is not None and not corrupt:
            freeze_devices(baseline, [report])
            save_json(state_path, baseline)
            # A failed retention check leaves the saved report intact and fails the module.
            prune(root, history, month)
        return report, body


def main():
    module = AnsibleModule(argument_spec={
        "directory": {"type": "path", "required": True},
        "observations": {"type": "dict", "required": True},
        "thresholds": {"type": "dict", "default": {}},
        "operation": {"type": "str", "choices": ['collect', 'replay'], "default": 'collect'},
        "report_id": {"type": "str", "default": ''},
    }, supports_check_mode=True)
    try:
        if module.params['operation'] == 'replay':
            root = Path(module.params['directory']).absolute()
            if any(p.is_symlink() for p in (root, *root.parents)):
                raise ValueError('unsafe replay directory')
            report = read_json(report_path(root, module.params['report_id']))
            if report['schema_version'] != 1 or report['report_id'] != module.params['report_id']:
                raise ValueError('invalid replay schema')
            module.exit_json(changed=False, report=report, body=markdown(report), summary=short_summary(report))
        if module.check_mode:
            report = build_report(module.params["observations"], "check-preview", datetime.now(JST).isoformat(),
                                  **module.params["thresholds"])
            module.exit_json(changed=False, report=report, body=markdown(report), summary=short_summary(report))
        report, body = archive(module.params["directory"], module.params["observations"], module.params["thresholds"])
        module.exit_json(changed=True, report=report, body=body, summary=short_summary(report))
    except (OSError, ValueError, KeyError, TypeError):
        module.fail_json(msg="Storage report archive failed; inspect local storage and schema")


if __name__ == "__main__":
    main()
