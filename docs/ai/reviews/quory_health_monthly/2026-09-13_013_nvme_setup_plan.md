# quory NVMe取得ツール配備 — 計画追補

対象要求: `2026-09-13_012_nvme_setup_requirement.md`。既存の001/002および`docs/ai/policies/quory_health_monthly_policy.md`に従う。

1. quory限定のsetup playbookとroleを新設する。入口は`check-mode-native`とし、事前の対象検査、check時の非変更、通常実行時の冪等導入、導入後のコマンドreadbackを分ける。導入後にコマンドが使えなければrc非0で止める。観測playbookと既存ホストのroleは変更しない。
2. Semaphoreのtemplate catalogへ、既存setup系に倣う`SEMI-SAFE`の手動用setupテンプレートを追加し、scheduleは追加しない。`playbooks/README.md`とquory月次Operations Contextを更新する。
3. Implementerは実ホストに触れずに構文・lint・対象guard/check境界を検証し、別identityのCodex Reviewerが差分を独立確認する。Testerはローカルで成立する範囲だけを検証し、実quoryでのパッケージ導入・CLI実行・健康ジョブ再実行はNot Runと明示する。実host名入りinventoryをdecoyと呼ばない。
4. 承認後のcommit/push、Yoshinobuによるtemplate setup check→apply→readback、専用setup check→apply→readback、月次ヘルスジョブ`--check`の順とする。Notion親ページ・月次scheduleは引き続き別工程であり、有効化しない。

配備前に残る判断: setup checkの差分、実quoryでのCLI readback、健康ジョブ`--check`の観測値。これらを満たすまでは通常collectを起動しない。
