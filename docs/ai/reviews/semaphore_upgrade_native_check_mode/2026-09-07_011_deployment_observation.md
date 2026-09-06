# Deployment observation: Semaphore upgrade native check mode

観測: 2026-09-07 / Coordinator
対象: quory Semaphore / template catalog reconcile job #1005

## 結論

Yoshinobuからjob #1005完了の連絡を受けた後、許可済みのread-only forced command
`semaphore-query template-list 200`でquoryのSemaphore API応答を観測した。API上でも
job #1005のstatusは`success`で、commit `3951af4`を取得していた。

配備済みのapply/rollback templateは、`roles/semaphore_templates/defaults/main.yml`
のカタログと一致した。これによりrequirement AC8の配備・実template観測をPASSとする。

## 観測値

| template | playbook | arguments | Survey Variables |
|---|---|---|---|
| `UN-SAFE: Semaphore upgrade (apply)` | `playbooks/semaphore_upgrade.yml` | `["--limit", "quory"]` | なし |
| `UN-SAFE: Semaphore rollback (rollback)` | `playbooks/semaphore_upgrade.yml` | `["--limit", "quory"]` | `rollback`、`rollback_to`のみ |

- 両templateともdescription markerは期待する`variant=apply` / `variant=rollback`だった。
- 独自`dry_run` Survey Variableは両templateに存在しない。
- Semaphore upgradeのscheduleは、template / scheduleの正本であるカタログに引き続き
  登録されていない。

## 残る初回観測

本観測はtemplate設定の配備確認であり、upgrade/rollback playbook自体は起動していない。
初回のquory UI Dry Runでは、実`homelab-semaphore-query`とACLを使うreading path、および
DB参照前後のSQLite WAL/SHM補助ファイルを確認する。通常upgrade/rollbackも本案件の
検証目的では実行していない。
