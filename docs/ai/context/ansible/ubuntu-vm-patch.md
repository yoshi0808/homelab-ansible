# Ubuntu VM Patch Repository Context

## 位置づけ

本書はUbuntu patch運用に関係する複数playbook / role、apt / non-apt収集、report、通知の横断契約を説明する非規範Contextである。許可、禁止、停止条件、判断軸は [`ubuntu_vm_patch_policy.md`](../../policies/ubuntu_vm_patch_policy.md) が正本であり、競合時はPolicyを優先する。単一taskの実装はcode、対象値はinventory / varsを正本とする。

## 入口とrole連携

| Playbook | 対象 | 主role / task | 横断上の責務 |
|---|---|---|---|
| `radius_healthcheck.yml` | `radius_servers` | `radius_healthcheck` | RADIUS状態を収集、分類し、report /通知する |
| `monitoring_healthcheck.yml` | `monitoring_servers` | `monitoring_healthcheck` | monitoring service群を収集、分類し、report /通知する |
| `ubuntu_nightly.yml` | `radius_servers`、`monitoring_servers` | playbook tasks、`recovery_mute`、`monitoring_healthcheck`、`common_slack` | reboot要否、条件付きreboot、post-check、通知を接続する |
| `ubuntu_vm_full_upgrade.yml` | `dev_nodes:control_nodes:radius_servers:monitoring_servers` | `ubuntu_vm_full_upgrade`、`recovery_mute`、healthcheck roles | monthly simulation /分類と確認付きsingle-node applyを接続する |
| `prometheus_update_check.yml` | `localhost`、`monnie` | `prometheus_update_check`、`common_slack` | version確認と、現行実装上は確認入力付きupdate / rollback補助を持つ |

この一覧は実装入口の索引であり、変更操作の許可ではない。特に`prometheus_update_check.yml`のupdate / rollback / restart機能はPolicyのUV-035〜UV-039と不一致である。 [`playbook-map.md`](playbook-map.md) の既知不一致を見える化するだけで、Contextから許可を追加しない。

## Full-upgrade判定契約

`ubuntu_vm_full_upgrade` roleは次の段階を横断して扱う。

1. `dry_run`、対象node、manual apply confirmationを検証する。
2. node固有healthcheckを行い、criticalならapt処理前に停止する。
3. apt index / check / full-upgrade simulationを収集する。
4. `dry_run=true`の場合だけ、登録済みnon-apt productのcurrent / latestをread-onlyで収集する。
5. apt / non-apt結果を分類し、node別JSON reportとSlack通知を作る。
6. manual applyではStatus gateを通過したsingle nodeだけを処理し、必要時にrebootとpost-checkを行う。

`authy`では`radius_healthcheck`、`monnie`では`monitoring_healthcheck`のcheck taskを再利用する。`ansy` / `quory`はrole内のgeneric healthcheckを使う。具体的なpackage pattern、threshold、confirmation variable、report schemaはrole defaults / tasksを正本とする。

## Ubuntu Proとのarchive境界

旧PolicyがUbuntu Pro / unattended-upgradesへ委ねるarchive contractは次の3系統である。

- `${distro_id}:${distro_codename}-security`
- `${distro_id}ESM:${distro_codename}-infra-security`
- `${distro_id}ESMApps:${distro_codename}-apps-security`

通常更新のmonthly判定はこれらの定常自動適用と役割を分ける。実際のarchive設定とunattended-upgrades設定は対象host上のconfigを正本とし、このContextは現在値を保証しない。

## Non-apt収集契約と既知不一致

`ubuntu_vm_full_upgrade`のgeneric registryは、productごとにcurrent / latestのread-only JSON endpoint、version抽出、tag prefix、timeout、noteを持つ。初期登録は`monnie`のPrometheusで、currentは同hostのbuild information API、latestはPrometheusのGitHub Releases latest stableから取得し、latest tagの`v` prefixを除去する。両取得に成功し数値versionとして比較できる場合だけupdate有無を確定し、取得やparseに失敗した結果はreportへ残す。

node通知の`apt外:`行は、updateありならcurrentからlatestとmanual updateが必要なこと、latestならcurrentとlatest状態、失敗ならcurrent / latest return codeを表示する。JSON reportの`nonapt`はname、current、latest、state、current / latest return code、HTTP status、noteを持つ。正確な文字列組立とschemaはrole tasksを正本とする。

一方、独立した`prometheus_update_check` roleは現行code上、明示`dry_run`、target version、rollback入力、backup、download、service healthを扱う。これはPolicyの「確認専用」「自動download /自動更新 / service restartを一切行わない」と一致しない。本標準化ではcodeもPolicy意味も変更せず、実行可否を本Contextで再定義しない。

## Nightlyとhealthcheck

- `ubuntu_nightly.yml`はreboot-required fileとneedrestart結果をORで評価する。
- reboot不要ならdestructive blockと通知をskipする。
- rebootが必要ならrecovery mute、開始通知、reboot、起動待機、node別post-check、結果通知を順に行う。
- standalone healthcheck入口は収集、分類、controller側report保存、異常時通知を行う。
- healthcheck roleのcheck taskを他callerが再利用する場合、保存、通知、failの責務はcaller側が持つ。

## Reportと通知

| 種別 | 主な入力 | 主な出力 |
|---|---|---|
| full-upgrade | health、apt simulation、hold、non-apt取得結果 | node別Status、reason、package detail、JSON report、Slack通知 |
| nightly | reboot flag、needrestart、post-check | reboot結果、service結果、Slack通知 |
| healthcheck | service、listen、resource、journal等の観測 | health分類、JSON report、異常時Slack通知 |

Slackは`common_slack/tasks/notify.yml`を通じて送信し、Webhook変数はVault管理する。通知失敗はbest-effortである。channel / statusの規範はPolicy §6、変数と分岐の実装はcaller / `common_slack` codeを正本とする。秘密値をContextへ複製しない。

## 論理group境界

- `ubuntu_vm_full_upgrade.yml`はgroup2「アプリ・パッケージ更新」の本Policy主入口である。
- `prometheus_update_check.yml`はgroup2のnon-apt関連入口だが、既知不一致を解消するまで変更機能の許可を意味しない。
- `ubuntu_nightly.yml`はpackage更新入口でなくreboot lifecycleの従属入口である。
- `codex_update_check.yml`はgroup2の横断indexに含まれるが、本Policyのowner外であり、対応5入口へ含めない。
- `radius_healthcheck.yml` / `monitoring_healthcheck.yml`はgroup1からも参照されるが、本Policy ownerのままであり、更新入口へ分類しない。
