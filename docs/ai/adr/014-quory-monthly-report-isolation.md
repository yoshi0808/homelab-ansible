# ADR-014: quory月次レポートを独立した観測・公開経路にする

**Status:** Proposed

## Context

quoryの容量・メモリ・NVMe健康情報を月次で記録する。既存のProxmox月次レポートはZFS pool・vdev、2ホスト集約、専用Notion親ページを前提とする。一方、quoryは単一の`control_nodes`ホストで、ext4/EFIとメモリを扱い、Notion投稿先も分ける。月次観測へパッケージ導入を混ぜない。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| 既存Proxmox roleへquory分岐を追加 | 投稿・履歴の既存経路をそのまま使える | host構成と判定の異なる2業務が結合し、既存の定期ジョブへ回帰リスクが及ぶ |
| 共通部を抽出して両roleを同時に移行 | 重複を抑えられる | 稼働中のProxmox月次ジョブまで変更し、初回導入の検証範囲が広がる |
| **quory専用roleと投稿先を作る** | 観測・判定・保存・再送を分離して検証できる | Notion/履歴の安全契約を新roleでも検証する必要がある |

## Decision

quory専用playbook/role、保存ディレクトリ、Notion親ページを設ける。既存`homelab-report` Integrationのtokenファイルは再利用し、quory専用ページへの権限を別途確認する。`common_slack`の通知入口とinventoryの`reports_base_dir`も再利用する。Proxmox実装は安全契約の参照とし、既存roleの挙動を変更しない。汎用コードを直接流用できるかはImport可能性を実装前に確認し、Proxmox既存経路を変える必要があれば本案件では複製を明示して独立テストする。NVMe取得ツールの導入は別の配備入口とし、観測入口はread-onlyに保つ。

## Trade-off Analysis

初回の重複量より、既存の本番月次ジョブを変えずにquory固有の失敗・通知・再送を試せることを優先する。共通化の価値は両業務の運用実績を得てから判断する。

## Consequences

- quory用のJSON/Markdown、Notion月次ページ、Semaphore template/scheduleはProxmoxと別identityにする。
- Notionのtoken検査・TLS・応答不明時の重複防止、保存時の原子性と保持保護は新経路のテスト対象になる。
- 導入前に、Semaphore実行コンテキストでのデバイス・ツール・権限と、専用NotionページのIntegration権限をreadbackする。
