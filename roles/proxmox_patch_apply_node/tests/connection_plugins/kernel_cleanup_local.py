"""Inject one lost connection at async launch/poll; all execution stays local."""
import os
from pathlib import Path
import time

from ansible.errors import AnsibleConnectionFailure
from ansible.plugins.connection.local import Connection as LocalConnection

DOCUMENTATION = r'''
name: kernel_cleanup_local
short_description: Local connection double for detached kernel cleanup tests
description: Executes locally and injects a single connection failure.
author: homelab-ansible
extends_documentation_fragment:
  - connection_pipelining
'''


class Connection(LocalConnection):
    transport = 'kernel_cleanup_local'

    def exec_command(self, cmd, in_data=None, sudoable=True):
        root = Path(os.environ['KERNEL_CLEANUP_TEST_STATE'])
        mode = (root / 'disconnect').read_text()
        needle = 'async_wrapper.py' if mode == 'launch_disconnect' else 'AnsiballZ_async_status.py'
        if needle in cmd and 'chmod' not in cmd and not (root / 'disconnected').exists():
            # Launch really runs the detached local job. Wait for our tiny
            # double to exit before losing its reply, so tests leave no job.
            if mode == 'launch_disconnect':
                super().exec_command(cmd, in_data, sudoable)
            for _ in range(100):
                if (root / 'completed').exists():
                    break
                time.sleep(0.05)
            else:
                raise AssertionError('local purge double did not finish')
            (root / 'disconnected').touch()
            raise AnsibleConnectionFailure('injected local connection loss')
        return super().exec_command(cmd, in_data, sudoable)
