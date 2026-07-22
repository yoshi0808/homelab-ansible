# Operations Context: healthcheck系roleの共通パターン

作成日: 2026-07-22
作成契機: `docs/ai/reviews/agent_skills_reorganization_plan.md` Phase 7 pilot3(techlead配下、agmsg`claude`依頼、2026-07-22T07:13:28Z)。

**位置づけ**: これはPhase 2で計画されている`context/operations/healthcheck.md`(推奨分類の`docs/ai/context/operations/`配下)の、Phase 7 pilot向け最小サブセットである。網羅的なOperations Contextではない。今回の対象案件(`proxmox_snapshot_check`への閾値2段化)に必要な範囲だけを記載する。Phase 2本格着手時に、他のhealthcheck roleを読んで拡充・再構成することを前提とする。

対象role(read-only診断・`safe-readonly` tester-gate系): `monitoring_healthcheck`、`radius_healthcheck`、`proxmox_healthcheck`、`proxmox_hw_check`、`proxmox_snapshot_check`、`time_sync_check`。

## 1. shell / Ansible責務分離

shellスクリプト(`files/*.sh`)は収集とJSON整形のみを行い、warning/critical等の判定をしない。判定・分類・reportは常にAnsible側(`tasks/*.yml`)が行う。正本は`docs/ai/core.md`。詳細は`docs/ai/core-migration-map.md`のC07-01/C07-02(旧core §7)を辿る。

`proxmox_snapshot_check`の収集script(`proxmox-snapshot-collect.sh`)はこの分離を明示コメントで守っている好例(「7日の閾値はAnsible tasks側で評価する」と明記)。新規判定を追加する際もshell側を変更する必要はなく、`tasks/main.yml`側だけで完結させられる。

## 2. warning/critical 二段階閾値の慣習

`monitoring_healthcheck`(disk/memory)、`radius_healthcheck`、`proxmox_healthcheck`(root filesystem)は、単一のstale/異常判定でなく、warning閾値とcritical閾値の二段階で分類している。

- 数値は`defaults/main.yml`の変数(例: `proxmox_healthcheck_root_fs_critical_pct`)にする場合と、`tasks/check.yml`内に直接定数として書く場合の両方が実在する(`monitoring_healthcheck`は後者)。既存roleは後者の書き方を選んでおり、新規追加時にどちらの書き方を採るかはimplementerの判断だが、同一role内の既存フィールド(例: memoryのwarning/critical)と書き方を揃える。
- 二段階を持たないrole(`proxmox_snapshot_check`は現状warning単一、`proxmox_hw_check`もwarning単一)に二段階目を追加する場合、閾値の意味(「warning=注意喚起」「critical=より深刻な状態を示す重大度」)を受入条件に明記し、既存の単一閾値をwarningのまま残すかcriticalへ格上げするかを明確に区別する。
- **severityとAnsibleのfail/termination(`ansible.builtin.fail`でplayを失敗させるか)は別軸である。** `criticality`はreport・summary・Slack通知の重大度分類であり、roleを実際にfailさせるかどうかはrole固有の既存挙動・受入条件次第である(pilot3の`proxmox_snapshot_check`はfail無しのnotification/report-onlyのまま拡張し、それが妥当と判断された)。新規にfailを追加する場合は、timer/Semaphoreへの影響を伴う独立した要求として明示的に扱う。

## 3. tester-gateマーカーと実guardの整合

`playbooks/*.yml`冒頭の`# tester-gate: safe-readonly`コメントは、Slack通知抑止の実際のguard(`roles/common_slack/tasks/notify.yml`の`tester_mode | default(false) | bool or skip_notifications | default(false) | bool`)と一致している必要がある。TODO 7-2(pilot1)・pilot2で、コメントの理由文と実guardが乖離する“marker drift”が実際に見つかった。reviewerは変更対象playbookのマーカー文言と`common_slack/notify.yml`の条件式を必ず突き合わせる。

## 4. reportの保存パターン

判定結果は`{{ <role>_report_dir | default(reports_base_dir + '/...') }}`配下へ`delegate_to: localhost` / `become: false`でJSON保存する。この経路はread-onlyホストへの副作用を生まないため、pilotのようなlocalhost source-task harnessでも安全にテストできる。

## 5. 既知の落とし穴: 意味論の自前計算

`used_percent`のような値は、`df`等が返すUse%列をそのまま採用し、`used/total`から自前計算しない(丸め・予約領域の扱いが異なるため)。TODO 7-2で見つかり、pilot2(`monitoring_healthcheck`)でも再発しないか確認済み。新しい閾値・指標を追加する際は、参照実装(同系statのある既存role)を実装前に読む。

## この文書の使い方

Tech Leadは案件のpilot setupメモから、この文書のうち関係する節だけを指定する。全節を毎回読ませる想定ではない。Implementer/Reviewer/Testerは、指定された節を読んだ上で疑問が残る場合のみ、対象roleの実コードを直接確認する(このContextより現在のコードを優先する)。
