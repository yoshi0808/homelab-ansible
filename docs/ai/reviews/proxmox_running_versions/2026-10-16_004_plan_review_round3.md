## Code Review: proxmox_running_versions r3 計画再査読

### Summary

round 2のMajor 2件は両方とも解消しています。ただし、R3の意味とユーザーストーリーの間に残存するMajor 1件を新たに確認しました。これはr3で導入された問題ではなく、r2から残っていた不整合です。

### round 2指摘の解消判定

| 前回 | 判定 | 根拠 |
|---|---|---|
| Major 1: inactive scheduleを後続commitだけでは有効化できない | **解消** | 有効化主体をYoshinobuによるSemaphore UI操作へ変更し、その後の`active: true`は実行効果ではなくカタログ表示を実態へ揃えるものと明記しています。工程管理表もinactive schedule追加時に更新します。[requirement.md:63](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:63)。これは既存scheduleのactiveを観測値から保持する実装と整合します。[semaphore_schedules.py:743](/home/yoshi/homelab-ansible/roles/semaphore_templates/filter_plugins/semaphore_schedules.py:743) |
| Major 2: `kernel_installed`の候補と版比較が未定義 | **解消** | boot可能な実体package、installed状態、meta/helper除外、Debian版比較、候補なし時の失敗が定義されています。[requirement.md:36](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:36)。AC1とAC1bで実値照合、複数系列、signed/non-signed、非installed、meta packageを観測できます。[requirement.md:92](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:92) |

### 新規Critical

なし。

### 新規Major

| # | 根拠 | Finding |
|---|---|---|
| 1 | [requirement.md:26](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:26)、[requirement.md:44](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:44)、[requirement.md:100](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:100) | **ユーザーストーリーが要求する「直近の週次パッチで再起動したか」は、R3の出力から判定できません。** R3は最新の週次・手動・成功・失敗を区別せず、最新apply試行だけを採用します。週次成功の後に手動applyや失敗試行があれば、その`reboot_done`で週次結果が上書きされます。AC5もFAILEDを最新値として公開する契約です。R3の制約を採るならユーザーストーリーを「直近のapply試行」に修正する必要があります。週次結果が本当に必要なら、現行レポートに出所がない以上、別の識別可能な正本が必要です。 |

### What Looks Good

- scheduleの生成、手動確認、UI有効化、カタログ追随、工程表更新の主体と順序が明確です。
- `kernel_pkg`と`kernel_installed`は同じ版体系として比較でき、文字列ソートを明示的に排除しています。
- 候補0件を正常値へフォールバックせず、node errorへ倒しています。
- r2までに解消された終了コード、Notion更新状態、tester-gate、全体statusの契約も維持されています。

### 推奨テスト

- kernel fixtureについて、Debian revisionやepochを含む文字列順とDebian版順が異なるケースもAC1bへ含める。
- R3の最終仕様に合わせ、週次成功後に手動またはFAILED applyが存在するfixtureで、読者がフィールドの意味を誤認しないことを確認する。

### 未確認

- 固定Notionページの共有状態。
- quory上の実applyレポート。
- 外部の工程管理表と07:00枠。
- 実Notion APIでのコードブロック更新挙動。

### Verdict

**Request Changes**

返却時点でも対象ディレクトリ全体が未追跡で、査読中のファイル変化はありません。こちらから変更は行っていません。