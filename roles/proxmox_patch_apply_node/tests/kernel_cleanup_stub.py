#!/usr/bin/python3
"""Local package-state sensor and package-manager doubles (no host commands)."""
import atexit
import base64
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parent
config = json.loads((root / 'scenario.json').read_text())
kind = Path(sys.argv[0]).name
args = sys.argv[1:]
state = root / 'packages'
with (root / 'calls').open('a') as stream:
    stream.write(kind + ' ' + ' '.join(args) + '\n')
packages = state.read_text()
post = (root / 'started').exists()
mode = config['mode']
if kind == 'collect':
    if mode == 'bad_json' and not post:
        print('not json'); sys.exit(0)
    boot = ('Manually selected kernels:\nNone.\nAutomatically selected kernels:\n'
            '6.17.13-21-pve\n7.0.14-28-pve\n7.0.14-30-pve\n')
    if post and mode == 'boot_changed':
        boot += '\n'
    encode = lambda text: base64.b64encode(text.encode()).decode()
    print(json.dumps({'running_kernel': '7.0.14-30-pve',
                     'packages': {'rc': 1 if mode == 'collect_rc' or (post and mode == 'post_rc') else 0,
                                  'output': encode(packages)},
                     'boot_tool': {'rc': 0, 'output': encode(boot)}}))
elif kind == 'apt-get':
    if mode == 'apt_rc':
        sys.exit(100)
    if mode == 'apt_empty':
        sys.exit(0)
    for name in args[2:]:
        print('Purg ' + name + ' [1]')
    if mode == 'inst_conf':
        print('Inst replacement (1)\nConf replacement (1)')
elif kind == 'dpkg' and '--simulate' in args:
    if mode == 'simulation_timeout':
        time.sleep(3)
    if mode == 'simulation_rc':
        print('dependency problems'); sys.exit(1)
    print('dpkg simulation')
elif kind == 'dpkg' and '--audit' in args:
    if mode == 'audit':
        print('unfinished package state')
elif kind == 'dpkg' and '--purge' in args:
    (root / 'started').touch()
    atexit.register(lambda: (root / 'completed').touch())
    targets = args[1:]
    if mode in {'partial', 'purge_timeout'}:
        targets = targets[:1]
    if mode != 'purge_rc':
        lines = [line for line in packages.splitlines() if line.split('\t')[1] not in targets]
        if mode == 'meta_missing':
            lines = [line for line in lines if line.split('\t')[1] != 'proxmox-kernel-7.0']
        state.write_text('\n'.join(lines) + '\n')
    print('x' * 4000, flush=True)
    if mode == 'purge_timeout':
        print('TIMEOUT TAIL', flush=True); time.sleep(3)
    if mode in {'purge_rc', 'partial'}:
        print('PURGE FAILURE TAIL', file=sys.stderr); sys.exit(1)
    if mode == 'hook':
        print('hook failed')
    print('purged')
else:
    raise SystemExit('unexpected stub invocation')
