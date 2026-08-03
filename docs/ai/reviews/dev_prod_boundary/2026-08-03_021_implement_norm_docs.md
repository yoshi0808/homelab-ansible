# Implement: 無人Claude Codeセッション消滅を規範文書へ反映

## 対象パスと変更の要点

| 文書 | 変更 |
|---|---|
| `docs/ai/role-routing-index.md` | 「### 無人実行されるCoordinator」節(見出し・本文2段落・許可範囲の表)を丸ごと削除。「## 証跡の扱い」節はそのまま残した |
| `docs/ai/memory-classification.md` | 「月次振り返りの対象と手順」内の2箇所を改訂。①「起動はtimerが行う」の文を、`claude -p`による無人実行の記述から、timerは通知のみを出し振り返り自体は人がCoordinatorとの対話セッションで行う旨へ差し替え。②「自律の境界」と「無人実行は`status.md`を書き換えない」の2段落を1段落へ統合し、書き出し先に`docs/ai/status.md`を追加、無人実行専用のallowlist記述・削除済み節への参照・lessonファイルへの参照を除去 |
| `skills/incident-recording/SKILL.md` | 運用ルールの1行を「timerが起動する」→「timerがきっかけの通知を出す」へ変更 |
| `docs/ai/status.md` | Watch行1件を削除(「月次Knowledge振り返りの初回無人実行。障害評価(2本目の`claude -p`)を含む」— 障害評価段が消滅したため観測対象自体が無くなった)。Watch行1件を部分修正(`incident_sync`退役に伴う行の「`claude -p`側は結果ファイルを読むだけでBash禁止のままでよい」を「対話セッション側は、用意された結果ファイルを読むだけでよい」へ)。Next行1件を削除(「月次評価に一次調査の成果物を読ませる(R13)」— `claude -p`ベースの評価promptという前提そのものが消滅) |

## lessonの扱い(判断と根拠)

`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md` は**削除せず、無変更のまま残した**。

根拠:
- 今回**触らない**`docs/ai/policies/incident_capture_policy.md`のIC-018が、この lesson を「無人セッションの封じ込めが成立する条件」の正本として現在も直接参照している。同Policyの改訂履歴(2026-08-03分)は「IC-018は変更していない — 無人セッションの封じ込めという規律自体は一次調査(Codex)に対して生きている」と明記しており、Claude Code固有の無人セッションが消えた後も、封じ込めの一般原則(allowlist方式・複数条件の併用・denylist不採用)をCodex側の一次調査に適用する根拠として意図的に存置されている。
- lessonを削除すると、自分の編集対象外であるPolicy本文(IC-018本文・§9参照リスト)、および他の複数のlesson(`verify-the-outside-of-a-claimed-boundary.md`等)・Incident記録・ADR-005から宙ぶらりん参照が生じる。これらはいずれも本Implementerの許可された変更範囲外。
- lesson自体の内容(3条件・4構成の実測結果・Bash全面禁止の理由)は、この環境固有の技術的知見として事実として妥当であり、実行主体がClaude Codeであった過去の記録として引き続き参照価値を持つ。

このため実装は行わず、現状維持とした。

## 波及の確認

- `docs/ai/core.md`、`docs/ai/roles/coordinator.md`、`docs/ai/role-context-matrix.md`、`docs/ai/context-classification.md`、`docs/ai/context/`配下を検索したが、「無人」「無人実行されるCoordinator」「claude -p」への言及は無し(波及なし)。
- `docs/ai/status.md`の「載せていないもの(判断の記録)」節に1件、`claude -p`への言及が残る(「月次評価のために、バンドル本文をその場で組み立てて`claude -p`へ渡すこと」— 2026-08-03にYoshinobuが却下した記録)。依頼文の対象は明示的に「Watch / Next行」であり、この節はいずれにも属さないため**変更していない**。この記録は「評価段が2026-08-03中にさらに全廃された」という、記録された時点より後の決定によって前提が二重に古くなっている可能性があるが、判断はCoordinatorへ委ねる。
- `roles/knowledge_review/`配下(`incident_evaluation.yml`、`job-settings.json.j2`、`incident-job-settings.json.j2`)がこの lesson ファイルをコメントで参照しているのを確認したが、コード側は別subagentが同時実装中のため一切触れていない。
- `git status`で確認した限り、自分の変更は上記4文書のみ。`docs/ai/policies/`、`roles/knowledge_review/`、`playbooks/knowledge_review.yml`はセッション開始前から差分があったが(他者の作業)、自分では一切変更していない。

## 自己検証(V1〜V4)

- V1: 4文書に対し`無人`/`claude -p`/`月次評価`を全文検索し、該当なし(クリーン)であることを確認済み。
- V2: 削除した「無人実行されるCoordinator」節への参照(完全一致文字列)が4文書内に残っていないことを確認済み。
- V3: 改訂後の記述(パイプライン=捕捉→一次調査→見直し(人)、LLMを使う段は一次調査のみ)が、改訂済みPolicyのIC-002/IC-005/IC-043/IC-044と矛盾しないことを文言レベルで確認済み。
- V4: `python3 scripts/check-doc-consistency.py`を実行し、`[check1] OK (100 compared)` `[check2] OK (8 compared)` `[check3] OK (91 compared)`で全件通過を確認済み。
- V5: 4文書への変更に経緯・改訂日・根拠引用を追加していない(削除・簡潔な言い換えのみ)。

## 未検証・未解決事項

- lessonファイルを残す判断はPolicy側の記述(IC-018が変更されていないこと)に基づく推論であり、Yoshinobu自身にこの整合を確認してもらってはいない。
- `docs/ai/status.md`「載せていないもの」節の`claude -p`言及(上記)の要否はCoordinator判断待ち。
- `roles/knowledge_review`・`playbooks/knowledge_review.yml`のコード側実装(別subagent)が完了した時点で、`docs/ai/memory-classification.md`の書き出し先記述(`docs/ai/memory/`・`docs/ai/context/`・`skills/`・`docs/ai/status.md`)が実装と一致するか、改めて突き合わせが必要。
