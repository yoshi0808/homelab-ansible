# Counterargument: scripts/codex-classify.sh

作成日: 2026-05-08

---

## 対象レビュー

- `docs/ai/reviews/scripts/codex-classify/2026-05-08_003_review.md`

---

## 受け入れる修正

### 1. 出力スキーマを policy Section 16 に合わせる

`proxmox_patch_policy.md` Section 16 の最低限 JSON 出力に合わせ、以下を追加する。

- `status_inputs.security_sensitive_updates`
- `package_classifications[].evidence`

理由:

- 後続の Ansible tasks が policy 側のスキーマを前提に読む可能性があるため。
- Codex CLI の出力契約を policy と揃えるため。

### 2. JSON 検証を強化する

以下を検証する。

- `package_classifications` が空でないこと
- `package` が `<updates の各パッケージ名に置き換えること>` のままでないこと
- 入力 JSON の `updates` 数と `package_classifications` 数が一致すること

理由:

- Codex がスキーマのダミーをそのまま返す問題を検出するため。
- 入力パッケージごとの分類漏れを防ぐため。

---

## 反論・変更しないこと

### 1. Section 16 のプロンプト追加は行わない

レビューでは、`proxmox_patch_policy.md` の Section 16 もプロンプトに含めるべきと指摘された。

しかし、この修正は採用しない。

理由:

- Section 16.3 にはサンプル JSON が含まれている。
- そのサンプル JSON を Codex がそのまま返すバグが発生することを確認済み。
- 現在の実装では、この問題を避けるために Section 16 を意図的に除外している。

したがって、Section 16 の内容はプロンプトへ直接追加しない。

必要なスキーマ整合は、スクリプト側の出力スキーマ例に `security_sensitive_updates` と `evidence` を明示的に追加することで対応する。

### 2. `codex exec` の呼び出しを stdin に変更しない

レビューでは、長い changelog を扱うために以下の stdin 形式へ変更することが推奨された。

```bash
codex exec < "$PROMPT_FILE" > "$CODEX_OUTPUT" 2>&1
```

しかし、この修正は採用しない。

理由:

- `codex exec < "$PROMPT_FILE"` はすでにテスト済みで、動作しないことを確認済み。
- 現在の環境では、以下の引数形式が正しい動作方法である。

```bash
codex exec "$(cat "$PROMPT_FILE")" > "$CODEX_OUTPUT" 2>&1
```

したがって、`codex exec` の呼び出し形式は現状維持とする。

---

## 今回の対応方針

今回の追加実装では、以下のみを行う。

1. `scripts/codex-classify.sh` の出力スキーマ例に `security_sensitive_updates` と `evidence` を追加する。
2. `scripts/codex-classify.sh` の JSON 検証を強化する。

以下は行わない。

1. Section 16 をプロンプトに追加しない。
2. `codex exec` を stdin 呼び出しに変更しない。

---

## Next step files

- `docs/ai/reviews/scripts/codex-classify/2026-05-08_001_requirement.md`
- `docs/ai/reviews/scripts/codex-classify/2026-05-08_002_implement.md`
- `docs/ai/reviews/scripts/codex-classify/2026-05-08_003_review.md`
- `docs/ai/reviews/scripts/codex-classify/2026-05-08_004_counterargument.md`
