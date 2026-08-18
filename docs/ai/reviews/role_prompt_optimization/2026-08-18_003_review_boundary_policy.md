# Code Review: `docs/ai/policies/execution_boundary_policy.md` 新設(実行境界の集約)

## Summary

複数の規範文書に分散していた「実ホストへ何を実行してよいか」の答えを `docs/ai/policies/execution_boundary_policy.md` 1本へ集約した未commit差分をレビューした。移設前(`git show HEAD:<path>`)と移設後を項目単位で突き合わせた結果、**規範の消失は無い**。読み手へ届く仕掛け(CLAUDE.md / core.md / role-context-matrix.mdの3層)は機能する形で入っている。宙ぶらりん参照・層の整合にも問題は無い。Minor 3件(うち1件はdiff対象外ファイルの残存参照)を指摘する。

## 移設対応表(規範の消失が無いことの根拠)

移設元の記述単位ごとに、新Policyのどのマーカー(`<!-- EXEC-nnn -->`)へ対応するかを突き合わせた。「等価」は文言の言い換えはあっても義務・禁止・例外の実体が変わっていないことを、両ファイルの現物を開いて確認したことを意味する。

| # | 移設元(旧) | 移設元の記述 | 移設先 EXEC-nnn | 判定 |
|---|---|---|---|---|
| 1 | `coordinator.md`旧「実ホストへの非冪等操作の承認」 | 判断軸「Policyの許可・禁止・停止条件に触れるか」 | EXEC-001 | 等価 |
| 2 | 同上 | 「実効的な境界は能力の不在で作られている」(ansyが認証情報を持たない5ホスト) | EXEC-002 | 等価 |
| 3 | 同上 | 「境界はホストで引く。書き込むかどうかでは引かない」+ monnie/ansy/sandbox の位置づけ | EXEC-010 | 等価(§2表へ構造化) |
| 4 | 同上 | 「`sandbox`は壊れてよいものとして用意されている」(Yoshinobu、2026-08-06) | EXEC-011 | 等価 |
| 5 | 同上 | 「この境界は`autoMode`と対応させて維持する(片方だけ変えるとドリフトする)」 | EXEC-012 | 等価 |
| 6 | 同上 | 承認区分表8行(git commit/push、Policy改訂、保護対象ホスト、到達手段が無いホスト、上記以外、冪等カタログ追加、systemd timer/service、soft_deny/hard_deny) | EXEC-030 | 等価(8行とも1:1対応、ホスト名は§2表へ集約) |
| 7 | 同上 | 「状態を変えない確認はどのホストでも確認不要」「冪等であることは根拠にならない」 | EXEC-040 / EXEC-041 | 等価 |
| 8 | 同上 | 「提示不要」列挙(healthcheck / `--syntax-check` / `--check` / decoy / ansyワークツリー・`/tmp` / localhost使い捨てplaybook) | EXEC-042 | 等価 |
| 9 | 同上 | 「届かないホストではdispatchの名前付きチェックのみ」「カタログに無いときはOperator Request Channelへ」 | EXEC-043 | 等価 |
| 10 | 同上 | 「迷ったら上げてよい。ただし必ず推奨を添える」 | EXEC-061 | 等価(coordinator.md側にも短縮形が残存、下記Suggestion #1参照ではなく別件) |
| 11 | `core.md`§人間の権限と安全境界 | 「patch/reboot/restart/…を暗黙の承認や推測で実行しない」「判断の3分類はcoordinator.md『実ホストへの非冪等操作の承認』を正本とする」 | EXEC-001と統合 | 等価(参照先のみpolicyへ付け替え) |
| 12 | 同上 | 「打鍵を伴う承認の入口を増やさない」全文 | EXEC-060 | 等価(ただしcore.mdにも同文が残存。Suggestion #1) |
| 13 | `core.md`§subagentが共通して守ること | 「実ホストへ触れてよい範囲は自分のRole文書が定める」+「実ホストへ触れないRoleでも次の3つは実行してよい」(`--syntax-check`等/decoy/ansyワークツリー・`/tmp`) | EXEC-051 | 等価 |
| 14 | `tester.md`旧「使ってよい検証環境」 | decoy inventory / `ansy`のSemaphore / `sandbox` VM の到達可否・用途3行表 | EXEC-052 | 等価(表の文言はほぼ逐語一致) |
| 15 | `tester.md`旧「禁止事項」 | 「保護対象ホストへの非冪等操作は着手前に計画をCoordinatorへ提示」 | EXEC-050(Tester行) | 等価 |
| 16 | `tester.md`旧「禁止事項」 | 「実行identityを昇格しない。`sudo --become-user`等で別のidentityを引き受けない…」 | EXEC-082 | 等価(逐語一致) |
| 17 | `implementer.md`旧「禁止事項」 | 「実ホストへansibleを実行しない(状態を変えない確認も含む)」の実行範囲の参照先 | EXEC-050(Implementer行) | 等価 |
| 18 | `reviewer.md`旧「禁止事項」 | 同上(Reviewer側) | EXEC-050(Reviewer行) | 等価 |

**新規に追加された規範として識別したもの**(移設元に対応が無い): EXEC-020(§3「対応するPlaybookとの直交関係」の説明文)。これはPolicy標準テンプレート(§1-8構成)の§3を埋めるための記述で、既存運用と矛盾する内容ではないが、6箇所のどこにも同旨の明文は無かった。Suggestion #2として扱う。

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/core.md` | 27 | 「打鍵を伴う承認の入口を増やさない」段落が、新設Policy §5(EXEC-060)とほぼ同文のままcore.mdにも残っている。「1本へ集約した」という変更履歴(execution_boundary_policy.md v1.0)の趣旨に対し、この1項目だけ二重管理のまま残存しており、将来の改訂で片方だけ直る形の実質的ドリフト経路になりうる。 | 規範の重複(消失ではない) |
| 2 | `docs/ai/policies/execution_boundary_policy.md` | 35(EXEC-020) | 「本書と`ansible_test_safety_policy.md`は直交する」という関係性の明文は、移設元6箇所のどこにも存在しなかった新規記述。内容自体は既存運用と矛盾しないため実害は無いと判断するが、同Policy末尾の変更履歴「移設に伴う規範の追加・削除は行っていない」という記述と字面上は整合しない。 | 変更履歴の記述精度 |
| 3 | `playbooks/serial_getty_mask.yml` | 37, 106 | コメントと`fail_msg`(operator向け実行時メッセージ)が旧見出し「`docs/ai/roles/coordinator.md`『実ホストへの非冪等操作の承認』」を name-check したまま。見出し自体は今も実在するため完全な断線ではないが、保護対象ホスト一覧の実体は新Policy §2(EXEC-010)へ移っており、このplaybookは移設前の場所を指している。**本diffの対象外ファイル**であり、修正はレビュー範囲外。 | 宙ぶらりん参照(diff対象外) |

## What Looks Good

- **規範の消失: 無し。** 移設対応表(上記)の18項目すべてで、旧文書の義務・禁止・例外が新Policyの対応するEXEC-nnnへ等価に存在することを、両ファイルの現物を開いて確認した。明示禁止が暗黙導出へ後退した箇所も無い。
- **読み手へ届く仕掛け: 機能する形で入っている。** `CLAUDE.md`(全セッション起動時に読む入口)が「対象作業に関わらず作業開始時に読む」と明記し、`docs/ai/core.md`「開発の作業時に読む情報」ステップ2が「4項の『対象業務のPolicyだけ』の例外はこれ1本」と明示し、`docs/ai/role-context-matrix.md`が4Role全ての当該行を「起動時」(他Policyの「着手時」より早い)に揃えている。宣言・索引・入口の3層が一致しており、Policyでありながら既定の「該当分野のときだけ読む」扱いを回避できている。
- **宙ぶらりん参照: 無し(diff対象範囲内)。** 新Policyが指す `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`、`docs/ai/context/operations/operator-request-channel.md`、`docs/ai/context/system/semaphore.md`、`docs/ai/context/system/autonomous-recovery.md`「検証用target」、`docs/ai/core.md`「Ansible変更の共通ゲート」を、いずれもファイルを開いて節見出しの文字列一致まで確認した。相対リンク(`../policies/...`、`../../policies/...`)も実パスで階層数を検算し正しい。変更12ファイル側の新規参照(`docs/ai/policies/execution_boundary_policy.md`)もすべて実在する。
- **意味変化: 無し。** 承認区分8行・ホスト3区分・状態を変えない確認の扱い・Roleごとの実行可否のいずれも、義務の強さ・適用範囲・例外が変わっていない。
- **層の整合: 問題無し。** 新Policyの中身(承認区分・ホスト境界・状態を変えない確認・Roleごとの実行可否)は`docs/ai/core.md`「Role・Skill・Context・Policyの関係」が定めるPolicyの定義(「対象業務の許可・禁止・停止条件」)に沿う。Role固有の作法(commitメッセージの書き方等)は`coordinator.md`側に残り、Context(環境事実)の混入も無い。Auditorは元から技術Contextを読まない設計(matrix「Auditorの参照範囲」、本diff対象外)で、Auditor自身の「実ホストへ触れない」は`auditor.md`側に独立して既存しており矛盾しない。

## Verdict

Approve(Minor 3件は指摘に留め、Coordinatorの裁量判断に委ねる)。
