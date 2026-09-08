# Code Review: schedule operation key preflight修正

作成: 2026-09-09 / Reviewer（追加差分レビュー）

### Summary

schedule preflightの実装と回帰テストは、2つのnamespaced operation keyを`environment`だけに追加し、key別enum・native `params`・既存closed-world/secret非露出/identityの境界を維持している。job #1027相当テストも公開preflightとdiffの実consumerを通っており、コード修正にblocking findingはない。一方、同じ差分のIncidentが、原因判明・修正確認済みの実装記録と矛盾して未完成のため、記録契約上のMajorが1件残る。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/memory/incidents/2026-09-09_schedule_operation_keys_rejected.md` | 4-26 | 実装記録010では原因を確定し、修正内容と97件の回帰テスト成功まで記録しているのに、Incidentは`状態: 調査中`、`原因分類: 調査中`、原因も「現時点では」のままで、修正内容・確認方法が空である。`incident-recording`の「原因判明後に同じファイルを完成」「修正の確認が取れた時点で解決済み」という契約に反し、月次振り返りでも解決済み原因タグの集計から恒常的に漏れる。`状態: 解決済み`へ更新し、確定原因、該当する原因分類（少なくともallowlist同時更新漏れと回帰テスト不足を表す分類）、修正内容、今回のlocal確認、および実Semaphore再実行が未確認であることを記録する必要がある。 | Major |

### Suggestions

なし。

### What Looks Good

- **environment限定とenum境界**: `ubuntu_vm_full_upgrade_operation`は`inspect|apply`、`prometheus_update_check_operation`は`inspect|update|rollback`だけをkey別に許可する。相互取り違え、enum外文字列、bool/intはいずれも公開`semaphore_schedules_preflight`から拒否されることを追加spot-checkした。
- **native params軸の分離**: `_PARAMS_ALLOWED_KEYS`は既存3 primitive keyのままで、operation keyは含まれない。両operation keyを`task_params.params`へ置いた場合も未知keyとして拒否される。
- **closed-worldとsecret非露出**: top-level allowlistは`environment|params`の2つから変わらず、primitive key/value型も既存suiteで回帰している。operation値エラーはpathと型だけを返し、拒否値そのものを診断へ含めない。
- **identity非変更**: 今回の実装差分はpreflight filterだけで、catalog、schedule/template名、legacy identityを変更していない。job #1027相当テストは既存schedule ID 2件を`new=0`、`task_params`だけのin-place `changed`として検出する。
- **空振りでない回帰テスト**: 新規テストは実filter pluginをimportし、公開`semaphore_schedules_preflight`の`errors`・`unmanaged`・解決済みID mapを、そのまま公開`semaphore_schedules_diff`へ渡して結果をassertしている。テスト専用の再実装や定数だけの比較ではない。
- **Security / reuse**: 既存の単一allowlist walkerを軸別key集合・validatorへ一般化しており、別の検査経路を重複実装していない。shell、外部入力のコマンド展開、API/secret出力の追加はない。
- **local checks**: schedule unit suite 97 tests、Semaphore task-flow 6 scenarios、doc consistency 3 checks、`git diff --check`はすべてrc=0。追加spot-checkもrc=0だった。

### 未確認事項

- 実Semaphoreでのcatalog reconcile再実行、schedule readback、通常inspection/Slack通知。Reviewerの境界に従い、実ホスト・quory・API・Slackには触れていない。
- commit / pushは実施していない。

### Verdict

**Request Changes** — Critical 0 / Major 1 / Minor 0。schedule preflightのコードとテストは要求を満たすが、Incident完成契約に反するMajorが残るためApproveしない。
