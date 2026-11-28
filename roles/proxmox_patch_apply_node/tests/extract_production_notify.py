#!/usr/bin/env python3
"""Read production notification tasks; never copy their Jinja into fixtures."""

import argparse
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[1]
FIRST = "Set notification subject and body"
LAST = "Insert bounded abort package notes into notification body"


def final_tasks(main_path=ROLE / "tasks/main.yml", report=False):
    document = yaml.safe_load(Path(main_path).read_text())
    always = next(task["always"] for task in document if "always" in task)
    names = [task.get("name") for task in always]
    start = names.index("Build and save final report" if report else FIRST)
    end = names.index(LAST) + 1
    tasks = always[start:end]
    # Fail closed if future edits introduce a command or Slack include here.
    for task in tasks:
        actions = {key for key in task if key.startswith("ansible.")}
        assert len(actions) == 1 and actions <= {"ansible.builtin.set_fact", "ansible.builtin.copy"}, task
        if "ansible.builtin.copy" in task:
            assert report and task["name"] == "Build and save final report"
    return tasks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    tasks = final_tasks()
    if args.destination:
        Path(args.destination).write_text(yaml.safe_dump(tasks, allow_unicode=True, sort_keys=False))
