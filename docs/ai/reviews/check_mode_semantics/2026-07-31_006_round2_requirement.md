# requirement: Round 2 — `risk-accepted` 14本を `check-mode-native` へ変換

日付: 2026-07-31
前提: Round 1(commit `3bf9894`)完了。棚卸しの正本は `docs/ai/reviews/check_mode_semantics/2026-07-31_004_classification_audit.md`

## 1. 問題定義

`tester-gate: risk-accepted` を宣言する17本のうち、TS-009の**条件2**(破壊的な本体操作を省いた検証には意味がない)を満たすのは棚卸しの判定で3本だけである。残り14本は**条件1(実害が軽微)だけを根拠に分類されており**、TS-009が求める「2条件をともに満たす」を満たしていない。TS-010に照らせば `check-mode-native` が正しい分類である。

Round 1でこの14本には `--check` 停止assertが入り、黙って適用する経路は塞がった。しかしそれは床であって、正しい分類ではない。

## 2. ゴール

1. 14本を `check-mode-native` へ変換し、`--check` が**本物のdry-run**として機能する状態にする。
2. 変換の済んだものからTS-030の停止assertと `check_mode: false` を外す(TS-032の手順)。
3. `risk-accepted` が3本になった時点で、分類理由が条件2に言及していることを機械検査する。

## 3. 非ゴール

- 3本(`cloudkey_cert_deploy` / `proxmox_backup_restore_verify` / `unifi_backup_fetch`)の分類変更。**条件2を満たすため `risk-accepted` のまま維持する。**
- `notify.yml` / TS-031 の再検討。Round 1で確定済み。
- `--check` なしの通常実行の挙動変更。**変換は `--check` 時の挙動だけを変えるものであり、通常実行は不変でなければならない。**

## 4. バッチ分割(2026-07-31 Yoshinobu合意)

| バッチ | 対象 | 選定理由 |
|---|---|---|
| **A** | `incident_capture_setup` / `incident_investigate_setup` / `recovery_probe_setup` | role内に既にcheck-mode対応のtaskが存在する。変換パターンを最小の変更で確定させる |
| **B** | `recovery_io_setup` / `recovery_push_setup` / `recovery_push_drill_setup` / `systemd_timers` / `incident_sync_timer` / `time_sync_ntp_reference` / `ca_trust_deploy` / `incident_inspect_setup` / `recovery_exec_setup` | 素直な配置系。`command`/`shell`/`uri` の auto-skip を1本ずつ見る。**`recovery_exec_setup` は最後**(2026-07-08にquoryで3日間のSSH障害を起こした `authorized_keys` 配布taskを含み、横方向の影響を持つ) |
| **C** | `cert_renew` / `codex_update_check` | multi-play・quory限定ガード・版判定ロジックがあり最も重い。`cert_renew` と `cloudkey_cert_deploy` の線引きもここで決める |

> **バッチBの内訳(2026-07-31)**: Bは2つの実装単位に分ける。**B-1 = 8本**(`recovery_io_setup` / `recovery_push_setup` / `recovery_push_drill_setup` / `systemd_timers` / `incident_sync_timer` / `time_sync_ntp_reference` / `ca_trust_deploy` / `incident_inspect_setup`)、**B-2 = `recovery_exec_setup` 単独**。B-2を分けるのは、同playbookが2026-07-08にquoryで3日間のSSH障害を起こした `authorized_keys` 配布taskを持ち、`-l` で絞っても横方向へ影響しうるためで、独立したレビューと検証を与える。
>
> role依存の実測(2026-07-31): B-1の8本のうち **`recovery_push_setup` と `recovery_push_drill_setup` は同じ `roles/recovery_push/` を触る**(後者は `tasks/drill_setup.yml` を `include_tasks` する)。実装単位を分けるならこの2本は同じ単位に置く。他の6本のroleは互いに独立している。`ca_trust_deploy` は `homelab_cert_renew` role も使うため、**バッチCの `cert_renew` と競合しうる** — B完了後にCへ入ること。

> **バッチ分割の訂正(2026-07-31)**: 当初の分割はA=3 / B=8 / C=2 の計13本で、非ゴールの3本と足しても16本にしかならず、母集団17本と合っていなかった。`incident_inspect_setup` が**どのバッチにも割り当てられていなかった**ためで、バッチBへ追加した(B=9、合計14本)。バッチAのレビューがこの算数の不一致を検出した。**分割を変えるときは、非ゴール3 + A + B + C = 17 が成り立つことを毎回確かめること。**

## 5. 要件(バッチ共通)

| # | 要件 |
|---|---|
| R1 | 対象playbookの `# tester-gate:` を `check-mode-native` へ変更し、理由に**TS-009の条件1と条件2の両方への言及**を含める(条件2を満たさないから移す、という形で書く) |
| R2 | Round 1で追加した `--check` 停止assertを除去する |
| R3 | role importに付いている `check_mode: false` のカスケードを除去する |
| R4 | **破壊的taskすべて**に `when: not ansible_check_mode` と `tags: [destructive]` を付ける(TS-014)。相互依存する一連はblock単位でゲートする(TS-015) |
| R5 | read-onlyだが `--check` で auto-skip されると後続の判定が壊れるtask(`command` / `shell` / `uri` 等)には `check_mode: false` を付ける(TS-017)。**付けた理由をその場のコメントに書く** |
| R6 | 停止assertの `fail_msg` に入っていた `-e skip_notifications=true` の案内は、除去とともに落とす(通知抑止の手段としては引き続き有効だが、停止しなくなるため案内の置き場が変わる) |

## 6. 受入条件

**AC1(dry-runとして成立する)**
Given 変換したplaybook
When `--check` を付けて起動する
Then **終了コード 0** で完走し、破壊的taskが `skipped` に現れる

> **AC1の訂正(2026-07-31)**: 当初この条件に「`changed` が『変更されるはずの件数』を示す」も書いていたが、TS-014が定める本リポジトリの方式(破壊的taskは `when: not ansible_check_mode` でskipする)では**破壊的taskは実行されないため `changed` に計上されない**。2つの記述は両立しない。TS-014が正であり、`changed` の件数はACの判定材料にしない。バッチAのImplementerがこの矛盾を指摘した。

**AC2(通常実行の不変)**
Given 変換したplaybook
When `--check` を付けずに起動する
Then 変換前と同じ結果になる。**終了コード 0**、適用対象が同じで、通知の有無も変わらない

**AC3(部分適用が起きない)**
Given 変換したplaybook
When `--check` を付けて起動する
Then **ホスト側に変更が一切生じていない**。`--check` 実行の前後でホスト状態を比較して確認する

**AC4(lintが通る)**
Given 変換後の作業ツリー
When `scripts/check-tester-gate.sh` を実行する
Then 終了コード 0。変換したplaybookは `risk-accepted` ではなくなるため停止assertを要求されない

**AC5(母集団が減っている)**
Given 変換後の作業ツリー
When `risk-accepted` を宣言するplaybookを数える
Then 変換した本数だけ減っており、最終的に3本になる

## 7. オープンクエスチョン

| # | 内容 | 誰が決めるか |
|---|---|---|
| ~~OQ1~~ **決着(2026-07-31)** | `systemd_timers` / `recovery_push_drill_setup` は変換後、全taskが破壊的でゲート対象になり、`--check` は「全部skip」になる。構文と変数解決以外の診断的価値は増えない。**それでも `check-mode-native` が正しい。** 分類が保証するのは「`--check` が書き込みを行わないこと」であって「`--check` が追加の診断情報を生むこと」ではない。両playbookはread-onlyではないため `safe-readonly` は誤りであり(TS-005)、`risk-accepted` は条件2を満たさないため選べない(TS-009)。**残る5分類の中で唯一該当するのが `check-mode-native` である。** 診断的価値が薄いことは分類の誤りではなく、そのplaybookの性質である | Coordinator決定 |
| OQ2 | `cert_renew`(分離可能な更新要否チェックを持つ)と `cloudkey_cert_deploy`(分離不能な `uri` 連鎖)の線引き | バッチCで決める |
| OQ3 | 条件2言及の機械検査をどの粒度で書くか(文字列一致では抜ける) | 全バッチ完了後 |

## 8. タイムライン考慮

- **バッチAでパターンを確定させてからB・Cへ進む。** Aの変換手順がレビュー・検証を通った形が、以降のテンプレートになる。
- 2026-07-31、Yoshinobuが当日以降のSemaphore定期ジョブを一時停止した。検証実行が定期実行と衝突しない。
- AC2(通常実行の不変)は本番適用にあたるため、Tester役は実行しない。確認方法はバッチごとに設計する。
