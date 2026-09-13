# quory NVMe取得ツール配備 — テスト計画

対象: 要求012、計画013、最終差分レビュー018、および現在の未コミット差分。

## 目的と安全境界

`quory_nvme_setup.yml` の構文、tester-gate、check-mode境界、対象欠落時のfail-closed、パッケージ導入の冪等性設計、Semaphore catalogの静的整合性を確認する。実quory、実ホスト名/IPを含むinventory、Semaphore API、Slack/Notionには接触しない。APT変更・APT cache更新を発生させる実行は行わない。

## カバレッジ

| 層 | 検証 |
|---|---|
| unit/static | syntax-check、ansible-lint、doc consistency、tester-gate lint、diff check、既存unit、task/module/source inspection |
| integration/dry-run | `safe-ansible-check.sh` + `localhost,` 合成inventoryで、quory不在が非0停止すること。実ホスト名をdecoyにしたpositive実行はしない |
| apply | Not Run。実quoryまたはlocal transportでAPTへ到達する実適用は禁止 |
| postflight/e2e | Not Run。実quoryの `nvme version`、月次health `--check`、Semaphore template/schedule readbackは配備工程で実施 |

## 受入条件との対応

- AC-S1: 静的に `check-mode-native`、aptのcheck-mode契約、readbackのcheck-mode抑止、quory限定対象を確認。合成inventoryでquory不在の空成功を非0停止することを実行確認。実quoryのrc・導入見込み・副作用非生成は未確認。
- AC-S2: `package_facts` による導入済み判定と条件付き `update_cache`、`apt state: present`、通常実行時だけの `nvme version`、既定のrc失敗伝播を確認。実導入・部分失敗後の再実行・CLI実機readbackは未実施。
- AC-S3: 観測playbook/roleに変更がないことを確認。setup後のhealth `--check`と `tool_unavailable` の消失は未実施。
- AC-S4: catalogの専用templateが1件であること、schedule差分がないこと、syntax/doc checksを確認。実Semaphore readbackは未実施。

## 実行順

1. 現在のstatus/diffと対象文書を確認。
2. 静的チェック一式を実行。
3. `safe-ansible-check.sh` を `--check`付きのlocalhost合成inventoryで実行し、対象不在時の非0停止を確認。
4. 実測結果、未実施、残存リスクをtest resultへ記録する。
