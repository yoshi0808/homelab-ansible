# Operations Context: healthcheck系roleの共通パターン

作成日: 2026-07-22(初版はPhase 7 pilot3向けの最小サブセット)
更新: 2026-07-26。旧`docs/ai/prompts/core.md` §7・§17のshell責務規範を移設し、**§1はリポジトリ全体に適用される正本**となった。

**位置づけ**: §1「shell / Ansible責務分離」は、healthcheck系に限らず**shellを使う全roleに適用される規範**である(移設元の旧core §7が全体規範だったため)。§2以降はhealthcheck系roleの共通パターンをまとめたContextであり、網羅的ではない。他のhealthcheck roleを読んで拡充・再構成することを前提とする。

§2以降が主に対象とするrole(read-only診断・`safe-readonly` tester-gate系): `monitoring_healthcheck`、`radius_healthcheck`、`proxmox_healthcheck`、`proxmox_hw_check`、`proxmox_snapshot_check`、`time_sync_check`。なお§1を根拠にしているshellはこれ以外にも存在する(`codex_update_check`、`ubuntu_vm_full_upgrade`等)。

## 1. shell / Ansible責務分離

shellスクリプト(`files/*.sh`)は収集とJSON整形のみを行い、warning/critical等の判定をしない。判定・分類・reportは常にAnsible側(`tasks/*.yml`)が行う。共通原則の宣言は`docs/ai/core.md`にあり、以下は旧`docs/ai/prompts/core.md` §7・§17から移設した詳細である(2026-07-26、移行表C07-01/C07-02)。

check系shellは対象ホスト上でコマンドを実行し、結果をJSONに整形して標準出力へ返す。**収集とJSON整形のみ**を行い、次を行わない。

- **変更操作**(check系shellへ変更を伴う操作を一切入れない)
- 正常 / 異常の判定
- warning / criticalの分類
- host_varsとの期待値比較
- 実行継続 / 中止の判断
- 通知
- レポート保存

責務分離は次のとおり。

```text
Shell:   収集とJSON整形のみ
Ansible: 配置、実行、JSON読込、期待値比較、warning/critical分類、保存、fail制御
```

補足:

- shellが`port_1812_listen: true/false`のような観測値を返すことは許容する。
- shellが`status: critical`や`warnings: [...]`を生成することは許容しない。
- shellはhealth判定の主体ではなく、対象ホスト上の情報収集センサーとして扱う。

`proxmox_snapshot_check`の収集script(`proxmox-snapshot-collect.sh`)はこの分離を明示コメントで守っている好例(「7日の閾値はAnsible tasks側で評価する」と明記)。新規判定を追加する際もshell側を変更する必要はなく、`tasks/main.yml`側だけで完結させられる。

## 2. warning/critical 二段階閾値の慣習

`monitoring_healthcheck`(disk/memory)、`radius_healthcheck`、`proxmox_healthcheck`(root filesystem)は、単一のstale/異常判定でなく、warning閾値とcritical閾値の二段階で分類している。

- 数値は`defaults/main.yml`の変数(例: `proxmox_healthcheck_root_fs_critical_pct`)にする場合と、`tasks/check.yml`内に直接定数として書く場合の両方が実在する(`monitoring_healthcheck`は後者)。既存roleは後者の書き方を選んでおり、新規追加時にどちらの書き方を採るかはimplementerの判断だが、同一role内の既存フィールド(例: memoryのwarning/critical)と書き方を揃える。
- 二段階を持たないrole(`proxmox_snapshot_check`は現状warning単一、`proxmox_hw_check`もwarning単一)に二段階目を追加する場合、閾値の意味(「warning=注意喚起」「critical=より深刻な状態を示す重大度」)を受入条件に明記し、既存の単一閾値をwarningのまま残すかcriticalへ格上げするかを明確に区別する。
- **severityとAnsibleのfail/termination(`ansible.builtin.fail`でplayを失敗させるか)は別軸である。** `criticality`はreport・summary・Slack通知の重大度分類であり、roleを実際にfailさせるかどうかはrole固有の既存挙動・受入条件次第である(pilot3の`proxmox_snapshot_check`はfail無しのnotification/report-onlyのまま拡張し、それが妥当と判断された)。新規にfailを追加する場合は、timer/Semaphoreへの影響を伴う独立した要求として明示的に扱う。

## 3. tester-gateマーカーと実guardの整合

`playbooks/*.yml`冒頭の`# tester-gate: safe-readonly`コメントは、Slack通知抑止の実際のguard(`roles/common_slack/tasks/notify.yml`の`skip_notifications | default(false) | bool or ansible_check_mode | bool or (AIエージェントセッション検出 and not slack_force_send)`、3条件のいずれか)と一致している必要がある。TODO 7-2(pilot1)・pilot2で、コメントの理由文と実guardが乖離する“marker drift”が実際に見つかった。reviewerは変更対象playbookのマーカー文言と`common_slack/notify.yml`の条件式を必ず突き合わせる。

## 4. reportの保存パターン

判定結果は`{{ <role>_report_dir | default(reports_base_dir + '/...') }}`配下へ`delegate_to: localhost` / `become: false`でJSON保存する。この経路はread-onlyホストへの副作用を生まないため、pilotのようなlocalhost source-task harnessでも安全にテストできる。

## 5. 既知の落とし穴: 意味論の自前計算

`used_percent`のような値は、`df`等が返すUse%列をそのまま採用し、`used/total`から自前計算しない(丸め・予約領域の扱いが異なるため)。TODO 7-2で見つかり、pilot2(`monitoring_healthcheck`)でも再発しないか確認済み。新しい閾値・指標を追加する際は、参照実装(同系statのある既存role)を実装前に読む。

## この文書の使い方

Coordinatorは案件のpilot setupメモから、この文書のうち関係する節だけを指定する(2026-07-29、Tech Lead廃止に伴い統合)。全節を毎回読ませる想定ではない。Implementer/Reviewer/Testerは、指定された節を読んだ上で疑問が残る場合のみ、対象roleの実コードを直接確認する(このContextより現在のコードを優先する)。
