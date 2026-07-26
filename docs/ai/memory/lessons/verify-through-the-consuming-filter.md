# 検証は値の目視で終えず、その値を消費する側まで通す

## 教訓

Jinja / Ansibleの変数を検証するとき、値を`debug`で表示して目を通すだけでは不十分である。**その値を実際に消費する下流のtask(`| length`、`| int`など、`None`で例外を起こすフィルタ)まで通してplaybookを完走させる**。

## 根拠(2026-07-26、proxmox_patch_dryrun単一ノード対応)

制御構文だけで静的テキストを一切含まないJinjaテンプレート(`{%- else -%}{%- endif -%}`のように、そのブランチで何も出力しないもの)は、Ansibleのtemplarが**空文字列`""`ではなくPythonの`None`**として返す。

ImplementerもReviewerもdecoy inventoryで値を確認し、「両ノード健全時は空文字列になる」と結論した。しかし`''`と`None`は`debug`の出力では見分けがつかない。この値へ無条件に`| length > 0`を適用していた3箇所が、実ホスト実行で`object of type 'NoneType' has no len()`を起こした。両ノード健全は**最も普通の日次実行ケース**であり、毎回失敗する回帰だった。

decoy検証を2者が独立に通過したうえで、実ホスト実行でのみ発覚している。「独立した2人が見た」ことは、両者が同じ弱い検証手段を使っていれば担保にならない。

## 適用

- 値を確認するときは`repr`相当の表示(Pythonなら`repr(value)`)を使い、`''`と`None`を区別する。
- 空文字列を期待する変数は`| default('', true)`で受ける。**第2引数`true`が必須** — 省略するとJinjaの`default`は`Undefined`しか置換せず、実体としての`None`は素通りする。
- テンプレート側でelseブランチに明示的に何かを出力させるのも有効。
- decoy inventoryを使う場合も、値の抽出だけでなく**実際のwhen条件・フィルタを含むplaybookを最後まで完走させる**。

## 関連

- `docs/ai/memory/lessons/multilayer-escaping-and-novel-stack-verification.md`(初物スタックでruntime再現手段を先に確保する)
- 案件記録: `docs/ai/reviews/proxmox_patch_dryrun/2026-07-26_003_implement.md` §8、`2026-07-26_005_test_result.md`
