#!/usr/bin/python
"""Local fixture module: emulate a static Notion API authentication failure."""
import os

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(argument_spec={
        "page": {"type": "str", "required": True},
        "token_file": {"type": "path", "required": True},
        "lock_directory": {"type": "path", "required": True},
        "observations": {"type": "dict", "required": True},
        "apply_report_dir": {"type": "path", "required": True},
        "node_roles": {"type": "dict", "required": True},
        "suppress": {"type": "bool", "default": True},
    }, supports_check_mode=True)
    status = os.environ.get("PROXMOX_RUNNING_VERSIONS_FIXTURE_HTTP_STATUS", "401")
    module.fail_json(msg="http_" + status, publication="incomplete", body="", overall_status="error",
                     execution_error=False)


if __name__ == "__main__":
    main()
