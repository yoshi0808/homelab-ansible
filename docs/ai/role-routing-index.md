# Role / routing index

状態: **正本**(2026-07-26改訂: 常駐マルチプロセスtrio体制を廃止し、Coordinator単一セッション+on-demand subagent体制へ移行)

このindexは、identityからRole、実現方式、案件ownerを推測なしに解決するための正本である。Role本文(責任・権限・成果物・禁止事項)は複製せず、`docs/ai/roles/<role>.md`を参照する。

## 現行体制(2026-07-26〜)

常駐する識別子は`claude`(Coordinator、この対話セッション自身)のみである。Tech Lead / Implementer / Reviewer / Testerは常駐identityを持たず、CoordinatorがTierに応じてその場で実行する。

| Role | モデル | 実現方式 |
|---|---|---|
| Coordinator | Opus | `claude`。Yoshinobuとの対話窓口、Tier判定、以下Roleの呼び出しと結果評価を行う本セッション自身。 |
| Tech Lead | **Opus** | Tier 3/4の案件でCoordinatorがAgent tool(Task)でsubagentを起動し、`docs/ai/roles/techlead.md`の責任・権限・禁止事項の範囲で要求分解・ADR・リスク整理・Implementer/Reviewer/Tester分解案の作成までを行わせる。Tech Lead subagent自身は実装しない(役割定義は不変)。 |
| Implementer | **Sonnet** | Tech Lead(subagentまたはCoordinator自身)がまとめたrequirement/分解案に基づき、Coordinatorが別途Agent toolでsubagentを起動する。`docs/ai/roles/implementer.md`の範囲(最小差分実装、commit/push禁止、本番適用禁止)は不変。 |
| Reviewer | **Sonnet** | 同様にCoordinatorが別のAgent tool subagentを起動する。Implementerを行ったsubagentとは別セッションとして起動し、独立性を保つ(`docs/ai/roles/reviewer.md`「自分が実装した変更を独立レビュー済みとして扱わない」を、同一subagentの使い回しをしないことで担保する)。 |
| Tester | **Sonnet** | 同様にCoordinatorが別のAgent tool subagentを起動する。実ホストへの`--check`/dry-run実行を含め、`docs/ai/roles/tester.md`の禁止事項(本番適用、`--check`なしのcheck-mode-native実行等)はそのまま適用される。 |

### モデル・effort配分(2026-07-26確定)

CoordinatorとTech LeadはOpus、Implementer / Reviewer / TesterはSonnet。**subagentは指定しなければ親のモデルを継承する**ため、Sonnet側は明示指定が必要である。各Roleのモデルとeffortは`.claude/agents/<role>.md`のfrontmatter(`model:` / `effort:`)に固定してあり、Coordinatorが`subagent_type`でそれを指定すれば配分は自動的に守られる。

| Role | model | effort | 根拠 |
|---|---|---|---|
| Tech Lead | opus | high | 要求分解・ADR・リスク整理は意味判断が支配的。既定値を明示しているだけで、下げていない |
| Implementer | sonnet | high | 実装は本番影響のある差分を作る唯一のRoleであり、ここは下げない |
| Reviewer | sonnet | **medium** | Opus 5世代のガイドが「レビュー精度は低effortでも保たれる」と明示。2026-07-26に試行開始 |
| Tester | sonnet | **medium** | 検証は実行と観測が主で、推論深度より実行経路を通すことが品質を決める。同日試行開始 |

Reviewer / Testerのmediumは**試行中の設定**である。Tier 4の逐行照合でfindings品質の低下が観測された場合は`high`へ戻す。Implementer / Tech Leadを既定のままにしているのは、品質変化が出たときに原因をReviewer / Tester側へ切り分けられるようにするためである。

根拠: 2026-07-26のTier 4フルサイクル(proxmox_patch_dryrun単一ノード対応)は、Implementer / Reviewer / Testerが実質すべてSonnetで走り、apply安全ゲートの保護漏れ、両ノード健全時のNoneクラッシュ、終了コード4の運用問題、その修正が1行では悪化する罠、の4件を本番影響前に検出した。一方でOpus級の判断が要ったのは「あるべきものが無い」ことの検出(`docs/ai/core.md`が旧モデルのまま残っていたドリフト、決定根拠がリポジトリに存在しなかった欠落)であり、いずれもCoordinatorの領分だった。

### Agent定義との関係

`.claude/agents/<role>.md`はClaude Code harness向けの**実行機構**(モデル指定と、subagent固有の運用事情)だけを持つ。役割の規範 — 責任・権限・成果物・禁止事項 — は`docs/ai/roles/<role>.md`が正本であり、agent定義へ複製しない。`CLAUDE.md`が共通原則を複製しないのと同じ理由で、正本が二重化するとドリフトする。

Tier 1/2はこれまで通りCoordinator自身が実装し、Tier 2のみTester相当のsubagentへ実ホスト検証を依頼する(`skills/delegation-tier/SKILL.md`)。

## 旧体制(2026-05〜2026-07-26、廃止)

以前は`techlead`/`implementer`/`reviewer`/`tester`(無印trio、Claude Codeベース、tmux常駐)と`techlead2`/`implementer2`/`reviewer2`/`tester2`(2付きtrio、Codexベース、techlead2はネイティブアプリ常駐)が、agmsgでCoordinatorおよび相互に非同期メッセージを送り合う常駐マルチプロセス体制だった。2026-07-26、処理速度(cross-process遅延、tmux ASK承認の手動待ち)を理由にCodexは本プロジェクトから外れ、あわせて常駐trio体制自体(Claude Codeベースの無印trioを含む)も廃止した。理由と経緯は`project_agmsg_to_subagent_transition`(Claude Memory、2026-07-26)を参照。

## 証跡の扱い(体制に依存しない不変の規律)

旧体制での実質的な証跡は、agmsgのメッセージ履歴そのものではなく`docs/ai/reviews/<target>/`配下のrequirement / implement(またはADR) / review / test_plan / test_resultファイルだった。この規律は体制変更後も継続する。Tier 3/4のsubagentは、要求分解・実装差分・レビュー所見・検証結果を必ず`docs/ai/reviews/<target>/`(該当すれば`docs/ai/adr/`)へファイルとして残す。subagent自身の思考過程・対話ログは永続化されない前提とし、判断の根拠は成果物ファイルに書き切る。

## 正本の優先順位

競合時は、情報の種類ごとに次を使う。Yoshinobuの当該案件に対する最新の明示指示が常に最優先である。

| 情報 | 優先する正本 | fallback |
|---|---|---|
| 全Role共通原則・安全境界 | `docs/ai/core.md` | なし |
| identity → Role対応、Role実現方式 | 本index | なし |
| Role本文(責任・権限・成果物・禁止事項) | `docs/ai/roles/<role>.md` | 本indexの要約 |
| Tierと呼び出し方針 | `skills/delegation-tier/SKILL.md` | 本index |
| 案件固有の要求・成果物 | 指定された`docs/ai/reviews/<target>/` | 関係しそうなreviewsを無差別に探索しない |
| 対象システム固有の判断 | `docs/ai/policies/*_policy.md` | なし |

## 作業開始時の解決手順

1. `docs/ai/core.md`を読む。
2. Tierを判定する(`skills/delegation-tier/SKILL.md`)。
3. Tier 3/4なら、該当Roleの`docs/ai/roles/<role>.md`を読み込ませたAgent tool subagentを起動する。Tier 1/2はCoordinator自身が実装する。
4. 案件固有の成果物は指定された`docs/ai/reviews/<target>/`だけを読む。
5. コード、`git status`、diffで現在の事実を確認する。
