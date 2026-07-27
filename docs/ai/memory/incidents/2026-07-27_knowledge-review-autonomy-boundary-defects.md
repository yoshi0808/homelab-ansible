# Incident: 月次Knowledge振り返りの無人実行で、境界設計の欠陥をcommit直前まで12件抱えていた

日付: 2026-07-27
状態: 解決済み
対象: `roles/knowledge_review`、`playbooks/knowledge_review.yml`、`playbooks/knowledge_review_timer.yml`、および同時に改訂した規範文書(`skills/incident-recording/SKILL.md`、`docs/ai/memory-classification.md`、`docs/ai/role-routing-index.md`)
種別: 未遂
原因分類: #テスト不足 #製造ミス #運用考慮ミス #要件定義ミス

## 症状

月次Knowledge振り返りを`claude -p`で無人実行する仕組みを実装した。Coordinatorが要求整理・設計・実装・検証をすべて単独で行い、各段階で「実測で確認済み」と報告した。

独立レビュー5巡で**Critical計12件**を検出。本番影響はゼロ(commit前・timer停止中に全件解消)だが、**Yoshinobuが「reviewerに見てもらわなくて大丈夫ですか」と問いかけなければ、全件がcommitされ2026-08-26に無人発火していた**。

巡ごとの内訳と、見落としの層:

| 巡 | Critical | 見落としの層 |
|---|---|---|
| 1 | 2件 | **機構の不在** — promptに文章で「書いてはいけない」と書いただけで技術的強制がゼロ。止めるものはモデルの自制のみ |
| 2 | 4件 | **列挙漏れ** — `--disallowedTools`のdenylistから漏れた`CLAUDE.md`・`AGENTS.md`・`docs/ai/`直下の正本群など9ファイルへ、レビュアーが実機で書込成功 |
| 3 | 2件 | **軸の欠落** — 書込だけ塞ぎ読取が無制限。vaultパスワード・SSHキーへ到達でき、書込先が公開GitHubのgit管理下 |
| 4 | 3件 | **安全弁が効かない** — `failed_when: false`が`timeout:`超過を吸収せず、タイムアウト時に通知経路ごと消失。汚れた作業ツリーでの中止も無通知(正常運用で毎月起き得る) |
| 5 | 1件 | **修正が新しい沈黙を作った** — 二重の沈黙を防ぐため入れたvault preflightに`failed_when: false`を付け、`failed`属性が上書きされて判定が絶対に真にならなくなった |

## 原因

**直接原因は独立レビューを工程から省いたこと。** `skills/delegation-tier/SKILL.md`の軸Bは「規範・正本の移設や削除」を`+R`必須としており、本案件は規範文書2件と正本1件を変更していたため、**文書化されたルール上は独立レビューが必須だった**。Tier判定を一度も声に出さず着手した。

判定を省いたこと自体は、省いた本人には検出できない(判定していないので判定漏れとして現れない)。人間の問いかけが唯一の検出手段になっていた。

**検証が毎回「効くこと」だけを測り「漏れがないこと」を測らなかった。** 2巡目では実際にdecoy環境でdenyが効くことを実測し「確認済み」と報告したが、測ったのは列挙した1件であり、列挙外は一度も試していない。3巡目の測り直しでは、テスト場所を`/tmp`(この環境では既に広く許可済み)に置いたため測定自体が無効化されていた。

**タグ別の内訳**:
- `#テスト不足` — 上記の検証設計そのもの。5巡すべてに関与する主因
- `#製造ミス` — `failed_when`の2つの副作用(timeout非吸収、`failed`属性の上書き)。Ansibleの仕様理解の誤り
- `#運用考慮ミス` — 汚れた作業ツリーでの無通知中止。先月分が未commitなら翌月必ず起きる経路を、異常系としてしか見ていなかった
- `#要件定義ミス` — 問題を「**書込**境界を作る」と自ら framing したため、読取が検討対象から外れた。軸の欠落はこの framing に起因する

## 修正内容

- 書込境界をdenylist(`--disallowedTools`)からallowlist(`--settings`+`--setting-sources ''`)へ反転。読取も`Read(docs/**)`・`Read(skills/**)`へ限定
- `Bash`/`WebFetch`/`WebSearch`を全面禁止(Writeのpath制限をshell経由で迂回させないため)
- auto-memory(repo外・git管理外)を読み取り専用にし、無人実行が触れない設計へ。期日更新はAnsible側が確定的に行う
- 中止を致命的失敗から「通知される正常終了」(`ABORTED_DIRTY`)へ変更。`ignore_errors`と`is failed`判定でタイムアウトも確実に`FAILED`へ倒す
- vault preflightを`failed_when: false`から`ignore_errors: true`へ(`failed`属性を保つため)
- 撤回した規範3件(旧Incident記録ルール、`--disallowedTools`の根拠、settings.json依存の記述)を機械的に掃引し残存ゼロを確認

教訓は `docs/ai/memory/lessons/verify-the-outside-of-a-claimed-boundary.md`(3層モデル)、`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`(封じ込めの条件)、`docs/ai/memory/lessons/sweep-all-documents-stating-a-changed-boundary.md`(根拠2として追記)へ昇格済み。

## 確認方法

- 独立レビュー5巡目で「残Criticalなし、収束としてよい」の判定を得た(4巡目Criticalは4状態すべてscratch環境で再現確認済み)
- 実機初回実行(2026-07-27 09:23〜09:30、`systemctl start`)が`Result: success`、ok=21/changed=4/failed=0で完走。Policy・`.claude/`・`playbooks/`・auto-memoryへの書込ゼロを`git status`で裏取り
- systemd配下でのvault復号・HOME解決・**Slack通知到達**まで実証(最後まで未検証だった経路)
- `--check`・`--syntax-check`・`ansible-lint`・tester-gate lint・pre-commit(機密/IPv4)すべてPASS

## 残課題

なし。5巡目レビュアーが推奨した `Abort when Slack vars cannot be decrypted` の実地確認は2026-07-27に実施した。`vars/slack.yml` を解決できないinventoryを渡して実行し、preflightが`ignored`、Abortが意図した文言で発火し、`claude -p`本体へ到達しないことを確認済み。

なお、このAbortは素の`fail`であるためSlack通知は飛ばない(systemd unitがfailed状態になるのが唯一の signal)。vault復号が壊れている状況ではSlack通知自体が不可能なため設計上の受容だが、**通知経路が壊れたときに能動的に知る手段が無いという残存リスクは解消していない**。5巡目レビュアーは既存の監視パイプライン(journald→Alloy/Loki)へ乗せる案を提示しており、対応するなら別案件とする。
