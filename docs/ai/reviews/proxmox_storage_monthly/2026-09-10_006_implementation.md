# 実装引き継ぎと検証

状態: 010独立再レビューApprove、011再テストPASS。本番未配備。

## 現物

003計画と005のApproveを入力として、既存の未commit実装を引き継いだ。対象は新playbook、roles/proxmox_storage_monthly全体、tests/test_storage_monthly.py、playbooks/README.md、運用Context。判定の共通処理はfilter_pluginsではなくmodule_utilsへ置かれている。

## 検証

- `python3 -m unittest discover -s tests -p test_storage_monthly.py -v`: 11件成功。
- inventory指定の`ansible-playbook --syntax-check`: rc0。動的group storage_monthly_targetsの未定義警告あり。
- `bash scripts/check-tester-gate.sh`: 61 playbook成功。
- `git diff --check`: 成功。

いずれも本番収集・Notion投稿・Slack送信を行っていない。既存テストの成功をAC全件の充足とは扱わない。

## 未完了

commit/push承認、Integration配備、実pve出力一致確認、初回本番受入。既存scrub/cronは変更しない。計画の省トークン効果は未測定。011の抑止組合せ数は128とあるが、実コードの5 booleanの組合せは32（010記載と一致）。検証結果自体はPASS。

## 007/009への対応（2026-09-11）

- 007 Major 1: report.yml現物から抑止式を読み込み、Ansibleでcheck/skip/CLAUDECODE/Notion force/Slack forceの組合せを評価するテストを追加。
- 007 Major 2: pruneを実際の一時ファイルで実行し、13か月境界・公開済削除・基準保護・未公開・symlink・directory除外を確認するfixtureを追加。Suggestionのtoken権限/空/symlinkも追加。
- 009: scan日時の英語曜日/月名をstrptimeで読むロケール依存を除去。明示的な月名対応とdatetimeの数値引数で解釈し、プロセスlocaleは変更しない。日本語/Cロケール、空白埋め日、不正月・日付の回帰テストを追加。
- 追加された3テストの変更者はCoordinatorである。検証担当の走行中に差分を変更したため停止を招いた。担当の変更ではなく、削除・復元は不要。再依頼後は対象差分を固定する。
- ユーザー提示の工程管理表を確認し、毎月15日08:00 JSTをcatalogへ追加。表に掲載された開始時刻とは重ならないが長時間処理の終了時刻は未確認。scheduleはactive=false、Integration/初回readback前に有効化しない。表のprivate URLは公開repoへ転記しない。
- 修正後 `LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8 python3 -m unittest discover -s tests -p test_storage_monthly.py -v`: 15件PASS（6.642秒）。syntax-check rc0、tester-gate 61件、doc-consistency 3チェック、git diff --check成功。独立再検証を代替しない。

## 実行境界の観測

Reviewerの既存pane確認はsandbox内でOperation not permittedだった。同一コマンドを正規のrequire_escalatedで再実行すると成功し、計画査読後の待機状態を確認した。境界設定は変更していない。
