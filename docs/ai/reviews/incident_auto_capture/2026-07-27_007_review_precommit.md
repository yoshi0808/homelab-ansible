# レビュー記録: commit前YAML構文検査の追加(独立レビュー)

日付: 2026-07-27(JST)
役割: Reviewer(独立subagent、実装者とは別セッション)
対象: 未commit差分
- `scripts/git-pre-commit-check.sh`(変更、+17行)
- `scripts/check-staged-yaml.py`(新規)

前提文書: `docs/ai/reviews/incident_auto_capture/2026-07-27_002_requirement.md` 節「`capture.yml` 破損時の扱い(Coordinator決定、2026-07-27)」。この変更はcommitゲート自体であり、壊れるとYoshinobuがcommitできなくなるため、依頼どおり「誤検知でcommitを止めないか」「検査すべきものが静かにスキップされないか」を最優先で検証した。

## 検証方法

`/tmp` 配下に使い捨てgitリポジトリを3つ作成して検証した(`git commit`は一度も実行していない。使い捨てリポジトリでも禁止と理解し遵守)。

1. `check-staged-yaml.py`単体への直接入力テスト(vaultタグ、複数ドキュメント、空ファイル、コメントのみ、アンカー/エイリアス、非UTF-8、シンボリックリンク、rename、大容量ファイル、staged/worktree不一致)。
2. `scripts/git-pre-commit-check.sh`本体(`check-tester-gate.sh`も配置)をend-to-endで実行し、既存チェック(gitleaks/dangerous-file/vault-header/tester-gate-lint)との相互作用、正常系、異常系(壊れたdynamic-include想定ファイル)を確認。
3. 実リポジトリの `git clone`(コミット履歴を保持、新規commitは作成せず)を使い、実在するYAML全152ファイル(最大 `roles/proxmox_patch_apply_node/tasks/main.yml` 1039行)に対する実測時間と、実ファイルの`rename`(`git mv`、未commit)を確認。
4. 検証後、使い捨てリポジトリ3つ(`yamltest`、`e2e`、`repoclone`)は削除済み。本番リポジトリのindexは一切変更していない(`git status`は本レビュー開始時と同じ差分のみ)。

なお `/tmp/.../scratchpad/yamlgate` というディレクトリが検証開始前から存在していたが、本レビューでは作成しておらず、他セッションの作業物と判断し触れていない。

## Critical Issues

### 1. 非ASCII文字を含む(gitがquoteする)ファイル名は、YAML構文チェックから**完全に無警告でスキップされる**

- File: `scripts/git-pre-commit-check.sh:56-60`
- 再現条件と実測: `git diff --cached --name-only` は `core.quotepath`(既定 `true`、本リポジトリは未設定=既定)により、非ASCII文字を含むパスを `"\346\227\245...yml"` のような8進エスケープ+ダブルクォート付きの1行として出力する。この行は末尾が `yml"` であり、`grep -Ei '\.ya?ml$'` の `$` アンカーは一致しない。結果として `yaml_files` 配列に一切追加されず、`check-staged-yaml.py` は**呼び出されすらしない**。
  実際に `roles/日本語role/tasks/main.yml` へ構文エラーのあるYAML(`foo: [1, 2` / `bar: baz`、閉じ括弧なし)を作り `git add` してから `scripts/git-pre-commit-check.sh` をフルパスで実行したところ、gitleaks・vault-header・tester-gate-lint(`playbooks/*.yml`のみ対象で当該roleを見ない)をすべて素通りし、**`[pre-commit] OK` / exit=0** となった。
- 影響: この案件が予防しようとしている「`capture.yml`のような、動的includeされるタスクファイルの構文エラーがcommit前検査を素通りする」事態そのものが、非ASCIIファイル名という別経路で今も起きる。本リポジトリの現存roleファイル名は現状すべてASCIIだが(確認済み)、将来ファイル名にYoshinobuの意図で日本語が使われる可能性を排除できず、また同じ欠陥は「ダブルクォートを含むファイル名」等、`core.quotepath`がエスケープする他の文字クラス全般に及ぶ。**「WARNINGを出すだけで止めない」設計判断(`check-staged-yaml.py`側)よりさらに悪い**——警告すら出ない。
- 推奨対応: `git diff --cached --name-only -z --diff-filter=ACMR`(NUL区切り、quote無効化)を使い、`read -r -d ''` でファイル名を分解する。既存の`staged_files`変数(dangerous-file/ipv4/vault-headerチェックが共用)も同じ弱点を持つが、これは本diffの変更範囲外であり指摘のみ留める。最小修正は新設のYAML検査ブロックだけでも `git -c core.quotepath=false diff --cached --name-only -z ...` へ切り替えることだが、`staged_files`自体を直す方が一貫する。

## Suggestions

### 2. `check-staged-yaml.py`のdocstringが、存在しない「既存の慣行との一致」を主張している

- File: `scripts/check-staged-yaml.py:3-7`
- 内容: 「staged content(`git show :<path>`)をチェックするのは、`git-pre-commit-check.sh`が他所(vault-headerチェック)で既に使っている慣行に合わせたもの」と書かれているが、現物を確認したところ誤り。`git-pre-commit-check.sh:40-54`のvault-headerチェックは`[[ -f "$file" ]]`と`head -n 1 "$file"`で**作業ツリー**のファイルを直接読んでおり、`git show :path`によるindex参照は使っていない。
- 影響: 実害はない(新設スクリプト自身の挙動——stagedを見る——はこの案件の目的に対して正しい。下記「良かった点」参照)。ただし、将来の保守者がこのdocstringを信じて「両者は同じ入力源を見ている」と誤認するおそれがある。
- 推奨対応: docstringの当該一文を削除するか、「vault-headerチェックは作業ツリーを見ており、本スクリプトは意図的にそれとは異なりstagedを見る」と正確に書き直す。

### 3. `git show :<path>`読み取り失敗時のWARNING(non-blocking)は妥当だが、明示的な合意が必要

- File: `scripts/check-staged-yaml.py:83-89`
- 実装は、`yaml_files`に含まれるパスに対し`git show :<path>`が失敗した場合、`ok`フラグを変えずWARNINGのみ出力してcommitを止めない。
- 判断: 依頼の観点「誤検知回避 vs 検査漏れ回避のどちらを優先すべきか」に対する私の判断は次のとおり。**この特定のギャップ(item)は許容してよい。** 理由は、この経路が発火するのは「`git diff --cached --name-only`が一覧した直後のパスに対し`git show :path`が失敗する」という、同一プロセス内の同一index状態への2回のクエリの間に矛盾が生じるケースに限られ、通常のローカル単独commit操作では実質発生しない(同時に他プロセスがindexを書き換える等の外的要因が要る)。これをERRORでブロックすると、YAML内容とは無関係な理由でcommitがまれに止まり、原因究明の負担をYoshinobuに強いる一方、防げる実害はほぼ無い。**ただしこの判断はCritical Issue 1が示すとおり「無警告スキップ」がすでに現実の経路(非ASCIIファイル名)で起きているという前提の上に立つ。** Critical Issue 1を修正しない限り、「まれな一過性の読み取り失敗だけを見逃す」という設計意図は成立しない(もっと高頻度に踏む無警告経路が別に存在するため)。Critical Issue 1の修正を条件に、本項目はApprove扱いでよいと判断する。

### 4. 大容量ファイルで`yaml.SafeLoader`(pure Python)を使っており、`yaml.CSafeLoader`(C実装、この環境で利用可能)より遅い

- File: `scripts/check-staged-yaml.py:81`
- 実測: 合成テスト(200,000行、4.7MBのフラットYAML)で6.2秒。本リポジトリの実在最大YAMLファイル(`roles/proxmox_patch_apply_node/tasks/main.yml`、1039行)を含む実リポジトリ全152ファイルの一括検査は0.678秒だった(実運用のcommitは通常数ファイルのみなので、実効コストはこれよりさらに小さい)。
- 現時点でblockingではないが、`yaml.CSafeLoader`(このホストでは`import yaml; hasattr(yaml, 'CSafeLoader')`が`True`)へのフォールバック付き切り替えで安価に高速化できる。ホストによってlibyaml未導入の場合もあるため、`try: yaml.CSafeLoader except AttributeError: yaml.SafeLoader`のフォールバックが要る。優先度は低い。

## What Looks Good

- **staged(`git show :<path>`)を見ており、作業ツリーを見ていない。** 意図的に2パターンで実証: (a) 有効なYAMLをstageした後に作業ツリーだけ壊す→検査は通る(exit 0)。(b) 無効なYAMLをstageした後に作業ツリーだけ直す→検査は落ちる(exit 1、staged側の構文エラーを正しく検出)。これは依頼の観点4そのものであり、正しく実装されている。
- **`yaml.compose_all()`の選択は的確。** Ansible/YAMLカスタムタグ(`!vault`)、複数ドキュメント(`---`区切り)、空ファイル(0ドキュメント)、コメントのみ、アンカー/エイリアスをすべて誤検知なく通過することを実測確認した。「値を構築せずノードグラフだけを組む」という設計選択は、カスタムコンストラクタ未登録によるvaultタグの誤検知を避ける正しいアプローチ。
- **シンボリックリンクの除外(`120000`モード)は正しく機能する。** `git ls-files -s`で一括取得し、symlinkのblob内容(パス文字列)をYAMLとして誤検査しない。実測確認済み。
- **rename検出との整合。** `--diff-filter=ACMR`によりrenameは新パスのみが一覧され、そのパスは`git show :path`で正しく取得できることを実クローンの`git mv`で確認した。
- **依存追加なし、かつfail-closed。** PyYAMLはansible-core自体の依存であるため新規依存ではない。`import yaml`失敗時の挙動を`builtins.__import__`をモックして直接検証したところ、ERRORメッセージを出して**exit 1(commitを止める)**ことを確認した——「サイレントにスキップ」ではなく「止めて知らせる」側に倒しており、この案件の主題(R5: 静かに壊れるのが最悪)と整合する。
- **既存チェックとの共存。** end-to-end実行で、gitleaks→dangerous-file→ipv4→vault-header→(新設YAML検査)→tester-gate-lintの順序が壊れておらず、失敗時のメッセージ(`ERROR: <path>: invalid YAML (...)` に続き `ERROR: staged YAML syntax check failed (see above)`)は原因がYAML検査であることを明確に示す。正常系(有効なplaybook1件をstage)は`[tester-gate-lint] OK`→`[pre-commit] OK`まで到達することを確認した。
- **`set -euo pipefail`下の安全性。** 空配列(`yaml_files=()`)の扱いは`${#yaml_files[@]} -gt 0`で先にガードしており、bash 5.3.9(このホスト)で問題なし。`grep`の0件マッチはすべて`|| true`で握っており、パイプ内の失敗も意図どおり伝播する。ファイル名の空白は`while IFS= read -r`の行単位読み取りにより保持され、word splittingの問題は起きない(`file with space.yml`で実測確認)。パスが`-`で始まるケースも、`git ls-files -s -- <paths>`・Python側の`subprocess.run`（配列引数、シェルを介さない）双方で`--`または安全な引数分離がされており問題ない(`-dashstart.yml`で実測確認)。

## 未確認事項

- Critical Issue 1の根本原因である`staged_files`変数(既存3チェックと共用)の`core.quotepath`起因の脆弱性は、本diffの変更範囲外であるvault-header/dangerous-file/ipv4チェックにも及ぶと考えられるが、それらは今回のレビュー対象外のため実測確認していない。別タスクとしての切り出しをTech Leadへ提案する。
- コントロール文字や埋め込み改行を含むファイル名など、`core.quotepath`のエスケープ対象のさらに極端なケースは個別実測していない(Critical Issue 1の再現で原理は確認済みのため、同一クラスとして扱ってよいと判断した)。

## Verdict

**Request Changes** — Critical Issue 1(非ASCIIファイル名の完全無警告スキップ)の修正を必須とする。この案件の目的が「commit前ゲートを唯一の予防層とする」ことである以上、ゲート自身に無警告の迂回路が実測で存在する状態でのApproveはできない。Critical Issue 1が解消されれば、Suggestions 2-4はblockingではなくApprove相当と判断する。
