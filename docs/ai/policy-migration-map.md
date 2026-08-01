# Policy構造標準化 移行追跡表

状態: **凍結(歴史的記録)**。2026-07-24時点のPolicy構造への1回限りの移行追跡表であり、対象Policyはその後複数回改訂され、行番号は現物と一致しない。どの生きた文書からも参照されていない。「role-map」「playbook-map」への言及は2026-07-29に廃止済みのファイルを指す(`docs/ai/reviews/process_retrospective/2026-07-29_006_ansible_context_map_retirement.md`)。参照する場合は現物のPolicy・コードを優先する。

対象: `docs/ai/core.md` と `docs/ai/policies/*_policy.md` 9本（2026-07-24時点、計10文書）。

本表は既存文書を書き換える前の構造索引である。既存記述と実装の意味的整合性は判定せず、標準構造への対応、論理group、Policy境界を追跡する。

## 標準テンプレート

将来の個別Policyは、該当する範囲で次の8セクションをこの順に持つ。

| # | 標準セクション | 収容する情報 |
|---|---|---|
| 1 | 目的 | Policyが守る対象、解決する運用上の問題 |
| 2 | 対象と実行範囲 | 対象、実行元、許可範囲、安全度、対象外との境界 |
| 3 | 対応するPlaybook | Policyを実装する入口playbookと主role。実装詳細そのものはRepository Contextまたはコードを正本とする |
| 4 | 判断軸 | Status、Urgency、閾値、合否、続行・停止・人間判断への移管条件 |
| 5 | ライフサイクル・処理フロー | 許可された処理順序、前提、失敗時・cleanup・復帰の流れ |
| 6 | 通知方針 | 通知条件、重要度、宛先種別、best-effortか否か |
| 7 | 制約・禁止事項 | 許可しない操作、秘密・安全境界、停止条件、明示的な除外 |
| 8 | 変更履歴 | 版、日付、構造または判断基準の変更概要 |

### セル判定

- **対応**: 既存の見出し付き範囲が標準セクションの目的を実質的に担う。見出し名が完全一致しなくてもよい。
- **未整備**: 対象業務には必要だが、独立した見出しまたは必要な記述がない。関連情報が別節に散在する場合は、その参照も併記する。
- **該当なし**: 文書種別または対象業務の性質上、その標準セクションを要求しない。欠落とは数えない。

`core.md` は個別業務Policyではなく全Role共通原則であるため、対応Playbook、ライフサイクル、通知方針は「該当なし」とする。変更履歴は正本保守のため必要と判断し「未整備」とする。

## 10文書 × 8セクション対応表

行番号は2026-07-24時点の現行ファイルに対する1始まりの行番号である。

| 文書 | 目的 | 対象と実行範囲 | 対応するPlaybook | 判断軸 | ライフサイクル・処理フロー | 通知方針 | 制約・禁止事項 | 変更履歴 |
|---|---|---|---|---|---|---|---|---|
| `core.md` | 対応: 「目的と正本」L5-14 | 対応: 「人間の権限と安全境界」L16-24、「開発と本番の境界」L26-37 | 該当なし: 個別業務の実行入口を定義する文書ではない | 対応（全体安全ゲート）: 「人間の権限と安全境界」L16-24、「Ansible変更の共通ゲート」L73-78 | 該当なし: 個別処理の順序を定義する文書ではない | 該当なし: 個別業務の通知を定義する文書ではない | 対応: 「公開情報と秘密情報」L39-46、「Ansible変更の共通ゲート」L73-78 | 未整備: 正本の変更履歴見出しなし |
| `autonomous_recovery_policy.md` | 対応: 「1. 目的」L14-16 | 対応: 「2. 対象と適用される復旧手段」L20-35 | 未整備: 標準見出しなし。入口は「5. 検知経路」L163-205と「8. 人間による手動レイヤー実行」L251-263に散在 | 対応（概念相当）: 「5.1 Pull」L165-187の閾値・flapping・ラダー分岐、「7. Mute / 一時停止機構」L227-247のskip・再開gate | 対応: 「5. 検知経路」L163-205 | 対応: 「9. 通知」L267-269 | 対応: 「6. Codex実行環境の安全設計」L208-223、「10. 禁止事項」L273-282、「11. 既知の制約」L286-288 | 未整備: 変更履歴見出しなし |
| `cert_renew_cloudkey_policy.md` | 対応: 「2. 目的」L34-43 | 対応: 「3. 対象と実行経路」L46-59 | 対応: 「対応するPlaybook」L61-65 | 対応（概念相当）: 「8. 命名と削除条件」L166-189、「9. 配信検証」L193-207 | 対応: 「6. 処理フロー」L122-135 | 対応: 「11. 失敗検知・通知」L226-237 | 対応: 「10. 認証情報・秘密鍵の扱い」L211-222、「13. リスクの明示」L253-262、「14. 除外対象」L266-275 | 対応: 「変更履歴」L9-13 |
| `cert_renew_policy.md` | 対応: 「1. 目的」L19-22 | 対応: 「2. 対象サービス」L26-35 | 対応: 「対応するPlaybook」L49-56 | 対応（概念相当）: 「7. 中間CA有効期限監視」L149-165、「8. 失敗検知」L169-179、「9. 証明書仕様」L182-189 | 対応: 「5. CA証明書の一時展開とcleanup」L116-126、「6. フルチェーン配布」L130-145、「10. CA復旧・移行手順」L193-243 | 対応: 「8. 失敗検知」L169-179 | 対応: 「4. CA構成」L60-113、「11. 除外対象」L246-253 | 対応: 「変更履歴」L10-15 |
| `log_observability_policy.md` | 対応: 「1. 位置づけ」L13-15 | 対応: 「2. アーキテクチャ」L17-34、「3. 現状構成」L36-68 | 対応: 「対応するPlaybook」L70-72 | 対応（概念相当）: 「4. Alloy運用方針」L74-83の検証・cutover・人間ゲート | 対応: 「4. Alloy運用方針」L74-83、「5. Phaseロードマップ」L85-90 | 未整備: 「5. Phaseロードマップ」L90に将来のSlack構想のみあり、現行通知方針なし | 対応: 「6. 制約・禁止事項」L92-105、「7. 不採用の代替案と管理境界」L107-112 | 対応: 「変更履歴」L7-11 |
| `proxmox_backup_restore_verify_policy.md` | 対応: 「1. 目的」L14-20 | 対応: 「2. 対象と実行」L24-41 | 対応: 「対応するPlaybook」L43-47 | 対応（概念相当）: 「5. 正常性判定」L104-116、「6. ロック方針」L120-153、「7. cleanupと終了判定」L157-163 | 対応: 「4. ライフサイクル」L81-100、「7. cleanupと終了判定」L157-163 | 対応: 「8. 通知」L167-178 | 対応: 「9. 制約」L182-189、「10. スコープ」L193-204 | 未整備: 変更履歴見出しなし |
| `proxmox_operations_policy.md` | 対応: 「1. 目的」L9-22 | 対応: 「4. ノードの役割」L145-159、「5. VM配置・退避・復帰方針」L162-320、「11. 土曜朝の自動パッチ運用」L1127-1336 | 対応（別名見出し／標準名未統一）: 「6. Playbook分離方針」L324-850 | 対応（明示）: 「3. 判断軸」L71-141、「7. 重要コンポーネント」L852-887、「8. Status判定ルール」L891-1015、「9. removeの扱い」L1019-1045、「10. Urgency判定」L1049-1123 | 対応: 「5. VM配置・退避・復帰方針」L162-320、「11. 土曜朝の自動パッチ運用」L1127-1336、「17. 実適用時の標準手順」L1805-1884、「18. 復旧方針」L1886-1930 | 対応: 「15. メール通知ルール」L1545-1614 | 対応: 「2. 基本方針」L26-67、「11.6 停止する条件」L1304-1319、「12. 保留方針」L1340-1352、「13. BLOCKED時のContingency Plan」L1356-1412、「16.8.3 apply停止条件」L1785-1789、「20. Sophos移行後の追加ルール」L1950-1960 | 未整備: 変更履歴見出しなし |
| `time_sync_check_policy.md` | 対応: 「1. 目的」L26-37 | 対応: 「2. 対象と実行」L41-52、「3. 対象と取得方式」L63-96 | 対応: 「対応するPlaybook」L54-59 | 対応（概念相当）: 「3. 対象と取得方式」L76-81の閾値、「4. ライフサイクル」L100-115の基準ノードゲート | 対応: 「4. ライフサイクル」L100-115 | 対応: 「5. 通知方針」L119-129 | 対応: 「6. 制約・禁止事項」L132-145、「8. スコープ」L163-176 | 対応: 「変更履歴」L18-22 |
| `ubuntu_vm_patch_policy.md` | 対応: 「1. 目的」L10-21 | 対応: 「2. 対象ノードと特性」L25-43 | 対応（別名見出し／標準名未統一）: 「5. Playbook構成」L133-173 | 対応（概念相当）: 「3.3 月次full-upgrade判定」L71-77、「3.4 非apt管理プロダクト」L79-91、「4.3 reboot判定」L124-129 | 対応: 「3. パッチ適用方針」L47-91、「4. reboot方針」L95-129、「5. Playbook構成」L133-173 | 対応: 「6. 通知方針」L177-235 | 未整備: 独立した制約見出しなし。規範は「3. パッチ適用方針」L47-91と「4. reboot方針」L95-129に散在 | 未整備: 変更履歴見出しなし |
| `unifi_backup_fetch_policy.md` | 対応: 「2. 目的」L40-49 | 対応: 「3. 対象と実行」L53-64 | 対応: 「対応するPlaybook」L66-72 | 対応（概念相当）: 「4. ライフサイクル」L76-87の取得・確定・cleanup・再fail条件、「7. 鮮度ガード」L129-137 | 対応: 「4. ライフサイクル」L76-87 | 対応: 「8. 通知方針」L140-150 | 対応: 「10. 制約・禁止事項」L167-176 | 対応: 「変更履歴」L15-19 |

### 見出し実測の補足

- 変更履歴見出しはPolicy 9本中5本にあり、4本にない。欠落は `autonomous_recovery`、`proxmox_backup_restore_verify`、`proxmox_patch`、`ubuntu_vm_patch`。`core.md` にもない。
- requirementの「4/9本にしかない」は現行実測の5/9と一致しない。本表は現行ファイルを正とする。
- 標準名の独立した「対応するPlaybook」見出しはPolicy 9本中6本にあり、`autonomous_recovery`、`proxmox_patch`、`ubuntu_vm_patch`の3本にない。後二者には対応内容が別見出しで存在するため、セルには参照範囲を併記した。

## 判断軸の位置づけ

| 文書 | 区分 | 標準「判断軸」への扱い |
|---|---|---|
| `core.md` | 概念相当 | 個別Statusではなく、権限・危険操作・Ansible変更ゲートを全体安全判断として置く |
| `autonomous_recovery_policy.md` | 概念相当 | probe失敗回数、flapping、VM状態、復旧結果によるラダー続行・停止と、対象別mute / global pauseによるskip・再開gateを明示する |
| `cert_renew_cloudkey_policy.md` | 概念相当 | 配信検証合否と旧証明書削除条件を判断軸としてまとめる |
| `cert_renew_policy.md` | 概念相当 | 証明書更新閾値、中間CA残存日数、cleanup成否を判断軸としてまとめる |
| `log_observability_policy.md` | 概念相当 | cutover前検証、人間ゲート、rollback条件を判断軸としてまとめる。ログseverity契約自体はデータ分類であり運用判断軸とは分ける |
| `proxmox_backup_restore_verify_policy.md` | 概念相当 | 正常性合格基準、残骸・所有判定、cleanupと終了コードを判断軸としてまとめる |
| `proxmox_operations_policy.md` | 明示的に実在 | Status/Urgencyを標準節へそのまま移す |
| `time_sync_check_policy.md` | 概念相当 | 基準ノードの同期可否、方式別offset閾値、収集失敗を判断軸としてまとめる |
| `ubuntu_vm_patch_policy.md` | 概念相当 | 月次判定のStatus昇格、reboot要否、healthcheck結果を判断軸としてまとめる |
| `unifi_backup_fetch_policy.md` | 概念相当 | 鮮度ガード、取得・確定・cleanup成否を判断軸としてまとめる |

「該当なし」は、合否・閾値・続行停止のいずれも業務上存在しない場合に限る。現行9 Policyには何らかの判断ゲートが存在するため、判断軸セルで「該当なし」とした文書はない。

## 目的別論理groupの実装突合

この6案は既存Policy全体を網羅する分類ではない。ファイル統合は行わず、次回書換時の論理索引として扱う。「主role」は、列挙した入口の中核処理・判定を実装する機能roleを実名で列挙し、`common_slack`、`recovery_mute`のような複数領域共通の補助roleは除外する。playbook内tasksだけで実装されroleがない処理は、role欄へ追加しない。

| # | 論理group案 | 実playbook | 主role | 判定と叩き台との差分 |
|---|---|---|---|---|
| 1 | 健康監視（Proxmox/Ubuntu横断） | `proxmox_healthcheck.yml`、`proxmox_hw_check.yml`、`monitoring_healthcheck.yml`、`radius_healthcheck.yml` | `proxmox_healthcheck`、`proxmox_hw_check`、`monitoring_healthcheck`、`radius_healthcheck` | **条件付き妥当**。`proxmox_hw_check.yml`だけでなく、同じ収集→判定→report型の3入口を追加する。`monitoring_healthcheck.yml`と`radius_healthcheck.yml`のPolicy ownerは`ubuntu_vm_patch_policy.md`のままとし、group 1は横断参照のための論理indexとして扱う。`proxmox_snapshot_check.yml`はsnapshot鮮度・保持状態、`time_sync_check.yml`は時刻同期という独立目的なので除外し、必要なら横断health indexから参照する |
| 2 | アプリ・パッケージ更新（apt/非apt横断） | `codex_update_check.yml`、`prometheus_update_check.yml`、`ubuntu_vm_full_upgrade.yml`、補助的に`ubuntu_nightly.yml` | `codex_update_check`、`prometheus_update_check`、`ubuntu_vm_full_upgrade`、`radius_healthcheck`、`monitoring_healthcheck` | **妥当だが更新とrebootを分離表示**。叩き台へ`ubuntu_vm_full_upgrade.yml`を明記し、`ubuntu_nightly.yml`は更新適用ではなくrebootライフサイクルとして従属扱いにする。`alloy_setup.yml`はaptを使っても構成配備・cutoverが目的なので除外する |
| 3 | Proxmoxパッチ（独立維持） | `proxmox_healthcheck.yml`、`proxmox_patch_dryrun.yml`、`proxmox_evacuate_node.yml`、`proxmox_patch_apply_node.yml`、`proxmox_patch_weekly_full.yml`、`proxmox_restore_vm_placement.yml` | `proxmox_healthcheck`、`proxmox_patch_dryrun`、`proxmox_evacuate_node`、`proxmox_patch_apply_node`、`proxmox_restore_vm_placement` | **妥当**。複数の安全度、退避、再起動、復帰を束ねるため独立を維持する。healthcheckはgroup 1からも参照するがPolicy ownerはProxmox patchのままとする |
| 4 | 構成ドリフト検知 | `systemd_timers.yml`、`proxmox_snapshot_check.yml` | `systemd_timers`、`proxmox_snapshot_check` | **不成立、統合しない**。前者はunitをtemplate配備してenable/startする変更系、後者はsnapshot鮮度・収集状態を判定するread-only診断で、共通の検知対象もライフサイクルもない。前者は「スケジュール構成管理」、後者はbackup/snapshot健全性へ分離する |
| 5 | リソース・容量管理（新設案） | `sophos_trim.yml`。容量観測の関連入口として`proxmox_healthcheck.yml`、`monitoring_healthcheck.yml`、`radius_healthcheck.yml` | `sophos_trim`、`proxmox_healthcheck`、`monitoring_healthcheck`、`radius_healthcheck` | **名称修正が必要**。`sophos_trim`は容量計測・閾値判定ではなくSSD trim実行である。現行の容量閾値はhealthcheck側にあり、`proxmox_hw_check`はfilesystemを収集するが容量判定しない。現時点では「ストレージ保守」を単独候補とし、将来の容量Policyはhealth groupとの境界を定めてから新設する |
| 6 | `serial_getty_mask.yml`（Policyなし） | `serial_getty_mask.yml` | なし（playbook内tasks） | **Policyなしで確定**。単一unitをread-only確認後に明示承認でstop/maskする限定作業で、対象・除外・安全手順はplaybook先頭に閉じている。再利用可能な横断判断基準が生じるまではPolicyを新設しない |

### 実装根拠

- 健康監視4入口はそれぞれ専用roleを呼ぶ（`playbooks/proxmox_healthcheck.yml` L3-9、`proxmox_hw_check.yml` L3-9、`monitoring_healthcheck.yml` L3-9、`radius_healthcheck.yml` L3-9）。
- `systemd_timers`はunit file配備、daemon reload、timer enable/startを行う（`roles/systemd_timers/tasks/main.yml` L2-38）。`proxmox_snapshot_check`はsnapshot age閾値と収集成否からStatusを作る（`roles/proxmox_snapshot_check/tasks/main.yml` L25-95）。
- `sophos_trim`はcheck modeで`fstrim --dry-run`、通常時に`fstrim`を実行し、SUCCESS/FAILEDを判定する（`roles/sophos_trim/tasks/main.yml` L2-69）。容量の継続測定はしない。
- `serial_getty_mask.yml`はroleを持たず、対象unitの状態確認とcheck-mode planの後、非check時だけstop/maskする（L23-76）。

### 6案の非対象系統

| 系統 | 現行Policy / 主入口 | 6案へ入れない理由 |
|---|---|---|
| 証明書・CA | `cert_renew_policy.md`、`cert_renew_cloudkey_policy.md`; `cert_renew*.yml`、`ca_trust_deploy.yml`、`cloudkey_cert_deploy.yml` | 鍵・CA・配信検証・削除ゲートという独立した安全境界を持つ |
| backup / restore | `proxmox_backup_restore_verify_policy.md`、`unifi_backup_fetch_policy.md`; 各対応playbook | 一時restore、backup鮮度、世代削除は健康監視や容量管理とは異なる破壊的境界を持つ。`proxmox_snapshot_check.yml`もこの系統の健全性索引候補 |
| observability | `log_observability_policy.md`; `alloy_setup.yml`、`rsyslog_forward_to_monnie.yml`、**`grafana_provisioning.yml`** | ログ収集平面、cutover、送信・受信境界に加え、**2026-07-30のv4.0でdashboard / alert ruleの配備方式(repo正本化・provisioning as code)を含む観測プレーン全体へscopeを拡張した**(LOG-074、`docs/ai/adr/007-grafana-provisioning-as-code.md`) |
| autonomous recovery | `autonomous_recovery_policy.md`; recovery系playbook群 | 検知からrestart/reboot/failoverへ進む権限・ラダーが独立 |
| time sync | `time_sync_check_policy.md`; `time_sync_check.yml`、`time_sync_ntp_reference.yml` | 異種NTP取得方式と基準ノードゲートが独立 |

## `proxmox_operations_policy.md` のPolicy範囲超過候補

判定基準は `docs/ai/context-classification.md` L31-48の「Policyは何をしてよいかという規範」「単一ファイルの実装詳細はコードを正本」とする。安全条件・許可・禁止・停止条件はPolicyへ残し、現状値はContext、手順はOperations Context/Skill、案件順序はIssue/レビュー記録へ移す。

| 現行section・行 | 範囲超過の種類 | 所見と移動先 | Policyへ残す核 |
|---|---|---|---|
| §4「ノードの役割」L145-151 | System Context | ノードの現状役割は `docs/ai/context/system/proxmox.md` 候補 | pve2先行、pve1へ進む条件（L153-159） |
| §5.2「home nodeの考え方」L190-228 | Repository Context / 実装例 | inventoryファイル説明、タグ付与コマンド、Jinja式はRepository Contextまたはコードへ | home nodeをタグで管理する規範、タグの意味 |
| §5.2 L246-261 | Repository Context / roadmap | roleの現行判定実装、report内容、未実装表示例はrole-map・Issueへ | HA/non-HAの許可された退避・復帰原則 |
| §6.2-§6.7 L360-827 | Repository Context | 各playbookの20段前後の処理、出力、変数例はplaybook-map・role-map・コードへ。標準Policyには入口、安全度、実行条件、停止条件だけを残す | safe/semi-safe/controlled/unsafe分類、許可条件、停止条件 |
| §6.5「post-healthcheckリトライ設定」L610-688 | 実装詳細 / Operations Context | defaults名、計算式、時系列例、変更コマンドはrole docsまたはOperations Contextへ | reboot後だけ再試行を許す原則と最終停止条件 |
| §11.2「スケジュール」L1193-1234 | Operations Context | 仮置き時刻と詳細タイムラインはrunbook/scheduler Contextへ | 実行モードごとの許可範囲 |
| §11.3-§11.4 L1236-1284 | Operations Context / 重複 | Mode別の逐次手順は§17とも重複するためrunbookへ集約 | control node配置条件、次nodeへ進む停止条件 |
| §14.2-§14.3 L1424-1482 | Skill / Repository Context | changelog取得コマンド、JSON例、Codexへの整形仕様は分類Skillまたはdry-run role docsへ | 参照情報の優先順位と最終判断をAnsible側に置く規範 |
| §16.1-§16.3 L1619-1669 | Skill / Repository Context | Codex CLIの入力・出力schema、説明生成方法は専用Skillまたはdry-run実装契約へ | AI出力を最終適用判断にしない規範 |
| §16.5 L1686-1704 | Role / Skill / Repository Context | Ansible・shell・Codexの詳細責務表はSkill/Operations Contextへ | apply可否は決定論的Policy gateが支配する原則 |
| §16.6-§16.7 L1706-1732 | System Context / Skill | CLI配置先、導入前提、セットアップ時期はSystem ContextとSkillへ | Proxmox host上で分類CLIを直接動かさない禁止だけ残す |
| §16.8.0-§16.8.2 L1744-1783 | System Context / Operations Context | 実行端末の現状、到着前後という時点依存の移行判断はContext/Decisionへ | control nodeが対象node上にいる場合のapply禁止（L1734-1743、L1785-1789） |
| §16.9「初期テスト方針」L1791-1803 | Test plan | 品質確認項目と初期実行時期はreview/test_planへ | なし |
| §17「実適用時の標準手順」L1805-1884 | Operations Context / runbook | Mode別の操作手順をrunbookへ移し、§11との重複を解消 | 開始・続行・停止・人間確認条件 |
| §18「復旧方針」L1886-1930 | Policy核 + Operations/System Context | §18.2-§18.4 L1895-1930のノード別復旧手順・再構築情報一覧はProxmox Operations/System Context候補へ | §18.1 L1888-1893の「OS rollbackを原則行わず再インストールする」をPolicy核として残す |
| §19「Sophos移行前の必須条件」L1933-1947 | 別Issue / migration Policy | Patch実装の成熟度から移行時期を決める内容であり、Sophos移行Decision/Issueへ | Sophos稼働時にpatchを許可する安全前提への参照 |
| §20「Sophos移行後の追加ルール」L1950-1960 | System Context + 条件付きPolicy | NIC/VLAN・稼働場所の事実はSystem Context、通信確認手順はrunbookへ | Sophos稼働nodeのpatch制約と停止条件 |
| §21「今後の実装順序」L1964-1986 | Issue / project plan | 実装済み項目を含む時点依存の順序なのでreview計画へ | なし |
| §22「参考リンク」L1989-2007 | 標準8節外の出典付録 | 一次情報の出典としてPolicyに同居可能。参照indexまたは分類Skillへ分離する選択肢はあるが、必須移動とはしない | 現状維持も可。移す場合も判断根拠から到達できる参照を残す |

## 個別書換の優先順位案

1. `proxmox_operations_policy.md`: 範囲超過と重複が最大で、変更履歴が未整備、Playbook見出しも標準名未統一。Policy核を残してContext/Skill/runbook/Issueへ分離する。
2. `autonomous_recovery_policy.md`: 実装・アカウント・鍵・wrapper詳細が大きく、標準Playbook見出しと変更履歴がない。権限・禁止・ラダーだけをPolicy核にする。
3. `ubuntu_vm_patch_policy.md`: apt/非apt/reboot/healthcheckが混在し、標準Playbook・制約・変更履歴を整える必要がある。目的別groupとの境界も同時に明示する。
4. `proxmox_backup_restore_verify_policy.md`: lifecycleと安全装置は明確だが変更履歴がなく、実装詳細をRepository Contextへ寄せる余地がある。
5. `core.md`: 個別Policyテンプレートを機械適用せず、変更履歴だけを共通原則の保守方式として整える。
6. `log_observability_policy.md`: 現行通知方針と将来アラート構想を分離し、現状構成・検証結果をContextへ寄せる。
7. `cert_renew_policy.md`、`cert_renew_cloudkey_policy.md`、`time_sync_check_policy.md`、`unifi_backup_fetch_policy.md`: 既存8要素の対応度が高いため、見出し名の統一と概念判断軸の昇格を後段で行う。

この順序は書換実施の承認ではない。個別差分は別requirement、review、testで扱う。
