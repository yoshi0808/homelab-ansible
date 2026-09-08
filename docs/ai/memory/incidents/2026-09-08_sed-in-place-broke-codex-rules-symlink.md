# Incident: sed -iがCodex rulesのsymlinkを通常ファイルへ置き換えた

日付: 2026-09-08
状態: 解決済み
対象: `~/.codex/rules/default.rules`
種別: 動作不具合

## 症状

Coordinatorが案内した`sed -i`をsymlinkである
`~/.codex/rules/default.rules`へ実行した結果、ホーム側のpathが通常ファイルへ
置き換わった。ホーム側は`git commit` / `git push`が`allow`になった一方、
リンク先だったrepoの`.codex/rules/default.rules`は`prompt`のまま残った。

## 原因

GNU sedのin-place更新が既定ではsymlinkのリンク先を書き換えず、一時ファイルとの
renameによってsymlink自体を置き換えることを考慮しなかった。対象がsymlinkだと
確認済みだったにもかかわらず、repo側の実体ではなくホーム側pathを指定した。

## 修正内容

repo側の実体を直接編集した後、ホーム側pathをrepo実体へのsymlinkへ戻す。

## 確認方法

`readlink -f`でホーム側pathがrepo実体を指すこと、`cmp -s`で両pathから
同じ内容が読めることを確認した。Codex 0.153.4の`execpolicy check`はrulesを
構文エラーなく読み込み、`git commit` / `git push` / `git status`をすべて
`allow`と判定した。
