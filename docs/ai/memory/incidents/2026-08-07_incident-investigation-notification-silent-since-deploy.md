# Incident: 一次調査のSlack通知が、配備以来8回とも出ていない

日付: 2026-08-07
状態: 調査中(原因未判明。原因を読むための前提が配備待ち)
対象: `roles/incident_investigate/files/incident-investigate.py` の `post_artifact_actions()` / `playbooks/incident_investigate_notify.yml`
種別: 動作不具合
原因分類: 未判明

## 症状

Semaphore ジョブが失敗すると、一次調査の完了が `#alerts` へ1本通知される設計(N1〜N3・N7・N11)。**この通知が本番で一度も出ていない。**

2026-08-07、Yoshinobu が #607 の失敗に対して「一次調査が流れてくるはずが流れてこない」と報告。調べたところ、

- **一次調査そのものは走っている。** `investigation-show semaphore-607 json` は存在し、`investigated_at 03:36:55+09:00` / `status: new` / `llm_rc: 0` / `confidence: high`。Codex は呼ばれ、所見も妥当な内容だった(#607 の真因を正しく指している)。
- 欠けているのは **Slack 通知だけ**である。
- **初回ではない。** 通知機能を配備した 2026-08-01 以降の成果物は 512 / 533 / 535 / 552 / 553 / 554 / 561 / 607 の**8件**あり、`docs/ai/status.md` の Watch「一次調査の通知が本番で実際に出るか」は満たされないままである。つまり**8回連続で出ていない。**

## 原因

**未判明。** 現時点で言えるのは、原因が「読めない」状態にあること自体である。

`post_artifact_actions()` は通知の失敗を捕捉して **stderr(= systemd ジャーナル)へ1行書くだけ**にしており、**成功時は何も残さない**(`docs/ai/reviews/incident_investigation_notify/2026-08-01_006_post_deploy_observation.md` AC1 節が「Slack に届いたことの確認が唯一の直接証拠」と明記している)。この2つが合わさると、通知機構は**どちらの向きにも観測できない** — 「出たが見落とした」と「出ようとして落ちた」が区別できない。

さらに、失敗が残る唯一の場所であるジャーナルへ**到達できなかった**。`journal-unit` が `-n 300` 固定で、このunitは1分timerで約3行/分を出すため、遡れるのは**約100分**である。03:36 の行は約10時間後には読めない。

**これは「壊れているときほどログ量が増えるため、必要な場面でだけ効かなくなる」穴の2件目である**(1件目は `2026-08-06_codex-exec-wrapper-intermittent-enoent.md`)。

### 測って否定した仮説(2026-08-07、いずれも状態を変えない確認)

| 仮説 | 測り方 | 結果 |
|---|---|---|
| 2026-08-06 の Slack アプリ差し替えで、vault 側の webhook が道連れで失効した | 3本の webhook へ**不正 payload** を POST(生きていれば `400 invalid_payload` が返り、**メッセージは投稿されない**。死んでいれば `404 no_service`) | info / alerts / patches とも **400 = 生存**。否定 |
| 通知 playbook 自体が壊れている | ansy で `--check` 実行(送信 task は `when: not ansible_check_mode` で止まる) | `ok=4` / `rc=0` / 0.6秒。assert・include_vars・token 抽出・本文組立はすべて通る。否定 |
| 配備物が repo と食い違っている | `deployed-hash incident-investigate` と repo の `sha256sum` | 一致。否定 |
| `/usr/bin/ansible-playbook` が quory に無く `FileNotFoundError` になっている | `ansible-cert-renew-quory.service` の ExecStart が同じパスを使っている | 存在する。否定 |

**8回連続という事実が示すのは、断続的な障害ではなく系統的な原因である。** かつ 2026-08-06 のアプリ差し替えより前から続いているため、資格情報のローテーションとは無関係である。

## 修正内容

**まだ原因を直していない。原因を読める状態を作る作業を2つ進めている。**

1. **`journal-unit` に行数 operand を足す(D8、Yoshinobu 承認 2026-08-07)。** 配備できれば 03:36 の stderr を実際に読める。記録は `docs/ai/reviews/dev_prod_boundary/2026-08-07_001_requirement.md`。
2. **通知の成否を成果物へ残す。** 次に落ちたときに、ジャーナルの保持窓に関係なく `investigation-show <id> json` から理由が読める形にする。記録は `docs/ai/reviews/incident_investigation_notify/2026-08-07_001_requirement.md`。

**2 は計測であって修正ではない。** 原因が分からない段階で送信側を推測で直さない。

## 確認方法

- D8 配備後、`ssh quory-investigate "journal-unit homelab-incident-investigate.service 24h <行数>"` で 03:36:55 前後の `incident-investigate: Slack notification failed for semaphore-607 (non-fatal): ...` を読む。**この行が無ければ、通知は「試みて失敗した」のではなく「成功したのに届いていない」ことになり、疑う先が Slack 側へ移る。**
- 原因が判明したら本ファイルの `原因` と `原因分類` を埋め、`解決済み` へ移す。
