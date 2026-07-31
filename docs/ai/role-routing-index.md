# Role / routing index

状態: **正本**

このindexは、identityからRole、実現方式、案件ownerを推測なしに解決するための正本である。Role本文(責任・権限・成果物・禁止事項)は複製せず、`docs/ai/roles/<role>.md`を参照する。

## 現行体制

常駐する識別子は`claude`(Coordinator、この対話セッション自身)のみである。Implementer / Reviewer / Tester / AuditorはCoordinatorが必要と判断したときにその場で起動する。

| Role | モデル | 実現方式 |
|---|---|---|
| Coordinator | **Opus以上を原則**(軽い直接実装に限りSonnet可) | `claude`。Yoshinobuとの対話窓口。要求分解・ADR・リスク整理・見積もり・分解方針の確定と、以下Roleの呼び出しおよび結果評価を自身で行う。**どこまで分解し誰へ委任するかはCoordinatorの裁量である**(2026-07-31、Yoshinobu明示) |
| Implementer | **Sonnet** | Coordinatorがまとめたrequirement/契約に基づき、Agent toolでsubagentとして起動する。`docs/ai/roles/implementer.md`の範囲(最小差分実装、commit/push禁止、本番適用禁止)は不変 |
| Reviewer | **Sonnet** | 別のsubagentとして起動する。Implementerを行ったsubagentとは別セッションとして起動し、独立性を保つ(`docs/ai/roles/reviewer.md`「自分が実装した変更を独立レビュー済みとして扱わない」を、同一subagentを使い回さないことで担保する)。計画の査読も担う |
| Tester | **Sonnet** | 別のsubagentとして起動する。実ホストへの`--check`/dry-run実行を含め、`docs/ai/roles/tester.md`の禁止事項(本番適用、`--check`なしのcheck-mode-native実行等)がそのまま適用される |
| **Auditor** | **Sonnet** | **Coordinatorが案件クローズ時に1回だけ**起動し、`docs/ai/roles/auditor.md`の範囲で「この記録から経緯を再構成できるか、辻褄は合っているか」を検査する。**入力はrepoの成果物のみで、Coordinatorの説明を受け取らない**(受け取ると自己申告の清書になる)。技術的な正否は判定しないが、**記録どうしの矛盾**は指摘する |

### モデル・effort配分

**Coordinatorは`Opus`以上を原則とする**(「以上」は特定の1モデルへ固定しない)。モデルの選択はYoshinobuが行う。Implementer / Reviewer / TesterはSonnet。**subagentは指定しなければ親のモデルを継承する**ため、Sonnet側は明示指定が必要である。各Roleのモデルとeffortは`.claude/agents/<role>.md`のfrontmatter(`model:` / `effort:`)に固定してあり、Coordinatorが`subagent_type`でそれを指定すれば配分は自動的に守られる。

| Role | model | effort | 根拠 |
|---|---|---|---|
| Auditor | sonnet | medium | 読むのはrepoの成果物のみで技術的な正否を判定しないため、推論深度を要さない。検査項目は`docs/ai/roles/auditor.md`§1に列挙済み |
| Implementer | sonnet | high | 実装は本番影響のある差分を作る唯一のRoleであり、ここは下げない |
| Reviewer | sonnet | **medium** | Opus 5世代のガイドが「レビュー精度は低effortでも保たれる」と明示。計画査読も同じeffortで担う。**2026-08-01に試行を終了し確定した**(下記) |
| Tester | sonnet | **medium** | 検証は実行と観測が主で、推論深度より実行経路を通すことが品質を決める。**同上** |

**mediumの試行は2026-08-01に終了し、そのまま確定した。** 判断の根拠は `incident_investigate_trigger` 案件での実績である — Reviewerは、走査の起点で例外を握りつぶし「未調査バンドルが無かった」と区別できなくなる退行(削除された旧コードとの比較を要する指摘)を検出した。Testerは、実装記録が書いていた検証手段が技術的に成立しないこと(`chmod 000` したファイルへの `stat` は `PermissionError` にならない)を独立に見抜き、正しい手段で再現し直した。**いずれも逐行照合と、先行成果物の主張を現物で確かめる作業であり、mediumで品質が落ちる懸念の中心だった部分**である。品質低下が見えたら`high`へ戻す方針自体は維持する。

Implementerを既定のままにしているのは、品質変化が出たときに原因をReviewer / Tester側へ切り分けられるようにするためである。

subagentをSonnetで回して本番影響前に実バグを検出できた実績がある一方、Opus級の判断が要るのは「あるべきものが無い」ことの検出(規範のドリフト、決定根拠がリポジトリに存在しない欠落)であり、それはCoordinatorの領分である。

### Agent定義との関係

`.claude/agents/<role>.md`はClaude Code harness向けの**実行機構**(モデル指定と、subagent固有の運用事情)だけを持つ。役割の規範 — 責任・権限・成果物・禁止事項 — は`docs/ai/roles/<role>.md`が正本であり、agent定義へ複製しない。正本が二重化するとドリフトする。

**セッション途中に作成した定義が登録されるかは、harnessの版に依存する。** 登録された実例も、されなかった実例もある。新規Roleを追加したら、実地の案件に組み込む前に一度起動して確かめる。

### 無人実行されるCoordinator

上表のCoordinatorは対話セッションだが、**対話相手を持たないCoordinatorが1つだけ存在する**。ansyのsystemd timer `ansible-knowledge-review.timer`が毎月26日に`playbooks/knowledge_review.yml`を起動し、`claude -p`が月次Knowledge振り返り(仕分け・昇格判断)を無人で実行する。手順の正本は`docs/ai/memory-classification.md`「月次振り返りの対象と手順」。

この実行形態には読み書き範囲を絞る技術的な制約が課してある。**制約の仕組み・根拠・実測結果の正本は`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`**であり、本節は現在の許可範囲だけを要約する。この節を読む必要があるのは、`roles/knowledge_review`の権限プロファイルを変更するとき、または無人実行の挙動を調べるときに限る。Role文書の整合性を点検するときは、この形態も対象に含めること。

| 項目 | 無人Coordinator |
|---|---|
| 起動 | systemd timer(ansy専用。auto-memoryがansyにしか無いため) |
| 判断の委譲先 | 無し。subagentを起動せず単独で完結する |
| 書込可(allowlist方式) | `docs/ai/memory/`、`docs/ai/context/`、`skills/` の3つ**のみ**(実装: `roles/knowledge_review/templates/job-settings.json.j2`) |
| 読取可 | `docs/`、`skills/`、`roles/`、`playbooks/`、`inventories/homelab/`(`inventories/vars/`は不可)、`--add-dir`で渡したauto-memoryのみ。それ以外は拒否 |
| Bash | 禁止 |
| auto-memory | **読み取りのみ**。repo外への書込はこの構成では許可できない。縮約が必要な項目は報告に列挙し、後で対話セッションかYoshinobuが行う |
| commit/push | しない。差分は作業ツリーに残しYoshinobuがcommitする |
| 中止条件 | 作業ツリーが汚れているとき(起動側のAnsibleが判定) |

## 証跡の扱い

実質的な証跡は、subagentとのやりとりそのものではなく`docs/ai/reviews/<target>/`配下のファイル(requirement / plan / implement / review / test_result / audit、該当すれば`docs/ai/adr/`)である。subagentを使う案件では、要求分解・実装差分・レビュー所見・検証結果を必ずこれらのファイルとして残す。subagent自身の思考過程・対話ログは永続化されない前提とし、判断の根拠は成果物ファイルに書き切る。

## 正本の優先順位

競合時は、情報の種類ごとに次を使う。Yoshinobuの当該案件に対する最新の明示指示が常に最優先である。

| 情報 | 優先する正本 | fallback |
|---|---|---|
| 全Role共通原則・安全境界 | `docs/ai/core.md` | なし |
| **現在地**(進行中・観測待ち・着手候補) | `docs/ai/status.md` | なし。Coordinatorのauto-memoryは正本ではない |
| identity → Role対応、Role実現方式 | 本index | なし |
| Role本文(責任・権限・成果物・禁止事項) | `docs/ai/roles/<role>.md` | 本indexの要約 |
| 案件固有の要求・成果物 | 指定された`docs/ai/reviews/<target>/` | 関係しそうなreviewsを無差別に探索しない |
| 対象システム固有の判断 | `docs/ai/policies/*_policy.md` | なし |

## 作業開始時の解決手順

1. `docs/ai/core.md`を読む。
2. `docs/ai/roles/<role>.md`で自分のRoleを確認する。対話セッションのCoordinatorは`docs/ai/status.md`で現在地も確認する(SessionStart hook `scripts/session-context.sh`が自動で載せる)。
3. 本indexで自分のRoleの実現方式を確認する。
4. Coordinatorは、どこまで分解し誰へ委任するかを決める。subagentへ渡すときは`docs/ai/roles/<role>.md`を読み込ませて起動する。
5. 案件固有の成果物は指定された`docs/ai/reviews/<target>/`だけを読む。
6. コード、`git status`、diffで現在の事実を確認する。
