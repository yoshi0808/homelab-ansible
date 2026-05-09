#!/usr/bin/env python3
# Merges per-node dryrun JSON files into a unified JSON for Codex classification.
# Usage: proxmox-dryrun-merge.py <nodes_json_in> <unified_json_out>
# nodes_json_in: JSON array of node dryrun results
# IMPORTANT_COMPONENTS env: JSON array of exact package names (important component list)
# IMPORTANT_COMPONENT_PREFIXES env: JSON array of name prefixes

import json
import os
import re
import sys

if len(sys.argv) != 3:
    print("Usage: proxmox-dryrun-merge.py <nodes_json_in> <unified_json_out>", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1], encoding="utf-8") as f:
    nodes = json.load(f)

important_components = json.loads(os.environ.get("IMPORTANT_COMPONENTS", "[]"))
important_prefixes = json.loads(os.environ.get("IMPORTANT_COMPONENT_PREFIXES", "[]"))


def is_important(name):
    if name in important_components:
        return True
    return any(name.startswith(p) for p in important_prefixes)


# Deduplicate updates by package name; track which nodes carry each package
merged_by_name: dict = {}
for node_data in nodes:
    node = node_data["node"]
    for u in node_data.get("updates", []):
        name = u["name"]
        if name not in merged_by_name:
            merged_by_name[name] = dict(u)
            merged_by_name[name]["important_component"] = is_important(name)
            merged_by_name[name]["nodes"] = [node]
        else:
            if node not in merged_by_name[name]["nodes"]:
                merged_by_name[name]["nodes"].append(node)

# Deduplicate removes by package name
merged_removes_by_name: dict = {}
for node_data in nodes:
    node = node_data["node"]
    for r in node_data.get("removes", []):
        name = r["name"]
        if name not in merged_removes_by_name:
            merged_removes_by_name[name] = dict(r)
            merged_removes_by_name[name]["nodes"] = [node]
        else:
            if node not in merged_removes_by_name[name]["nodes"]:
                merged_removes_by_name[name]["nodes"].append(node)

node_names = [n["node"] for n in nodes]
updates_list = list(merged_by_name.values())
removes_list = list(merged_removes_by_name.values())

# Classify: common (all nodes) / per-node-only
all_nodes_set = set(node_names)
common_updates = [u for u in updates_list if set(u["nodes"]) == all_nodes_set]
node_only: dict = {n: [] for n in node_names}
for u in updates_list:
    if set(u["nodes"]) != all_nodes_set:
        for n in u["nodes"]:
            node_only[n].append(u["name"])

# Node-level summary
node_summaries = {}
for nd in nodes:
    node_summaries[nd["node"]] = {
        "apt_check_ok": nd["apt_check_ok"],
        "sim_ok": nd["sim_ok"],
        "reboot_required": nd["reboot_required"],
        "collected_at": nd["collected_at"],
        "update_count": len(nd.get("updates", [])),
        "remove_count": len(nd.get("removes", [])),
    }

unified = {
    "cluster_summary": {
        "nodes": node_names,
        "total_unique_updates": len(updates_list),
        "total_unique_removes": len(removes_list),
        "common_update_count": len(common_updates),
    },
    "node_summaries": node_summaries,
    "classification": {
        "common": [u["name"] for u in common_updates],
        **{f"{n}_only": node_only[n] for n in node_names},
    },
    "updates": updates_list,
    "removes": removes_list,
}

with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(unified, f, ensure_ascii=False, indent=2)

print(f"OK: merged {len(updates_list)} updates, {len(removes_list)} removes -> {sys.argv[2]}")
