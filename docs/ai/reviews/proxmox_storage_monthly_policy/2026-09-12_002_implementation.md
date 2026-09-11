# 実装記録

既存`proxmox_operations_policy.md`のSB-020へ月次点検をsemi-safe入口として追加し、SB-096〜SB-099を新設した。規定対象はhost/device非変更、全nodeを含む部分失敗、健康状態と処理成否の分離、JSON/Notion/Slackの役割、collect/replay、保持削除、秘密情報、check/通知抑止。

新しいPolicyファイル、実装・schedule変更はない。現行requirement、Operations Context、コードの契約をPolicyへ移し、Contextは引き続き運用上の読み方と実値を持つ。Operations ContextからPolicyの安定IDへ参照を追加し、両文書の責務を明示した。

独立規範レビュー`2026-09-12_003_review.md`はApprove。見出し階層のSuggestionは安定参照を優先して据え置き、判断を`2026-09-12_004_review_response.md`へ記録した。配備操作は不要。
