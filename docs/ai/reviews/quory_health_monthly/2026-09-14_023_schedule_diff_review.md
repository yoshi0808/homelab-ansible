# quory月次ヘルス schedule登録 差分レビュー

## Code Review: roles/semaphore_templates/defaults/main.yml (schedule追加) / docs/ai/reviews/quory_health_monthly/2026-09-14_022_schedule.md

### Summary

契約の5項目(schedule追加の5フィールド、templateコメント更新、cron義務コメント、既存schedule不変、`environment`の値)をすべて現物で確認し、いずれも満たされている。requirementに無い実装・記述の混入は無い。`roles/semaphore_templates/` のreconcileが前提とするデータ形状(識別キー`name`、`template`名の生成規則、`task_params.environment`がJSON文字列でありdictでないこと)とも整合する。実装記録の記述は現物のdiffおよび同ディレクトリの先行記録(`2026-09-14_021_deployment_observation.md`)と食い違いが無い。blocking findingなし。

### Critical Issues

なし。

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | roles/semaphore_templates/defaults/main.yml | 881 (追加schedule) | 新規schedule追加は識別キー`name`と生成規則上の`template`名が一致する形(既存の`SEMI-SAFE: Proxmox storage monthly`と同型)になっており、`同定はnameで行う`という既存規約(753行目近辺のコメント)から外れていない。指摘ではなく確認事項として記録する。 | Suggestion(確認のみ、対応不要) |

### What Looks Good

- **schedule追加の5項目**: `name`/`template`ともに`"SEMI-SAFE: Quory health monthly"`で、`roles/semaphore_templates/filter_plugins/semaphore_templates.py`の命名規則(`"{class}: {title}"`)が`semaphore_templates_catalog`の`quory_health_monthly`エントリ(`class: SEMI-SAFE`, `title: "Quory health monthly"`)から生成する名前と一致することを確認した。`cron: "15 8 15 * *"`(毎月15日08:15)、`active: true`、`task_params.environment: "{}"`も契約どおり。`_REQUIRED_CATALOG_FIELDS`(`semaphore_schedules.py`)が要求する5フィールドと一致し、余剰フィールドは無い。
- **`environment`の型**: YAML上`"{}"`という文字列(クォート付き)であり、`main.yml`753行目のコメント「`task_params.environment`はJSON文字列でありdictではない」という既存契約、および`semaphore_schedules.py`の`_environment_public_problems`がstr型を要求する実装と一致する。dictへ変えていない。
- **operationの非複製**: `task_params`に`operation`相当のキーを追加しておらず、`roles/quory_health_monthly/defaults/main.yml:2`の既定値`collect`を正本のまま維持している。
- **templateコメント更新**: `semaphore_templates_catalog`側の`quory_health_monthly`エントリのコメントを、旧「scheduleは未確定のため追加しない」から「readback確認済みでscheduleを下記へ登録する」へ書き換えており、schedule追加という事実と食い違う記述が残っていない。
- **既存scheduleの不変性**: `git diff`で新規追加ブロック以外に変更が無いことを確認した。追加箇所直前の`SEMI-SAFE: Proxmox storage monthly`(`cron: "0 8 15 * *"`)を含め、`semaphore_schedules_catalog`全24件のうち新規1件を除く23件の`name`が重複なく、既存のパターン(第1〜3バッチの記法)を壊していない。
- **cronを決める義務への対応**: 追加したコメントが「この行自身が枠を占有する」ことと、Notion表との突合をCoordinatorが実施済みである旨を明記しており、`main.yml`冒頭の「cronを決める・変えるときの義務」節が要求する記録を満たしている。
- **実装記録の現物一致**: `2026-09-14_022_schedule.md`の「既存23件」という記述を、`semaphore_schedules_catalog:`以降の`- name:`出現数(python3で機械カウント、diff適用前相当=新規追加を除けば23)で裏取りした。時刻・所要時間の記述(31秒 / 13〜28秒)はCoordinatorから渡された確定事実および先行記録`2026-09-14_021_deployment_observation.md`(job #1094が約27秒)と矛盾しない。
- **セキュリティ観点**: 今回の変更はYAMLデータのみで、shell/commandモジュールや変数注入・`no_log`・`delegate_to`に関わる実装差分は無い。攻撃面の追加なし。
- **重複・再利用**: 新規ロジック追加は無く、既存の`SEMI-SAFE: Proxmox storage monthly`エントリと同型のパターンを踏襲しているのみ。

### 未解決事項

- Semaphoreへの適用(reconcileの実行)、schedule readback、次回実行時刻の確認はこの案件の範囲外であり未実施(依頼文どおり)。適用後の受入検証はTesterの担当。
- Yoshinobuによる「毎月15日08:15 JST」の承認そのもの、およびNotion「バッチ処理工程管理表」との突合結果は本リポジトリ外の事実であり、Reviewerとしては現物確認できない。Coordinatorから渡された確定事実として扱った。

### Verdict

Approve

## 確認範囲

- `git diff roles/semaphore_templates/defaults/main.yml`(全文)。
- `docs/ai/reviews/quory_health_monthly/2026-09-14_022_schedule.md`(全文)。
- `roles/semaphore_templates/filter_plugins/semaphore_templates.py`(name生成規則)、`roles/semaphore_templates/filter_plugins/semaphore_schedules.py`(必須フィールド・`environment`の型検証ロジック)。
- `roles/semaphore_templates/defaults/main.yml`の`semaphore_templates_catalog`中`quory_health_monthly`エントリと`semaphore_schedules_catalog`全体(既存23件+新規1件、`- name:`のPython集計で重複無しを確認)。
- `roles/quory_health_monthly/defaults/main.yml`(`operation`既定値)。
- 同ディレクトリの先行記録`2026-09-14_021_deployment_observation.md`との突合。
- 実ホスト・Semaphore APIへは到達していない(Reviewerの権限外)。
