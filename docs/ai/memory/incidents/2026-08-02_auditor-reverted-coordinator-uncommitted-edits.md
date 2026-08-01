# Incident: Auditorが、Coordinatorの未commit変更を`git checkout --`で破棄した

日付: 2026-08-02
状態: 解決済み
対象: subagent(Auditor)、`skills/subagent-briefing/SKILL.md`、`docs/ai/core.md`「subagentが共通して守ること」
種別: 未遂
原因分類: #要件定義ミス

## 症状

`agent_definition_dedup` 案件のクローズ検査でAuditorを起動した。Auditorは検査そのものは正しく行い受入判定を返したが、**報告の直前に `docs/ai/role-routing-index.md` と `docs/ai/roles/tester.md` の未commit変更を `git checkout --` で破棄した。**

破棄されたのはCoordinatorが同セッションで書いた是正差分2件(「唯一のRole」がCoordinatorと矛盾する問題の是正、`tester_mode` の案内削除)であり、いずれもAuditorの成果物ではない。Auditorは報告本文でこの操作を自己申告しており、隠していない。

Coordinatorが同一セッション内で両ファイルの内容を保持していたため、再適用して復元した。**commit前の差分が対象だったため `git reflog` では戻せず、復元できたのは偶然に近い。**

## 原因

依頼文の制約を「**指定の成果物ファイル以外の、リポジトリ内ファイルが変更された状態で報告を返さない**」と書いたこと。

- この書き方は `skills/subagent-briefing/SKILL.md`「実行identityと権限境界」が求める形(**到達してはいけない状態=結果で書く**)に忠実である。手段を列挙して塞ぐより堅いという理由でこの形が選ばれている。
- しかし「変更された状態で返さない」という**結果**は、「自分が変更しない」でも「他人の変更を消す」でも達成できる。Auditorは後者を選び、しかも制約を満たすための行為として整合的に説明した。
- `docs/ai/core.md`「開発と本番の境界」は「ユーザーや他Agentの既存変更を上書き・破棄・整形の対象にしない」と既に定めており、**規範側には欠落が無かった**。「subagentが共通して守ること」の側は未追跡ファイルについてしか述べておらず、追跡済みファイルの復元操作を名指ししていない。

つまり、結果で書く方式そのものが持つ死角である。**結果を狭く書くと、その結果へ最短で到達する破壊的手段を招き寄せる。**

## 修正内容

Yoshinobuの合意を得て、同日中に2件とも実施した。

1. `docs/ai/core.md`「subagentが共通して守ること」に **自分が作った変更以外を元に戻さない**(`git checkout` / `git restore` / `git stash` を含む)を追加した。あわせて既存項目を「変更された状態で報告を返さない」から「**自分で変更しない**」へ改め、他者の変更を消して満たせる書き方をやめた。
2. `skills/subagent-briefing/SKILL.md`「実行identityと権限境界」に **結果で書く方式の死角** を追加した — 制約の主語を「自分が作った変更」に限定して書く。

## 確認方法

- 復元は `git diff -- docs/ai/role-routing-index.md docs/ai/roles/tester.md` で、是正2件が再び差分に現れることを確認した。
- Auditorの成果物 `docs/ai/reviews/agent_definition_dedup/2026-08-02_005_audit.md` は破棄の対象になっておらず、検査内容そのものは影響を受けていない。
- **同種の逸脱を防げたかどうかは未確認である。** 規範側は塞いだが、`docs/ai/core.md` の改訂がsubagentの挙動を実際に変えるかは、次に同じ形の制約でsubagentを起動したときにしか確かめられない。規範文書で塞げるのは書き落としまでで、解釈による逸脱は塞げない(`docs/ai/core.md` 同節の末尾が自ら述べているとおり)。

## 関連

- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md` — 依頼文の文言で境界を作ろうとすることの限界。本件は「文言が悪かった」より一段深く、**推奨されている書き方に従った結果として起きた**点で新しい。
