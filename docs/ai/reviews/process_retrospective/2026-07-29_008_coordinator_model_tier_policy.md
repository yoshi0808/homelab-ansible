# Coordinatorのモデル選択方針(2026-07-29)

状態: **決定**。Yoshinobu提案「Policy見直し等は上位モデルが必要だが、playbook程度の作成ならSonnetで十分ではないか」にCoordinatorが妥当性を検討し、「Opus以上を原則、Tier 1/2の直接実装に限りSonnet可」で合意(2026-07-29)。

## 背景

このセッション自体がFableで動いていたが、`docs/ai/role-routing-index.md`は「Coordinator: Opus」と記載しており、既に実態と乖離していた。

## 決定

- **原則: Coordinatorは`Opus`以上のモデルで動かす。** 「以上」は特定の1モデルへ固定しない(将来のモデル追加を見込む)。
- **例外: Tier 1/2の直接実装(Coordinator自身がplaybook等を書く場面)に限り、Sonnetでもよい。**
- **Tier判定そのもの、およびTier 3/4(要求分解・ADR・リスク整理・見積もり)は、上記の例外に含めない。** 常にOpus以上で行う。
- モデルの選択はYoshinobuが行う(Coordinator自身が自分のモデルを切り替える手段は無い)。Yoshinobuが難易度を高いと判断した場合は、Tier 1/2相当でも上位モデルを使ってよい。

## なぜTier判定・Tier3/4を例外に含めないか

`docs/ai/role-routing-index.md`「モデル・effort配分」が既に記録している実測が根拠である。2026-07-26のTier 4フルサイクルで、Opus級の判断が必要だったのは**「あるべきものが無い」ことの検出**(`docs/ai/core.md`が旧モデルのまま残っていたドリフト、決定根拠がリポジトリに存在しなかった欠落)であり、これはCoordinatorの領分だった。本日(2026-07-29)一連の作業(Auditor起動条件の自己矛盾、Tech Lead廃止の要否判断、Ansible地図3ファイルの要否判断)も同じ「あるべきものが無いことの検出」型であり、Coordinator自身がTier 3/4の分解・判断を担う現体制ではこの検出力がCoordinatorのモデル能力に直結する。

## 残るリスク(受容)

Tier判定は着手前に行うため、「Sonnetで始めたところ、想定より難しいと判明した」ケースの検出はモデル能力に依存し続ける。「不確実だと自覚して止まる」判断は比較的弱いモデルでもできるが、「不確実だと気づかずに見落とす」は本日の欠陥の大半がこの型だった。既存の「迷ったら上げてよい」エスカレーション文化(`docs/ai/roles/coordinator.md`)と、Yoshinobuの上流での難易度判断が補完する。運用しながら見落としの増減を観察する。

## 関連

- `docs/ai/role-routing-index.md`「モデル・effort配分」
