## Code Review: proxmox_running_versions r2 計画再査読

### Summary

前回のCritical 1件・Major 5件はすべて解消しています。ただし、r2で新たにMajor 2件が生じています。特に、予定されたSemaphore scheduleの有効化手順は現行実装では機能しません。

### 前回指摘の解消判定

| 前回 | 判定 | 根拠 |
|---|---|---|
| Critical 1: 到達不能・収集エラーをrc 0へ畳む | **解消** | 片系unreachableだけを正常終了とし、command/parse errorと全node unreachableを非0・1通知へ分離しています。[requirement.md:56](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:56)。AC2b/AC2cも追加されています。[requirement.md:94](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:94) |
| Major 1: `role-guarded`分類が不適合 | **解消** | `check-mode-native`へ確定し、収集とNotion更新のゲート範囲も定義されています。[requirement.md:64](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:64) |
| Major 2: 最新applyレポートを週次成功と誤認 | **解消** | 意味を「週次パッチ結果」から「最新apply試行」へ変更し、手動・失敗を選別しないこと、公開する実在フィールドを明記しています。[requirement.md:44](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:44)。FAILED fixtureもAC5に追加されています。[requirement.md:99](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:99) |
| Major 3: Notion途中失敗状態が未定義 | **解消** | `updating → node更新 → complete`の順序、読者の有効性判定、再実行による回復が定義されています。[requirement.md:45](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:45)。途中失敗と回復はAC4bで観測可能です。[requirement.md:98](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:98) |
| Major 4: templateとscheduleを別変更にする契約違反 | **解消** | 同じ変更でtemplateとinactive scheduleを追加する形へ改訂されています。[requirement.md:63](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:63)。ただし、後述の新規Major 1があります。 |
| Major 5: 全体statusが未定義 | **解消** | `ok` / `partial` / `error`の値域とnode statusからの集約規則が定義され、AC1・AC2・AC2bでも期待値が指定されています。[requirement.md:47](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:47) |

### 新規Critical

なし。

### 新規Major

| # | 根拠 | Finding |
|---|---|---|
| 1 | [requirement.md:63](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:63)、[semaphore_schedules.py:736](/home/yoshi/homelab-ansible/roles/semaphore_templates/filter_plugins/semaphore_schedules.py:736)、[test_desired_and_diff.py:146](/home/yoshi/homelab-ansible/scripts/tests/semaphore_schedules/test_desired_and_diff.py:146)、[semaphore defaults:768](/home/yoshi/homelab-ansible/roles/semaphore_templates/defaults/main.yml:768) | **後続commitでカタログを`active: true`へ変えても、既存scheduleは有効化されません。** canonical環境では既存scheduleの`active`はoperator-ownedとして観測値を保持し、カタログとの差をdiff対象にしません。この挙動は既存テストでも明示されています。初回reconcileで`active: false`として作成された後は、カタログだけをtrueにする計画では永続的にinactiveのままです。有効化主体と経路を実在する仕組みに合わせて決め直す必要があります。またカタログはschedule追加時点で外部工程表への反映を要求していますが、R8はactive化まで反映を遅らせており、その間07:00が空き枠に見える矛盾もあります。 |
| 2 | [requirement.md:38](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:38)、[requirement.md:92](/home/yoshi/homelab-ansible/docs/ai/reviews/proxmox_running_versions/2026-10-16_001_requirement.md:92)、[fixture:30](/home/yoshi/homelab-ansible/roles/proxmox_patch_dryrun/tests/fixtures_blocked_removes.yml:30) | **`kernel_installed`の「最新」が一意に判定できません。** `proxmox-kernel-*`には系列・ABI・`-signed`を含む複数パッケージが存在しますが、候補をboot可能な実体packageだけにするのかmeta packageも含めるのか、installed状態をどう判定するのか、版比較にdpkg順序を使うのかが未定義です。文字列順では、例えば6.8系と6.14系の順序を誤り得ます。AC1の「dpkgの版と一致」も比較対象が一つに定まらず、受入判定できません。候補集合とDebian version比較規則を要件化し、`kernel_pkg`との比較が同じ版体系で成立することをfixtureで確認する必要があります。 |

### What Looks Good

- 追加・改名されたキーはR2、R4、AC1で一貫しています。
- `pve_qemu_kvm_installed`が稼働中VMのQEMU版ではないことを、キー名・注記・非ゴールで明示しています。
- `state: complete`だけを有効とする読者契約と、26時間の鮮度判定の所在が分離されています。
- 複数障害時のSlackを1通へ集約しており、無音化と重複通知の両方を避けています。
- AC3は3つの抑止条件を個別に検証し、トークン未読と予定本文全体の表示まで観測できます。

### 推奨テスト

- inactiveで新規作成したscheduleについて、カタログだけをtrueへ変更しても現行reconcileでは有効化されないケースを確認し、改訂した有効化経路をテストする。
- 複数kernel系列、meta package、boot可能な実体package、Debian revisionを混在させ、`kernel_installed`の選択をassertする。
- `kernel_pkg != kernel_installed`と一致するケースをそれぞれ用意し、再起動待ちの読み取りが成立することを確認する。

### 未確認

- 固定Notionページの共有状態。
- quory上の実applyレポート。
- 外部のバッチ処理工程管理表と07:00枠。
- 実Notion APIでのコードブロック更新挙動。

### Verdict

**Request Changes**

返却時点でも対象ディレクトリ全体が未追跡で、査読中のファイル変化はありません。こちらから変更は行っていません。