# implement: Phase 3 Step 1 — 既存 helper の filename 検証拡張 + バンドル読取 helper 新設

日付: 2026-08-03 (JST)
requirement: `2026-08-02_001_requirement.md` R13b / R14c
plan: `2026-08-03_007_plan_phase3.md` §1.2 / §1.4 / §2 Step 1
catalog(正本): `2026-08-03_008_phase3_check_catalog.md` §0(I-1〜I-6)/ §1 Q-A(Q1〜Q4)/ Q-B の G1 注記

## 1. 成果物

| 契約 | 種別 | パス |
|---|---|---|
| 契約1 | 既存ファイル修正 | `roles/recovery_exec/files/recovery-reports-helper` |
| 契約1 | 既存ファイル修正 | `roles/recovery_exec/files/homelab-reports` |
| 契約2 | 新設(helper 実体) | `roles/recovery_exec/files/incident-bundle-helper` → 配備先 `/usr/local/sbin/incident-bundle-helper` |
| 契約3 | 新設(Codex 向け wrapper) | `roles/recovery_exec/files/homelab-incident-bundle` → 配備先 `/usr/local/bin/homelab-incident-bundle` |
| 契約4 | 配備 task 追加 | `roles/recovery_exec/tasks/main.yml`(既存 `homelab-reports` / `recovery-reports-helper` 配備の直後に2task追加) |
| 契約4 | Codex 向け説明追記 | `roles/recovery_exec/templates/AGENTS.md.j2`(新節 "Incident bundle lookup" + `## Prohibitions (§13)` の許可ツール列挙に追加) |

`roles/dev_investigate/` は触れていない(依頼の禁止事項どおり)。`docs/ai/reviews/dev_prod_boundary/` の2件の untracked plan/catalog、`roles/recovery_exec/files/claude-investigate*.pub` は自分が作った変更ではない(着手前から untracked)。

## 2. 契約の充足状況

### 契約1(FILE_RE を1文字だけ広げる)

両ファイルとも `FILE_RE='^[a-zA-Z0-9_-]+\.json$'` → `'^[a-zA-Z0-9_+-]+\.json$'`。`.` を足さない理由をコード中コメントに明記(「名前部に `.` を許すと `..` が入りうるため、traversal が構造的に不可能である性質を崩さない」)。`homelab-reports` 側は `recovery-reports-helper` の同一コメントを参照する形にした(重複を避けた)。

### 契約2(incident-bundle-helper)

- `BASE=/home/yoshi/homelab-ansible/reports/incidents` を固定値でハードコード。operand から一切組み立てない。
- サブコマンド4種は依頼文の表と完全一致(`list-bundles` / `show-bundle <id> <file>` / `list-investigations` / `show-investigation <id> <ext>`)。
- `id` は `^semaphore-[0-9]{1,9}$`。`file` / `ext` は正規表現でなく `case` の enum リテラル一致(4種 / 2種)とし、`+`や`.`を含む任意文字列が通る余地自体を無くした。
- `_spool/` `_runs/` はコード上どの分岐からも参照されない(`list-bundles` は `ID_RE` で `semaphore-` prefix必須のため `_spool`/`_runs` は構造的にマッチしない。`list-investigations` は `_investigations/` 固定パスのみを読む)。
- `recovery-reports-helper` と同型の `under_base()` による defense-in-depth(realpath 解決後に BASE 配下か再確認)を踏襲。
- I-1(read only): `cat` / `find` / `grep` / `sed` / `sort` のみ。書込語彙なし。
- I-2(`eval` 不使用): 使用なし。
- I-3(operand からパス組み立てない): BASE固定 + enum/正規表現済みの id・file・extのみで path を組む。
- I-4(固定 arity): 各分岐で `[[ $# -eq N ]]` を明示チェック。
- I-5(改行・復帰を含む operand の拒否): 実測で確認(§3 参照)。
- I-6(`denied:` + 非ゼロ終了): 全拒否経路で満たす。**当初 arity 違反・未知サブコマンドの fallback (`usage()`) が `usage: ...` のみを出しており I-6 を満たしていなかった。自己検証中に発見し `denied: usage: ...` へ修正した**(§4 参照)。

### 契約3(homelab-incident-bundle)

- 配備先 `/usr/local/bin/homelab-incident-bundle` を固定。
- `homelab-reports` → `recovery-reports-helper` と同型の2層構成: wrapper が自分の判断で検証してから `exec /usr/local/sbin/incident-bundle-helper "$@"`、helper 側が全operandを独立に再検証する。どちらか一方を通ればもう一方が必ず再判定するため、単層の見落としに依存しない。
- wrapper 側の `usage()` も同じ理由で `denied:` prefix に修正済み(契約2と同じ発見・同じ修正)。

### 契約4(配備・周知)

- `main.yml`: 既存 `homelab-reports` / `recovery-reports-helper` の配備 task 群(quory ローカル、`become: true` + `when: not ansible_check_mode` + `tags: [destructive]`)と同じ形で2task追加。配置は既存 `homelab-semaphore-query` 配備の直後、`Remove legacy homelab-mute-exec wrapper` の直前。
- `AGENTS.md.j2`: `### Reports lookup` と `### Semaphore failure lookup` の並びに `### Incident bundle lookup (homelab-incident-bundle)` を新設(`### Monitoring control` の直前に挿入)。`## Prohibitions (§13)` の許可ツール一覧にも `homelab-incident-bundle` を追加(既存の列挙にツールを1つ足すだけで、他は変更していない)。

## 3. 自己検証(V1〜V6)

実データは ansy 上の incident bundle ミラー `reports/incidents/quory/`(`semaphore-114` 他、`_investigations/semaphore-473` 他)と、実際の JST タイムスタンプ付きレポート `reports/drift/20260803_072005+0900.json` を使った。**BASE は固定値のまま変更していない** — `incident-bundle-helper` の検証は `/tmp/.../scratchpad/` へコピーした上で `BASE=` の1行だけを書き換えたテスト専用コピーに対して行い、リポジトリ側の `BASE=/home/yoshi/homelab-ansible/reports/incidents` は元のまま(この BASE は本来 quory 実機上のパスであり、ansy では存在しない)。契約1(recovery-reports-helper / homelab-reports)は BASE が `/home/yoshi/homelab-ansible/reports` で ansy 上に実在するため、リポジトリのファイルをそのまま `bash` で直接叩いて検証した。

| # | 検証 | 手段 | 結果 |
|---|---|---|---|
| V1 | 実在バンドル1件(`semaphore-114`)の4ファイル全種取得 | scratchpad コピー(`BASE` を `reports/incidents/quory` へ retarget)で `show-bundle` を4種とも実行 | 全て rc=0。`summary.json`(2781B)/`semaphore-log.log`(173006B)/`semaphore-hosts.log`(99B)/`semaphore-errors.log`(705B)。`show-bundle summary.json` の出力を元ファイルと `diff` して完全一致を確認 |
| V2 | 実在 `_investigations/semaphore-473` の `md`/`json` 両方 | 同上コピーで `show-investigation semaphore-473 md/json` | rc=0(1304B / 1435B)。`json` 出力を元ファイルと `diff` して完全一致を確認 |
| V3 | 負経路: `../`、`semaphore-abc`、絶対パス、空文字、`;`/空白混入、宣言数超過operand、未知サブコマンド、`_spool`/`_runs`をidに指定 | 19パターンを `incident-bundle-helper` 直接呼出しと `homelab-incident-bundle`(exec先をscratchpad上のhelperへ retarget)の両方に対して実行 | **19/19 とも rc≠0 かつ stderr先頭が `denied:`** |
| V4 | `_spool`/`_runs` が operand 経由で届かないこと | `show-bundle _spool summary.json` / `show-bundle _runs summary.json` を実行 | ID_RE不一致で `denied: bad bundle id`(構造的に到達不能。コード上も `list-bundles`/`list-investigations`の列挙対象外) |
| V5 | 契約1: `20260803_053711+0900.json` 形式の名前が通り、`..` を含む名前が通らないこと | **BASE変更なし**、リポジトリの `recovery-reports-helper` / `homelab-reports` を直接 `bash` 実行。正例は実在する `reports/drift/20260803_072005+0900.json`、負例は `..` を含む自作ファイル名 | 正例: rc=0(両ファイルとも、二層構成で確認)。負例(`20260803_07..005+0900.json`、`../../etc/passwd`、`..secret.json`)は両ファイルとも `denied: bad filename` / `usage: ...`(wrapper側は元々`usage:`表記のままで契約1の変更対象外) |
| V6 | 変更した shell script の構文妥当性 | `bash -n` を4ファイル全てに実行 | 全て OK |

### V3 で見つけたバグとその場での修正

`usage()` フォールバック(サブコマンド不明・arity違反)が `usage: incident-bundle-helper ...` とだけ出力しており、catalog I-6(「拒否は必ず `denied:` を stderr へ出し非ゼロ終了する」)と依頼文 V3(「宣言数を超えた operand ... いずれも `denied:` を stderr へ出して非ゼロ終了する」)を満たしていなかった。`incident-bundle-helper` と `homelab-incident-bundle` 両方の `usage()` を `denied: usage: ...` へ修正し、19パターン全件で再検証して通過を確認した(上表の値は修正後の結果)。

既存の `recovery-reports-helper` / `homelab-reports` の `usage()` は元から `usage: ...`(`denied:` prefix なし)であり、これは契約1のスコープ外(既存の挙動を変える指示ではない)として変更していない。両者の fallback 文言が不揃いなことは未解決事項として次節に記す。

### 実機システム状態への影響

`homelab-reports` の wrapper 挙動検証中、一度 `bash $W ...` を素で実行して `/usr/local/sbin/recovery-reports-helper`(2026-07-05にansyへ配備済みの実バイナリ、本タスクと無関係)を意図せず経由してしまったことに気づいた。read-only な `cat`/`usage` 呼出しのみで実害はないが、以降はexec先をscratchpad上のコピーへ retarget したテスト専用ラッパーを使い、実配備物には触れない形へ切り替えた。

検証中に誤って `chmod +x` でリポジトリ内の `recovery-reports-helper` / `homelab-reports` の git mode を 644→755 に変えてしまったことに気付き、`chmod 644` で元に戻した(`git diff` で mode 変更が消えていることを確認済み)。

## 4. 未解決事項

- 契約2・3は Step 2(`dev_investigate` role の quory dispatch)が呼ぶことを前提にした実装だが、その dispatch 自体は別 subagent が並行実装中であり、本Stepの範囲では未接続。dispatch 側が `incident-bundle-helper` を直接呼ぶか `homelab-incident-bundle` 経由か(catalog Q1〜Q4は前者を想定)は Step 2 側の実装で確定する。
- `usage()` の fallback 文言が、契約1対象(`recovery-reports-helper`/`homelab-reports`、`usage:` のまま)と契約2・3対象(`incident-bundle-helper`/`homelab-incident-bundle`、`denied: usage:` に統一)とで不揃いになった。既存2ファイルは契約1のスコープ外として変更していないが、Reviewer/Testerが両者を並べて見たときに意図的な差か見落としかを問われる可能性がある。
- 実ホスト(quory)への配備・実機での forced command 経由の検証は行っていない(依頼の禁止事項どおり)。Coordinator による配備後、Tester による AC8/AC9/AC10/AC19/AC20 の受入検証が必要。
- `git add` は行っていない(範囲を決めるのはCoordinatorの責務のため)。
