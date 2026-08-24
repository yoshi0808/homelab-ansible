# Incident: 一次調査のSlack通知が、配備以来届いていない

日付: 2026-08-07
状態: 解決済み(2026-08-25。原因Aは確定・解消済み。原因Bは読む手段が失われたため打ち切り。以後3回の一次調査がいずれも通知成功で記録されている)
対象: `roles/incident_investigate/files/incident-investigate.py` の `post_artifact_actions()` / `playbooks/incident_investigate_notify.yml`
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

Semaphore ジョブが失敗すると、一次調査の完了が `#alerts` へ1本通知される設計(N1〜N3・N7・N11)。**この通知が本番で一度も出ていない。**

2026-08-07、Yoshinobu が #607 の失敗に対して「一次調査が流れてくるはずが流れてこない」と報告。調べたところ、

- **一次調査そのものは走っている。** `investigation-show semaphore-607 json` は存在し、`investigated_at 03:36:55+09:00` / `status: new` / `llm_rc: 0` / `confidence: high`。Codex は呼ばれ、所見も妥当な内容だった(#607 の真因を正しく指している)。
- 欠けているのは **Slack 通知だけ**である。
- **初回ではない。** 通知機能を配備した 2026-08-01 以降の成果物は 512 / 533 / 535 / 552 / 553 / 554 / 561 / 607 の8件ある。

**何件が落ちたのかは確定していない。** 当初この記録は「8回連続で出ていない」と書いたが、根拠にした `docs/ai/status.md` の Watch 行は**最終確認が 2026-08-03** であり、それ以降を保証しない。確定しているのは次のとおりである。

| 成果物 | 通知 | 根拠 |
|---|---|---|
| 512(8/1)/ 533(8/2)/ 535(8/3) | **出ていない** | Watch 行が 8/3 時点でそう記録している |
| 552 / 553 / 554 / 561(いずれも 8/4) | **不明** | 8/3 以降、誰も確認していない |
| 607(8/7) | **出ていない** | Yoshinobu の観測 |

**この誤りは無害ではなかった。** 「8回連続」を系統的な単一原因の根拠として使い、原因を1つに寄せて探していた。実際には後述のとおり**時期の異なる複数の原因**がありうる。

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

### quory の作業ツリーが汚れていた(2026-08-07 に判明)

同日、別件(`git push` 後に worktree-sync の成功通知が来ない)を追う過程で、**quory の作業ツリーの `inventories/vars/slack.yml` が変更された状態**になっていることが分かった(mtime 2026-08-06 11:45:33)。Yoshinobu が中身を確認したところ**古い版**で、既に削除したパラメータと `vault_claude_code_oauth_token` が残っていた。

これが効く範囲は次のとおり分かれる。

- **quory の作業ツリーから systemd 経由で走る通知**(一次調査 / worktree_sync / recovery_probe / cert_renew_quory)は、この古いファイルを読む
- **Semaphore のジョブは影響を受けない。** ジョブごとに `/opt/semaphore/project_1/repository_1_template_5/` へ clone するため(#607 のエラーメッセージが示すパスがこれ)

古い版は旧アプリ(2026-08-06 に削除され webhook ごと失効)の webhook URL を持っている可能性が高く、**607 の沈黙の説明になる。**

**ただし 512(8/1)と 533(8/2)は説明できない。** 汚れが始まる4〜5日前である。**時期の異なる複数の原因があることになる。**

なお、この汚れは**自分の警報を自分で黙らせていた** — worktree-sync が「作業ツリーが汚れている」と報せる通知は、その汚れているファイルを読んで送られる。13:49 と 14:49 に1時間周期で2回試みられ、2回とも消えている。

### 607 の原因は確定した(2026-08-07 夕、D8 配備後)

D8 を配備してジャーナルを遡り、当該行を取得した。

```
8月 07 03:36:56 quory flock[41561]:
  incident-investigate: Slack notification failed for semaphore-607 (non-fatal):
  notify playbook rc=2 stderr=''
```

`rc=2` は ansible-playbook の「1つ以上のhostが失敗」。**通知playbookは起動し、その中のtaskが落ちている。** 当該時刻の quory の作業ツリーは上記の古い slack.yml、すなわち削除済み旧アプリの失効した webhook を持っていた。**607 はこれで説明が付き、`git restore` により解消している。**

裏付けとして、Yoshinobu の観測が一致する — dirty の警告は**旧アプリが有効だった昨日は届いており**、アプリ削除後の 13:49 / 14:49 の2回は消えている。今朝 3:31 の monnie 障害通知が届いたのは、あれが Semaphore ジョブで**毎回 clone する**ため作業ツリーを見ないからである。restore 後 15:13 の worktree_sync 成功通知は `#info` へ届いた。

### 残っているもの(原因B)

**8/1〜8/4 の分は説明が付かない。** 汚れが始まったのは 8/6 11:45 で、それ以前の作業ツリーは健全だった(8/3 に worktree-sync が pull に成功している = dirty ゲートを通っている)。8/4 には `deployment_drift_check` 等が `#alerts` へ届いており、**その日 webhook は機能していた。**

**ジャーナルの窓は 8/6 15:36 までしか届かず、8/1〜8/4 は永久に読めない。** 次に一次調査が発生したときが唯一の検証機会である。

## 修正内容

**607 の原因(古い slack.yml)は解消済み。原因Bは未解明で、読める状態を作る作業を2つ進めた。**

1. **`journal-unit` に行数 operand を足す(D8、Yoshinobu 承認 2026-08-07)。** 配備済み。これで 03:36 の行が読め、607 の原因が確定した。記録は `docs/ai/reviews/dev_prod_boundary/2026-08-07_001_requirement.md`。
2. **通知の成否を成果物へ残す。** 次に落ちたときに、ジャーナルの保持窓に関係なく `investigation-show <id> json` の `notification` から理由が読める形にする。記録は `docs/ai/reviews/incident_investigation_notify/2026-08-07_001_requirement.md`。

**2 は計測であって修正ではない。** 原因が分からない段階で送信側を推測で直さない。

**そして 2 の初版は用をなしていなかった。** 記録する文字列が `rc` と **stderr** だけで、ansible が失敗の理由を書くのは **stdout** の側である。配備した直後に読んだ 607 のジャーナルが、まさにその無内容な文字列(`rc=2 stderr=''`)だった。stdout を捕捉する形へ直し、通知playbook側にも理由を出し直す `rescue` を足した。**この欠陥は契約にも実装にも現れず、「実際に落ちたときの出力」と突き合わせて初めて見えた** — 独立レビュー2体はどちらも Approve している。経緯と是正は `docs/ai/reviews/incident_investigation_notify/2026-08-07_005_followup.md`。

## 決着(2026-08-25、月次Knowledge振り返りで実測)

**「次に一次調査が発生したときが唯一の検証機会である」と書いた検証機会は、3回訪れて3回とも緑だった。**

| 成果物 | `notification` | 通知時刻 |
|---|---|---|
| `semaphore-631` | `attempted: true` / `sent: true` / `error: null` | 2026-08-08T06:12:00+09:00 |
| `semaphore-675` | 同上 | 2026-08-11T09:16:57+09:00 |
| `semaphore-802` | 同上 | 2026-08-22T15:06:35+09:00 |

測り方は `ssh quory-investigate "investigation-show <id> json"` の `notification` フィールドで、これは本Incidentの「修正内容」2番目(通知の成否を成果物へ残す)が入れたものである。**ジャーナルの保持窓に依存せず読めるようになっている**ことが、この3件で実証された。

**原因B(8/1〜8/4の沈黙)は打ち切る。** ジャーナルの窓が 8/6 15:36 までしか届かず、当時の成果物には `notification` フィールドが無いため、**原理的に読む手段が無い**。以後の観測が3回とも成功しているため、追う価値も残っていない。

**残る限界**: `sent: true` が意味するのは「通知playbookが rc=0 で終わった」ことであって、Slackのチャンネルに実際に表示されたことではない。両者を隔てる経路(Slack API側の黙殺)は依然として観測していない。

## 確認方法

- D8 配備後、`ssh quory-investigate "journal-unit homelab-incident-investigate.service 24h <行数>"` で 03:36:55 前後の `incident-investigate: Slack notification failed for semaphore-607 (non-fatal): ...` を読む。**この行が無ければ、通知は「試みて失敗した」のではなく「成功したのに届いていない」ことになり、疑う先が Slack 側へ移る。**
- 原因が判明したら本ファイルの `原因` と `原因分類` を埋め、`解決済み` へ移す。
