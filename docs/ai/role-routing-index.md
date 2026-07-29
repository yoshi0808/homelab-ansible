# Role / routing index

状態: **正本**(2026-07-26改訂: 常駐マルチプロセスtrio体制を廃止し、Coordinator単一セッション+on-demand subagent体制へ移行)

このindexは、identityからRole、実現方式、案件ownerを推測なしに解決するための正本である。Role本文(責任・権限・成果物・禁止事項)は複製せず、`docs/ai/roles/<role>.md`を参照する。

## 現行体制(2026-07-26〜)

常駐する識別子は`claude`(Coordinator、この対話セッション自身)のみである。Implementer / Reviewer / Tester / Auditorは常駐identityを持たず、CoordinatorがTierに応じてその場で実行する。

| Role | モデル | 実現方式 |
|---|---|---|
| Coordinator | **Opus以上を原則**(Tier 1/2の直接実装に限りSonnet可。2026-07-29、`docs/ai/reviews/process_retrospective/2026-07-29_008_coordinator_model_tier_policy.md`) | `claude`。Yoshinobuとの対話窓口、Tier判定、以下Roleの呼び出しと結果評価に加え、**Tier 3/4の要求分解・ADR・リスク整理・見積もりもCoordinator自身が行う**(2026-07-29、Tech Lead役廃止。`docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md`)。 |
| Implementer | **Sonnet** | Coordinatorがまとめたrequirement/分解案に基づき、Coordinatorが別途Agent toolでsubagentを起動する。`docs/ai/roles/implementer.md`の範囲(最小差分実装、commit/push禁止、本番適用禁止)は不変。 |
| Reviewer | **Sonnet** | 同様にCoordinatorが別のAgent tool subagentを起動する。Implementerを行ったsubagentとは別セッションとして起動し、独立性を保つ(`docs/ai/roles/reviewer.md`「自分が実装した変更を独立レビュー済みとして扱わない」を、同一subagentの使い回しをしないことで担保する)。**2026-07-29から、Tier 3/4のCoordinatorの計画査読も担う**(`docs/ai/roles/reviewer.md`「計画査読」)。 |
| Tester | **Sonnet** | 同様にCoordinatorが別のAgent tool subagentを起動する。実ホストへの`--check`/dry-run実行を含め、`docs/ai/roles/tester.md`の禁止事項(本番適用、`--check`なしのcheck-mode-native実行等)はそのまま適用される。 |
| **Auditor** | **Sonnet** | 2026-07-28新設。**Coordinatorが案件クローズ時に1回だけ**起動し(起動条件と手順は`docs/ai/roles/coordinator.md`。全単位が完了し`progress.md`と番号付き成果物が出揃った時点、`docs/ai/status.md`の該当行を消す前)、`docs/ai/roles/auditor.md`の範囲で「この記録から経緯を再構成できるか、辻褄は合っているか」を検査する。**入力はrepoの成果物のみで、Coordinatorの説明を受け取らない**(受け取ると自己申告の清書になる)。技術的な正否は判定しないが、**記録どうしの矛盾**は指摘する。走行中の工程管理は行わない。 |

### モデル・effort配分(2026-07-26確定)

**Coordinatorは`Opus`以上を原則とする**(「以上」は特定の1モデルへ固定しない)。**Tier判定そのもの、およびTier 3/4(要求分解・ADR・リスク整理・見積もり)はこの原則の例外を認めない。** Tier 1/2の直接実装(Coordinator自身がplaybook等を書く場面)に限り、Sonnetでもよい(2026-07-29 Yoshinobu明示、`docs/ai/reviews/process_retrospective/2026-07-29_008_coordinator_model_tier_policy.md`)。モデルの選択はYoshinobuが行い、難易度を高いと判断すればTier 1/2でも上位モデルを使ってよい。Implementer / Reviewer / TesterはSonnet。**subagentは指定しなければ親のモデルを継承する**ため、Sonnet側は明示指定が必要である。各Roleのモデルとeffortは`.claude/agents/<role>.md`のfrontmatter(`model:` / `effort:`)に固定してあり、Coordinatorが`subagent_type`でそれを指定すれば配分は自動的に守られる。

| Role | model | effort | 根拠 |
|---|---|---|---|
| Auditor | sonnet | medium | 2026-07-28追加。読むのはrepoの成果物のみで技術的な正否を判定しないため、推論深度を要さない。検査項目は`docs/ai/roles/auditor.md`§1に列挙済み。**「あるべきものが無い」ことの検出**が中核だが、コールドスタートで再構成を試みれば欠落は詰まりとして現れるため、列挙とこの手順でSonnetに足りる |
| Implementer | sonnet | high | 実装は本番影響のある差分を作る唯一のRoleであり、ここは下げない |
| Reviewer | sonnet | **medium** | Opus 5世代のガイドが「レビュー精度は低effortでも保たれる」と明示。2026-07-26に試行開始。**2026-07-29から計画査読(旧・2人目のTech Leadがopus/highで担っていた層2の技術的前提の反証を含む)も同じeffortで担う** — mediumで層2相当の反証を確実にこなせるかは新しい観測対象であり、findings品質の低下が見えたら見直す |
| Tester | sonnet | **medium** | 検証は実行と観測が主で、推論深度より実行経路を通すことが品質を決める。同日試行開始 |

Reviewer / Testerのmediumは**試行中の設定**である。Tier 4の逐行照合でfindings品質の低下が観測された場合は`high`へ戻す。Implementerを既定のままにしているのは、品質変化が出たときに原因をReviewer / Tester側へ切り分けられるようにするためである。

根拠: 2026-07-26のTier 4フルサイクル(proxmox_patch_dryrun単一ノード対応)は、Implementer / Reviewer / Testerが実質すべてSonnetで走り、apply安全ゲートの保護漏れ、両ノード健全時のNoneクラッシュ、終了コード4の運用問題、その修正が1行では悪化する罠、の4件を本番影響前に検出した。一方でOpus級の判断が要ったのは「あるべきものが無い」ことの検出(`docs/ai/core.md`が旧モデルのまま残っていたドリフト、決定根拠がリポジトリに存在しなかった欠落)であり、いずれもCoordinatorの領分だった。

### Agent定義との関係

`.claude/agents/<role>.md`はClaude Code harness向けの**実行機構**(モデル指定と、subagent固有の運用事情)だけを持つ。役割の規範 — 責任・権限・成果物・禁止事項 — は`docs/ai/roles/<role>.md`が正本であり、agent定義へ複製しない。`CLAUDE.md`が共通原則を複製しないのと同じ理由で、正本が二重化するとドリフトする。

Tier 1/2はこれまで通りCoordinator自身が実装し、Tier 2のみTester相当のsubagentへ実ホスト検証を依頼する(`skills/delegation-tier/SKILL.md`)。

**セッション途中に作成した定義が登録されるかは、harnessの版に依存する。** 2026-07-26には登録されず`subagent_type`指定が失敗したが、2026-07-28の`pmo`追加では**同一セッション中に登録された**(harnessが新Role追加を通知してきた。**なおこの`pmo`役自体は同日中に退役しており、現存しない** — ここで示しているのは登録挙動の実例である)。したがって「次のセッションまで使えない」とも「すぐ使える」とも決め打ちしないこと。新規Roleを追加したら、**実地の案件に組み込む前に一度起動して確かめる**。`effort:`等の既存値の変更が即時反映されるかは未確認である。

### 無人実行されるCoordinator(2026-07-27〜)

上表のCoordinatorは対話セッションだが、**対話相手を持たないCoordinatorが1つだけ存在する**。ansyのsystemd timer `ansible-knowledge-review.timer`が毎月26日に`playbooks/knowledge_review.yml`を起動し、`claude -p`が月次Knowledge振り返り(仕分け・昇格判断)を無人で実行する。手順の正本は`docs/ai/memory-classification.md`「月次振り返りの対象と手順」。

対話セッションのCoordinatorと異なり、この実行形態には読み書き範囲を絞る技術的な制約が課してある。**制約の仕組み・根拠・実測結果の正本は`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`**であり、本節は現在の許可範囲(実現方式)だけを要約する。この節を読む必要があるのは、`roles/knowledge_review`の権限プロファイルを変更するとき、または無人実行の挙動を調べるときに限る。Role文書の整合性を点検するときは、この形態も対象に含めること。

| 項目 | 無人Coordinator |
|---|---|
| 起動 | systemd timer(ansy専用。auto-memoryがansyにしか無いため) |
| 判断の委譲先 | 無し。subagentを起動せず単独で完結する |
| 書込可(allowlist方式) | `docs/ai/memory/`、`docs/ai/context/`、`skills/` の3つ**のみ**(実装: `roles/knowledge_review/templates/job-settings.json.j2`) |
| 読取可 | `docs/`、`skills/`、`--add-dir`で渡したauto-memoryのみ。それ以外は拒否 |
| Bash | 禁止 |
| auto-memory | **読み取りのみ**。repo外への書込はこの構成では許可できない。縮約が必要な項目は報告に列挙し、後で対話セッションかYoshinobuが行う |
| commit/push | しない。差分は作業ツリーに残しYoshinobuがcommitする |
| 中止条件 | 作業ツリーが汚れているとき(起動側のAnsibleが判定) |

## 旧体制(2026-05〜2026-07-26、廃止。経緯確認のときだけ読めばよく、現行運用には不要)

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
