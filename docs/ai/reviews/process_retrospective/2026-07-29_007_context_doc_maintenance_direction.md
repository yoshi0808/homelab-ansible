# ドキュメント保守責任の分担(方向性合意、実装は別途)

状態: **方向性合意**(2026-07-29)。実装は未着手。

## 問い

`docs/ai/context/system/`・`docs/ai/context/operations/`等の維持は今回有用と判断し残したが(`2026-07-29_006_ansible_context_map_retirement.md`と対になる判断)、Yoshinobuから「これまで通りrequirement・Policy策定とテスト合否判定はYoshinobuが行うが、今回のドキュメント群は誰が保守するのか」という問いがあった。

## 合意した分担

- **Policy(`docs/ai/policies/*_policy.md`)・requirement・テスト合否判定**: 引き続きYoshinobu(変更なし)。
- **それ以外(`docs/ai/roles/*.md`、`skills/*`、System/Operations Context、`docs/ai/context/ansible/`等)**: Coordinatorが保守する。

## なぜ「Coordinatorが保守する」だけでは不十分か

地図3ファイル(`2026-07-29_006_...md`参照)が示した教訓——「更新することになっている」という独立したルールは、書いても実行されないことが4回実証されている——を繰り返さないため、次の2点を実際の仕組みとして機能させる方向で合意した。**いずれも未実装。**

1. **Context更新を独立タスクにしない。** Context記載の環境事実に触れる変更では、その案件のStep計画に「Context更新」をStepとして含める(実装Stepと同格に扱う)。`docs/ai/roles/coordinator.md`への明文化が必要(未着手)。
2. **月次Knowledge振り返りへ、Context現物との突合を追加する候補として残す。** 既存の`ansible-knowledge-review.timer`(自律実行、`claude -p`、commit/pushはせず作業ツリーに残しYoshinobuがcommitする)を拡張する案。

## 実装に先立って詰める技術的な論点

無人実行(`docs/ai/role-routing-index.md`「無人実行されるCoordinator」)の読み取り可能範囲は現状`docs/`・`skills/`・auto-memoryのみで、Context記載内容の照合対象である`roles/`・`playbooks/`・`inventories/`を読めない。これは`docs/ai/memory/lessons/claude-code-unattended-session-confinement.md`に基づく意図的な設計であり、拡張する場合は次を決める必要がある。

- `roles/`・`playbooks/`・`inventories/`への読み取りを許可するか。
- 許可する場合、`inventories/vars/`(秘密を含み得るパス)をどう除外するか。

## 関連

- `docs/ai/reviews/process_retrospective/2026-07-29_006_ansible_context_map_retirement.md`
- `docs/ai/reviews/process_retrospective/2026-07-29_005_techlead_retirement.md`§4(「残る穴」として同種の課題を既に起票)
- `docs/ai/role-routing-index.md`「無人実行されるCoordinator」
