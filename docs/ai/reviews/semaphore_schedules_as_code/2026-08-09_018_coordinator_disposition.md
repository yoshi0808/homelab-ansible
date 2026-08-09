# Coordinator disposition: 実装レビュー(`_017`)の採否と、環境側の対応

作成日: 2026-08-09 / 作成: Coordinator

対象レビュー: `2026-08-09_017_review_implementation.md`(codex 側 Reviewer、Verdict = Request Changes)

## 1. 採否

| # | 指摘 | 採否 | 送り先 |
|---|---|---|---|
| Critical 1 | stage 1 の PUT が、差分計算時点の古い `active` を fresh GET へ上書きする | 採用 | task 側 Implementer |
| Critical 2 | `allow_flag` / `closed_world` に文字列が渡ると真と評価され、有効化が許可される | 採用 | **両方**(filter で真偽値以外を失敗扱い、task 入口で型検証) |
| High 3 | 失敗経路でレポートへ到達しない | 採用 | task 側 Implementer |
| High 4 | ansy 向け token の既定パスが所有権検査と両立しない | 採用(**解決は環境側**。§2) | task 側 Implementer(パスの per-target 分岐の撤去のみ) |
| High 5 | 同一変更での template + schedule 追加で `--check` と apply の前提が分岐する | **採らない**(§3) | メッセージの明示のみ |
| High 6 | 書き込み後検証が非管理フィールドの保持を見ていない | 採用 | filter に `semaphore_schedules_nonmanaged_diff` を追加し、task が配線 |
| High 7 | `task_params` の公開可否判定が未知値を fail-open する | 採用 | filter 側 Implementer |
| Suggestion 1–3 | task 層の integration テスト、R9⑦ の negative case、templating 境界を通す test | test_plan へ引き継ぐ | Tester |

Critical 2件は Coordinator が独立に再現した。#1 は `schedules_apply_stage1_item.yml` の PUT が `item.after`(早い GET 由来)を merge していること、#2 は `activation_gate` へ `allow_flag="false"` を渡すと `allowed: True` が返ることを、それぞれ現物で確認している。

## 2. 環境側の対応 — ansy の token(High 4)

**コード側の所有権検査は緩めない。** `token.yml` の「root 所有 0600 でなければ停止」は本番 quory と共有する経路であり、検証環境の都合で弱めると本番側の保証が下がる。

代わりに ansy 側を契約へ合わせた(2026-08-09、Yoshinobu 承認のうえ Coordinator が実施)。

- `/etc/homelab-recovery/`(root:root 0700)を作成
- `/etc/homelab-recovery/semaphore-templates-api-token` を root:root 0600 で配置。内容は既存の ansy 用 token と同一

これにより `semaphore_templates_token_path` は **quory と ansy で同一の絶対パス**になり、per-target 分岐と `~` の展開先の曖昧さがどちらも消える。

既存の `~/.semaphore-api-token-ansy`(yoshi 所有 0600)は残す。codex の read-only MCP がこのパスを所有者と mode の検証つきで読んでおり、動かすとそちらが壊れるため。**ansy の開発用 token が同一ホスト上に2つの root/yoshi 専用ファイルとして存在する状態を、承知のうえで受け入れている。** UI で token を再発行したときは両方を更新すること。

## 3. High 5 を採らない理由

requirement R10 が、この分岐を**運用制約で解決すると明記している** — 「template と schedule を同一変更で追加する場合は、template を先に適用する2段階とする。`--check` と apply で前提が分岐しないことをこの制約で担保する」。

`--check` で template 未作成のまま schedule の名前解決が 0 件になり停止するのは、この制約に反した入力に対する fail-closed であって、実装の欠陥ではない。**実装を変えると、requirement が意図的に置いた制約を実装側で吸収することになり、二段階適用という運用上の約束が消える。**

対応は、名前解決の失敗メッセージがこの2段階の規約を名指しすることに限る。今回のバッチは新規 template を含まないため、この経路は発火しない。

## 4. 引き継ぐ未確認事項

- Semaphore 2.18.4 が受理する cron grammar(R9④の判定規約)
- 新規 POST に、管理5項目 + `project_id` 以外の必須フィールドがあるか(OQ7)
- AC1〜AC23 の task 層での成立、実 API round-trip、OQ1 / OQ3 / OQ5 / OQ8
