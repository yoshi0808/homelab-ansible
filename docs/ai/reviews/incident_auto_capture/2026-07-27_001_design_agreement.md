# 障害の自動捕捉・第一報起票 — 設計合意(2026-07-27)

状態: **設計合意済み。requirement未着手。**

Yoshinobuとの対話で確定した方針を記録する。実装はまだ無い。この文書は requirement を書く前段の合意事項であり、各決定の**理由**まで残す(結論だけ残すと、前提が変わったときに見直す手がかりが無くなるため)。

## 背景と目的

Ansibleジョブの失敗は現在Slackへ通知され、Yoshinobuが必要に応じてSlack経由でCodex→`recovery.io`のallowlistコマンドで調査している。この経路は**調査の道具としては機能している**。

不足しているのは**捕捉**である。気づかなかった事象・後回しにした事象が記録に残らない。これは既に測定済みで、2026-07-27の月次Knowledge振り返りが「種別:未遂の該当2件が未起票、母数不足でタグ集計が働かない」と報告している。Incident→Policy/Skill昇格のループが入口の枯渇で回っていない。

目的は「自律運用を開発へ還元する」ことであり、そのためにまず**事実の捕捉を自動化する**。

## 決定事項

### D1. granting の単位は「名前のついた操作」であり、Ansible実行権そのものではない

`recovery.io` の allowlist が安全なのは、リストが短いからではなく**引数面がゼロ**だからである(`recovery-investigate-dispatch.sh.j2` は `SSH_ORIGINAL_COMMAND` を固定文字列と突き合わせ、非一致は `denied`。ヘッダにも "No arguments accepted from the SSH client" と明記)。AIは名前を選ぶだけで、何が走るかを形作れない。

`ansible-playbook` の実行権を与えるとこの性質が失われる。`-e` / `--limit` / `--tags` があるため、**同じplaybookでも引数次第で影響範囲が変わる**。「playbookはrepoにあるからcommit+pullが要る」は*どのplaybookが存在するか*を縛るだけで、*どう呼ぶか*を縛らない。

したがって与えるのは名前付き操作とする。実装がAnsibleでもよいが、引数は固定し呼び出し側から渡せない。

```
investigate-proxmox-health → ansible-playbook playbooks/proxmox_healthcheck.yml(引数固定)
```

拡張経路は現行と同じ: repo編集 → commit → quory pull → `recovery_exec` 再デプロイ。人手が2回入る。

### D2. カタログ登録は1本ずつ人が判断する。`safe-readonly` は必要条件であって十分条件ではない

`# tester-gate: safe-readonly` は現在40 playbook中8本。ただし `docs/ai/policies/ansible_test_safety_policy.md` 自身が「`safe-readonly`であっても、script配置、report保存、条件付きSlack通知などの副作用を持つ場合がある。分類名から副作用ゼロを推定しない」と釘を刺している。

さらにあの分類は**人が見ている開発ワークフロー**を前提に作られており、無人・深夜・障害中という条件で再点検されていない。よって自動的な適格判定には使わない。

### D3. 第一報は5節構成、確度をラベルする。`原因分類`タグは空のまま

| 節 | 内容 | 確度 |
|---|---|---|
| §1 何が起きたか | 落ちたjob、task、rc、時刻 | 確定事実 |
| §2 今どうなっているか | 影響範囲、継続中か自己復旧したか | 確定事実(報告時点の観測) |
| §3 想定される原因 | 仮説を複数、各々に支持/反証/未確認 | **仮説** |
| §4 想定される対応 | 選択肢と前提・副作用。実行はしない | **提案** |
| §5 未確認事項 | 確かめられなかったこと | — |

`原因分類`(`#製造ミス` 等)は月次でPolicy/Skill昇格を駆動する集計キーであり、仮説が混ざると母数が汚れて昇格判断が狂う。**§3に仮説を書くことと、タグを埋めることは別の行為**とする。タグを埋めるのは人、または確定後の対話セッション。

`skills/incident-recording/SKILL.md` の2段階(`調査中` → `解決済み`)がこの分離をすでに担保している。自動化が触れるのは `調査中` まで。

**§5が開発ループにとって最も価値が高い。** 「確かめたかったが叩ける操作が無かった」の各行が、次に追加すべき名前付き操作の根拠つきrequirementになる。カタログは机上で広げず、実際の障害が必要性を証明したものだけを通常の開発工程で足す。初期のカタログが貧弱なのは欠陥ではなく、成長を推測でなく証拠で駆動するための設計である。

### D4. 収集はquory(決定論、LLMなし)、叙述はansy(`claude -p`)

**ansyはクラスタ配下のVMであり、報告すべき障害に巻き込まれて落ちうる**(Yoshinobu指摘)。障害と一緒に死ぬ報告者は役に立たない。観測者は観測対象の外側に置く。quoryはクラスタ外の制御点であり、この条件を満たす。

一方 `docs/ai/core.md` は「quory上で原則としてコードを直接編集・commitしない」と定めるため、quoryのAIがrepoへ書くとこれを破る。したがって**収集と叙述を分ける**。

```
[quory] 失敗 → 証拠バンドル(JSON)を reports/ 配下へ。★LLMなし、決定論的
[ansy]  timerが read-only で取得 → claude -p が §1〜§5 を起票
```

腐りやすい情報(現況)をクラスタ外の生存者が押さえ、腐らない情報(叙述)を後で書く。ansyが落ちていても事実は失われない。副次的に、quoryへ `claude` を導入・ログイン・課金する必要がなくなる(**本番制御平面にLLMを置かない**)。

収集にLLMは要らない。2026-07-27にYoshinobuが共有した `recovery.io` の調査結果2件を分解すると、収集部分(SSH到達性、`pvecm status`、HA master、VM一覧、Semaphoreジョブ出力)はすべて固定チェックで出せる。判断が要ったのは「異常/人手確認推奨」「エスカレーション対象」という結論だけで、そこが §3・§4 に当たる。

### D5. 排他は flock。予定表を読ませない

**排他は「予定表を読む」ではなく「実際のロックを見る」で判定する。** 予定はズレるがロックはズレない。Notionの人間向け時刻管理表をAIに読ませる案は、repo外の索引を状態の根拠にする形であり、`docs/ai/status.md` 新設で解消したのと同じ構造の罠になるため採らない。

実装は軽い。`knowledge-review.service` が既に `/usr/bin/flock -n /run/lock/...` を使っている前例がある。加えて収集はread-onlyなので衝突の害が小さい(現allowlistは `systemctl status` / `journalctl` / `df` / `free` / `ip` で、パッチ実行中に走っても壊さない)。

将来 apt/dpkg 状態を見るチェックを足す場合は、そのチェックが「確認できず(パッチ実行中)」と正直に返す。これは §5 に載るべき情報であり、隠すべき失敗ではない。メンテ窓の概念が本当に必要になった時点で `recovery_mute` へ相乗りする。

### D6. 捕捉の起点は2つ。片方では系統的に漏れる

| 起点 | 拾えるもの | 落とすもの |
|---|---|---|
| **Semaphore の SQLite**(ジョブ結果) | 中断・crash・rc≠0。**生ログ全文とジョブID** | **rc=0の意味的WARNING**(Semaphoreは緑) |
| **`notify.yml` 冒頭** | `slack_status` の意味的重大度(warning/critical) | 中断・crash系(notifyへ到達しない) |

- `notify.yml` は33箇所からincludeされる**単一の絞り**であり、全タスクが `delegate_to: localhost`(本番ではquory)。仕込むと証拠は自動的にquoryへ落ちる。
- ただし冒頭に `tester_mode` / `skip_notifications` の抑止ゲートがある。**捕捉はこのゲートより前に置く。** 通知の抑止は人間の注意管理、証拠の保全は開発ループであり、別の要件である。mute中・通知を絞っている局面ほど証拠が要る。`tester_mode` 中の捕捉はスキップせず**フラグとしてバンドルに記録**し、仕分けは叙述側で行う(「捕捉と昇格を分ける」と同じ形)。
- `notify.yml` は role が明示的にincludeして初めて動くため、UNREACHABLE中断・`any_errors_fatal`・テンプレート/構文エラー・timeout・killでは発火しない。**`proxmox_patch_dryrun` の単一ノード問題がまさにこのクラス**だった。
- Semaphore側は上記クラスをすでに記録済みであり、**ジョブ番号という識別子も既にある**。相関IDは発明せずこれを使う。Semaphore外の本番ジョブは実質 `cert-renew-quory` のみなので、そこだけ薄い保険を足す。

### D7. 証拠バンドルには「要約」と「生ログ」の両方を入れる

同じジョブから2種類のログが出る。

- **要約(alert宛て)**: `SUMMARY proxmox_hw_check | Result=OK | Next=none | pve2=OK` — roleが解釈した結果
- **生ログ(semaphore宛て)**: `fatal: [pve1]: UNREACHABLE!` / `exit status 4` — 実際に起きたこと

**両者は食い違うことがあり、食い違い自体が情報である。** 2026-07-26のSemaphore #461 が実例で、要約は `Result=OK` だがジョブ全体は pve1 到達不能で rc=4。要約はpve2しか見ていない。`docs/ai/memory/lessons/always-loaded-summaries-are-the-least-current.md` のランタイム版にあたる。突き合わせは叙述側(ansy)に行わせる。

## 相関ID

現在、Slack通知 / `recovery.io` の調査結果 / `docs/ai/memory/incidents/` の3つに共通の識別子が無い。そのため良質な調査結果がSlackの散文として蒸発している。

捕捉時にIDを確定し、Slack本文へ載せる。これにより通知が**終点でなく入口**になる。

- Semaphoreジョブ由来: ジョブ番号を使う
- Semaphore外: `timer-<unit>-<timestamp>` 形式

## 実装前に潰す細部

1. **UTC / JST の混在**。Semaphoreは `2026-07-26 20:45:01 UTC` で保持する。リポジトリの時刻表記はJSTが正。バンドルのスキーマでタイムゾーンを明示して持ち、Incident本文はJSTへ変換する。**なおJST規約自体がrepo内にほぼ記載されていない**(`autonomous_recovery_policy.md` に通知文言の1行があるのみ)。Implementerが従うべき規約なので別途repo側へ明文化する。
2. **Semaphoreスキーマへの結合**。SQLiteを直接SELECTするとSemaphoreのアップグレードで壊れる。危険なのは壊れ方で、**静かに空のバンドルを作り続ける**のが最悪。SELECTを1箇所へ閉じ込め、スキーマ不一致は「取得失敗」として明示的にバンドルへ記録する。
3. **無人起票と月次振り返りの相互作用**。無人実行はcommitできない(`docs/ai/core.md`)。Incidentが自動起票されると作業ツリーが汚れたまま残るが、月次Knowledge振り返りは「作業ツリーが汚れているときは何も書かずに中止」する。**自動起票が動くほど月次が発火しなくなる。** 起票先を分けるか、中止条件を「自分が書く範囲だけ見る」へ精緻化するか、requirement段階で決める。
4. **秘密情報の混入**。バンドルにはjournal/stderrの生ログが入り、それを公開repoの `docs/ai/memory/incidents/` へ書く。gitleaksとIPv4 pre-commitチェックは効くが、ホスト名や内部パスは素通りする。**生ログをIncident本文へ転記させず、バンドルへの参照だけ書かせる**規律を仕様に含める。

## やらないこと

- **Claudeに自動復旧させない。** 決定論的な復旧は `recovery_probe` のラダー(VM reboot → HA failover)が既に持つ。judgmentが要るのは報告であって行動ではない。
- **原因を断定させない。** `状態: 調査中` 止まり。
- **常時接続チャネルを増やさない。** `recovery.io` の静的allowlistは現行のまま引き継ぐ。
- **§4「想定される対応」の実行を自動化しない。** なお allowlist が縛るのはAIであって人ではない。第一報を読む人間はallowlistの外にいるため、対応案には「実行する前に確かめること」を併記させる。目的はAIの暴走防止ではなく、**疲れている人間の判断を助けること**。

## 次のステップ

Step 1 =「quory側の証拠バンドル + 現況スナップショット生成」の requirement 作成。対象ジョブの選定(全playbookか、Semaphore scheduleに載っているものだけか)とバンドルのスキーマ決定を含む。意味判断の量が多く、実装前に調査と受入を分ける価値があるため **Tier 4** 想定。

## 参照

- `docs/ai/status.md`(現在地)
- `skills/incident-recording/SKILL.md`(Incidentの型、2段階)
- `docs/ai/memory-classification.md`(月次振り返り、昇格ラダー)
- `docs/ai/policies/ansible_test_safety_policy.md`(`safe-readonly` 他の分類)
- `roles/recovery_exec/templates/recovery-investigate-dispatch.sh.j2`(現行allowlist)
- `roles/common_slack/tasks/notify.yml`(単一の絞り、抑止ゲート)
