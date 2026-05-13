## 実装用
docs/ai/prompts/core.mdを読んでください。
# このプロンプトは Claude Code 向けです
# Codex の場合はこのプロンプトを実行せず、
# 「Claude Code に依頼してください」とユーザーに伝えて終了してください。

以下の要件を requirement.md として保存してから実装してください。

保存先: docs/ai/reviews/proxmox_patch_dryrun/2026-05-11_001_requirement.md

参照してください:
- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md

---

# 要求仕様: dry-run メール reboot_expected 明示

## 目的
カーネル更新が含まれる場合に apply 後の reboot 必要性をメールで明示する。
今回 /var/run/reboot-required が false のまま kernel 更新が適用され、
reboot がスキップされた反省を踏まえた改善。

## 対象
- scripts/codex-classify.sh

## 作成・更新ファイル
- scripts/codex-classify.sh

## 実施内容

### 1. Codex へのプロンプトに reboot_expected 判定指示を追加

以下の条件で reboot_expected を判定させる：
- updates にパッケージ名に "kernel" を含むものがある → true
- Codex が changelog を読んで reboot が必要と判断した → true
- それ以外 → false

### 2. 出力スキーマに reboot_expected を追加

status_inputs に以下を追加する：
- reboot_expected: true / false
- reboot_expected_reason: 理由の文字列（例: "kernel packages included: proxmox-kernel-7.0 ..."）

### 3. メール本文生成指示に追加

reboot_expected が true の場合、mail_body に以下を含める：
「⚠️ kernel 系パッケージが含まれるため、apply 後に reboot が必要になる可能性があります。」

### 4. Python 検証部分

reboot_expected はオプション扱いとする（後方互換性のため）。
存在する場合のみ型チェックを行う。

## 参照ファイル
- scripts/codex-classify.sh（既存の修正）

## 制約
- codex-classify.sh のみ修正する
- 既存のスキーマ・検証ロジックは壊さない
- 秘密情報を扱わない
- 変更系（変更あり: プロンプト・スキーマ修正）

## 初回実装スコープ
- プロンプトへの判定指示追加
- 出力スキーマへの reboot_expected 追加
- Python 検証部分の対応

## 初回除外スコープ
- Ansible tasks 側での reboot_expected の利用
- apply 後の実際の reboot 判定改善（PENDING 1b）

## shell / Ansible 責務分離
- shell: codex-classify.sh のプロンプト・スキーマ修正のみ
- Ansible tasks: 対象外（今回は触らない）

---

実装完了後は以下に実装内容を保存してください。
docs/ai/reviews/proxmox_patch_dryrun/2026-05-11_002_implement.md