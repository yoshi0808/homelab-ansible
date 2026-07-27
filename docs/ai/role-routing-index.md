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
| **PMO** | **Sonnet** | 2026-07-27新設。Tier 3以上でCoordinatorが計画を決め切った後に起動し、`docs/ai/roles/pmo.md`の範囲で工程の組み立て・計画レビュー(60分/30分の単位基準と未決定数)・進捗と逸脱の検出・課題管理、および**Coordinator自身の工程遵守の点検**を行う。**技術的な判断・解決は一切しない。** 入力はリポジトリ(計画、`status.md`、案件フォルダ、`effort-baseline.md`)のみでコールドスタートに耐える設計。**ただし2026-07-27時点で `.claude/agents/pmo.md` が未作成のため、`subagent_type: pmo` での起動はまだできない**(`docs/ai/roles/pmo.md`「実行機構」)。それまではCoordinatorが代行する。 |

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

### 無人実行されるCoordinator(2026-07-27〜)

上表のCoordinatorは対話セッションだが、**対話相手を持たないCoordinatorが1つだけ存在する**。ansyのsystemd timer `ansible-knowledge-review.timer`が毎月26日に`playbooks/knowledge_review.yml`を起動し、`claude -p`が月次Knowledge振り返り(仕分け・昇格判断)を無人で実行する。手順の正本は`docs/ai/memory-classification.md`「月次振り返りの対象と手順」。

対話セッションのCoordinatorと異なり、この実行形態には次の制約が技術的に課してある。Role文書の整合性を点検するときは、この形態も対象に含めること。

| 項目 | 無人Coordinator |
|---|---|
| 起動 | systemd timer(ansy専用。auto-memoryがansyにしか無いため) |
| 判断の委譲先 | 無し。subagentを起動せず単独で完結する |
| 書込可 | `docs/ai/memory/`、`docs/ai/context/`、`skills/` の3つ**のみ** |
| 書込不可 | **上記以外すべて**。専用の権限プロファイル(`roles/knowledge_review/templates/job-settings.json.j2`)によるallowlist方式で、許可した3パス以外への書込はharnessが拒否する |
| 読取可 | `docs/`、`skills/`、および`--add-dir`で渡したauto-memoryのみ。**それ以外は拒否**(作業ディレクトリ外を含む) |
| auto-memory | **読み取りのみ**。repo外への書込はこの構成では許可できないため、無人実行が触れない。縮約が必要な項目は報告に列挙し、後で対話セッションかYoshinobuが行う |
| Bash | 禁止。Write のpath制限をshell経由で迂回させないため |
| commit/push | しない。差分は作業ツリーに残しYoshinobuがcommitする |
| 中止条件 | 作業ツリーが汚れているとき(起動側のAnsibleが判定) |
| 期日更新 | `MEMORY.md`の期日行は起動側のAnsibleが更新する(LLMは書けない) |

**denylist方式は採用していない。** 当初`--disallowedTools`で禁止パスを列挙したが、2026-07-27の独立レビューが実機で検証し、**列挙から漏れた`CLAUDE.md`・`AGENTS.md`・`docs/ai/`直下の正本群・`docs/ai/reviews/`の計9ファイルへ実際に書き込めた**。列挙漏れは列挙した本人には見えないため、「許可した場所以外は全部拒否」の向きに反転させてある。

この封じ込めは次の3条件が**同時に**成立して初めて機能する(いずれか欠けると崩れることを実測で確認済み)。変更する際は3つまとめて確認すること。

なお**読取も同じ理由で絞ってある**。bareな`Read`を許すとansyユーザーが読める全ファイル(vaultのパスワードファイル、SSHキー等)へ到達でき、書込先が公開repoのgit管理下であることと組み合わさると機密混入の経路になる。書込側だけを塞いでも封じ込めは片側にしかならない。

1. 権限ルールのpathは**相対表記**。絶対表記だとルールが照合されず全拒否になる
2. `--permission-mode acceptEdits` を**付けない**。付けると作業ディレクトリ内の編集が無条件承認され、path指定が無効化される
3. `--setting-sources` を**空**にする。repoの`.claude/settings.json`(`Write(./**)`)が載ると素通りする

## 旧体制(2026-05〜2026-07-26、廃止)

以前は`techlead`/`implementer`/`reviewer`/`tester`(無印trio、Claude Codeベース、tmux常駐)と`techlead2`/`implementer2`/`reviewer2`/`tester2`(2付きtrio、Codexベース、techlead2はネイティブアプリ常駐)が、agmsgでCoordinatorおよび相互に非同期メッセージを送り合う常駐マルチプロセス体制だった。2026-07-26、処理速度(cross-process遅延、tmux ASK承認の手動待ち)を理由にCodexは本プロジェクトから外れ、あわせて常駐trio体制自体(Claude Codeベースの無印trioを含む)も廃止した。理由と経緯は`project_agmsg_to_subagent_transition`(Claude Memory、2026-07-26)を参照。

## 証跡の扱い(体制に依存しない不変の規律)

旧体制での実質的な証跡は、agmsgのメッセージ履歴そのものではなく`docs/ai/reviews/<target>/`配下のrequirement / implement(またはADR) / review / test_plan / test_resultファイルだった。この規律は体制変更後も継続する。Tier 3/4のsubagentは、要求分解・実装差分・レビュー所見・検証結果を必ず`docs/ai/reviews/<target>/`(該当すれば`docs/ai/adr/`)へファイルとして残す。subagent自身の思考過程・対話ログは永続化されない前提とし、判断の根拠は成果物ファイルに書き切る。

## 正本の優先順位

競合時は、情報の種類ごとに次を使う。Yoshinobuの当該案件に対する最新の明示指示が常に最優先である。

| 情報 | 優先する正本 | fallback |
|---|---|---|
| 全Role共通原則・安全境界 | `docs/ai/core.md` | なし |
| **現在地**(進行中・観測待ち・着手候補) | `docs/ai/status.md` | なし。Coordinatorのauto-memoryは正本ではない |
| identity → Role対応、Role実現方式 | 本index | なし |
| Role本文(責任・権限・成果物・禁止事項) | `docs/ai/roles/<role>.md` | 本indexの要約 |
| Tierと呼び出し方針 | `skills/delegation-tier/SKILL.md` | 本index |
| 案件固有の要求・成果物 | 指定された`docs/ai/reviews/<target>/` | 関係しそうなreviewsを無差別に探索しない |
| 対象システム固有の判断 | `docs/ai/policies/*_policy.md` | なし |

## 作業開始時の解決手順

1. `docs/ai/core.md`を読む。対話セッションのCoordinatorは`docs/ai/status.md`で現在地も確認する(SessionStart hook `scripts/session-context.sh`が自動で載せる)。
2. Tierを判定する(`skills/delegation-tier/SKILL.md`)。
3. Tier 3/4なら、該当Roleの`docs/ai/roles/<role>.md`を読み込ませたAgent tool subagentを起動する。Tier 1/2はCoordinator自身が実装する。
4. 案件固有の成果物は指定された`docs/ai/reviews/<target>/`だけを読む。
5. コード、`git status`、diffで現在の事実を確認する。
