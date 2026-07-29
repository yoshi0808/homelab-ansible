# Ansible地図3ファイル(inventory-map/playbook-map/role-map)の廃止(2026-07-29)

状態: **決定**。Yoshinobuの問いかけ(「本当に必要ですか？二重管理や誤認のリスクばかりで役に立っていないのでは」)にCoordinatorが同意し、「明確に役に立たないなら削除しましょう」と承認(2026-07-29)。

## 何を変えたか

`docs/ai/context/ansible/inventory-map.md` / `playbook-map.md` / `role-map.md` を削除した。`repository-overview.md`はじめ、これらを参照していた9ファイル(`context-classification.md`、`role-context-matrix.md`、`status.md`、`core-migration-map.md`、`context/system/ubuntu-vm-patch.md`、`context/operations/proxmox-patch.md`、`policies/{ubuntu_vm_patch,proxmox_patch,log_observability}_policy.md`)を、`inventories/homelab/hosts.yml`・`playbooks/*.yml`・`roles/*`への直接参照へ更新した。

## なぜ変えたか

**証拠が既にあった。** `docs/ai/status.md`に「索引は2026-07-25以降更新されず、7/27・7/28の追加が丸ごと抜けていた(role 3件・playbook 6件)」「同種の欠陥は4回起き、うち1回は教訓を記録した**後**だった」という記録が残っていた。手動更新の索引を維持する運用は、書いても実行されないことが繰り返し実証されていた。

**古い索引は、索引が無いより悪い。** Coordinator自身の実際の調査方法は、この種の要約より`grep`/`find`で現物に直接あたる方が速く、かつ必ず最新である。索引が無ければ「調べていない」と自覚できるが、索引が古いと「調べたつもり」で見落とす。これは`docs/ai/memory/lessons/always-loaded-summaries-are-least-current.md`と同型の構造であり、機械チェックを伴わない手動索引は維持コストに見合わないと判断した。

**対応する機械チェック案(`status.md`「Context索引と現物の突合を機械的検査にする」)は起票済みだったが、実装されていなかった。** 索引を維持するのではなく、索引自体を無くして問題を解消する方を選んだ。

## 何を失うか

- 「この要求はどのroleに関係しそうか」という発見の補助は無くなる。System Context(`docs/ai/context/system/*.md`)や`playbooks/README.md`、直接のgrepで代替する。
- `inventory-map.md`のgroup↔host対応表は、`inventories/homelab/hosts.yml`を直接読むことで代替する(9host・9groupの小規模構成のため負担は小さい)。

## 関連

- `docs/ai/status.md`(削除した該当行)
- `docs/ai/context/ansible/repository-overview.md`(新しい navigation 手順)
