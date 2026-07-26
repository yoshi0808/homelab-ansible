# テスト結果: log_observability debug除外(LOG-070/071)Phase 3a — --check相当の検証

対象: `docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md`
(implementer)、`2026-07-26_027_review_debug_exclusion.md`(reviewer、Approve/blocking 0)。
diff: `roles/alloy/tasks/main.yml`、`roles/alloy/templates/config.alloy.j2`、
`roles/alloy/templates/observability-sources.rsyslog.j2`。
実行環境: ansy、tester(Claude Code)。実行日時: 2026-07-26未明(JST)。
tester-gate: check-mode-native。**Phase 3a、APPLYは実施していない**(techlead指示どおり)。

## 前提確認(techlead依頼)

`roles/alloy/tasks/main.yml`を確認し、techlead記載の前提を実行結果で裏付けた。

- `rsyslogd -N1`相当(`Validate the staged Phase 2 rsyslog snippet`)、
  `alloy validate`相当(`Validate the deployed Alloy configuration before cutover`等)を含む
  実バイナリ検証タスクは、いずれも`when: not ansible_check_mode`(または同等条件)で
  ガードされており、**`--check`実行では`skipping`となり実行されない**ことを実行結果で
  確認した(下記「1. alloy_setup.yml」参照)。
- 一方、`Check the rendered Alloy pipeline contract`のassertタスク(今回2件追加・1件削除)は
  `when`句を持たず`check_mode`も明示されていないため、`assert`/`set_fact`の既定の
  check-mode対応により**`--check`下でも評価される**。実行結果で`ok`(PASS)を確認した。

前提はいずれも正しかった。

## 結果サマリ

| # | 確認項目 | 結果 |
|---|---|---|
| 1 | `alloy_setup.yml --check`が対象host(monnie)でエラーなく完走、新設assertがPASS | **PASS** |
| 2 | `rsyslog_forward_to_monnie.yml --check`が対象sender(ansy/quory/authy)でエラーなく完走 | **PASS**(3host個別) |
| 3 | `--check`のdiffが意図した変更範囲に収まっている | **PASS** |
| 4 | 実バイナリ検証(`rsyslogd -N1`/`alloy validate`) | 既知の制約により未実施(techlead指示どおり) |

## 1. alloy_setup.yml --check(monnie)

```
$ ansible-playbook -i inventories/homelab/hosts.yml playbooks/alloy_setup.yml --check --diff
...
TASK [alloy : Check the rendered Alloy pipeline contract] **********************
ok: [monnie]
...
PLAY RECAP
monnie  : ok=50  changed=3  unreachable=0  failed=0  skipped=19
```

新設の2 assert(`observability_debug_excluded`件数一致、`action = "drop"`総数の内訳一致)を
含め、`Check the rendered Alloy pipeline contract`タスクは`ok`(全assert PASS)。

`--diff`出力で確認した変更範囲は、implement/review記録が説明する4系統と完全に一致した:

- `config.alloy.j2`: unifi/network_devicesのbest-effort側2箇所(`stage.static_labels`→
  `action=drop`)、pve_nodes/sophos_fw/ubuntu_nodesのfile source側3箇所(debug drop新設)、
  monnie journalのグローバルdebug drop1箇所(既存の自ノイズdropより前に配置)。冒頭コメントの
  更新も確認。
- `observability-sources.rsyslog.j2`: severity==7の`action()`ブロックが消え、
  `stop`直前にLOG-071を明記したコメントのみが残る形(pve_nodes/sophos_fw/ubuntu_nodesの
  3ブロックとも同形)。

それ以外の意図しない差分(error/warning/info経路、`AlloyRemoteError`/`Warning`/`Info`
template、既存の自ノイズdrop selector等)は見られなかった。

`Validate the staged Phase 2 rsyslog snippet`、`Validate the deployed Alloy configuration
before cutover`を含む実バイナリ検証・cutover系タスク19件は全て`skipping`(前提確認どおり)。

## 2. rsyslog_forward_to_monnie.yml --check(ansy → quory → authy、この順で個別実行)

このplaybookは`pre_tasks`のassertで`ansible_play_hosts_all | length == 1`を要求するため、
`-l`で1hostずつ指定した(playbook冒頭コメントが指定する順序: ansy → quory → authy)。

| host | 結果 | changed | failed |
|---|---|---|---|
| ansy | PASS | 1(forwarding候補のrender diffのみ) | 0 |
| quory | PASS | 1(同上) | 0 |
| authy | PASS | 1(同上、新規rsyslogインストール前提の`stop`行を含む) | 0 |

3hostとも`--check`で完走し、`Require an explicit single-host rollout limit`assertも含め
`failed=0`。このplaybook・role(`rsyslog_forward_to_monnie`)はsender側の転送設定のみを
扱い、debug除外ロジック自体は含まないため(除外処理は受信側のmonnie/Alloyで行う)、
`--diff`で見えた差分はいずれも既存の転送テンプレートのrender(`type="omfwd"`、
`target="monnie.internal"`)のみで、今回のdebug除外変更とは無関係かつ想定どおりだった。
`Validate the staged forwarding candidate`等の実バイナリ検証タスクは3hostとも
`skipping`(前提どおり)。

## 3. --checkのdiff範囲確認

上記1・2の`--diff`出力を全て目視確認し、今回のdiff(implement報告の4系統+
`tasks/main.yml`のassert修正)が生成する差分だけが現れていることを確認した。
error/warning/infoの経路、`AlloyRemoteDebug`削除以外のrsyslog template定義、
既存の自ノイズdrop(`observability_info_debug`)のselector・カウント式には
一切触れていない。

## 4. 実バイナリ検証(未実施・既知の制約)

`rsyslogd -N1`・`alloy validate`はいずれも`--check`ではガードされ実行されないため、
本段階では確認できなかった(前提確認のとおり)。implementer/reviewerが既に検討・
見送った理由(ansy実rsyslogサービスへの影響回避、`alloy`バイナリがansyに存在しない)を
確認し、tester側でも同じ制約に直面した:

- `rsyslogd -N1 -f <rendered file>`をansy上で試みる代替手段は検討したが、
  実rsyslogサービスへ影響しうる`/etc/rsyslog.d/`配下への設置なしには意味のある検証が
  できず、production log pathへの影響を避けるため実施しなかった(techlead指示の
  「無理に実施しない」に従った)。
- `alloy`バイナリはansyに存在しない(implement/review記録と同じ制約)。

Policy(LOG-032/054)が定める設計どおり、これらはAPPLY時(Phase 3b以降)に
`roles/alloy/tasks/main.yml`の既存フローが実行することを確認済みであり、本Phase 3aの
スコープではこれ以上の検証手段はないと判断する。

## 失敗・ブロッカー

なし。

## 総合判定

**Phase 3a(--check相当)の検証は全て完了。新設assert PASS、diff範囲は意図した4系統の
変更に限定、sender側playbookも3host個別に完走・失敗なし。実バイナリ検証(`rsyslogd -N1`/
`alloy validate`)は設計どおりAPPLY時に委譲。ブロッカーなし、Phase 3b(APPLY)へ進んで
問題ないと判断する。**

## Next step files

- docs/ai/reviews/promtail_to_alloy/2026-07-26_026_implement_debug_exclusion.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_027_review_debug_exclusion.md
- docs/ai/reviews/promtail_to_alloy/2026-07-26_028_test_result_debug_exclusion.md(本ファイル)
