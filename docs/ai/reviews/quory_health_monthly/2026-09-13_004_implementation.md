# quory月次ヘルスレポート 初期実装

要求001、計画002（査読003 Approve）、ADR-014、Policy `docs/ai/policies/quory_health_monthly_policy.md`に基づく初期実装。実ホスト・quory・本番Notion/Slackには一切到達していない。

## 変更ファイル

- 新規 `playbooks/quory_health_monthly.yml`（`# tester-gate: check-mode-native`）
- 新規 `roles/quory_health_monthly/`
  - `defaults/main.yml`
  - `files/quory_collect.py`（read-only collector: df root/EFI、/proc/meminfo、lsblkでNVMe namespace検出、nvme id-ctrl/smart-log）
  - `module_utils/quory_health_files.py`（`storage_files.py`と同じlocked/atomic契約、独立ファイル）
  - `module_utils/quory_health.py`（filesystem/memory/device判定、markdown/short_summary）
  - `library/quory_health_archive.py`（保存・baseline凍結・13か月保持、`storage_archive.py`と同じ契約）
  - `library/quory_health_notion.py`（Notion投稿、`storage_notion.py`と同じ契約、parent未設定時は`parent_unconfirmed`で必ず失敗）
  - `tasks/collect.yml`, `tasks/report.yml`
- 更新 `roles/semaphore_templates/defaults/main.yml`（`quory_health_monthly`テンプレートのみ追加。scheduleは追加していない）
- 更新 `playbooks/README.md`（「ホスト保守・定期運用」に追加）
- 更新 `.gitignore`（`reports/quory-health-monthly/`を追加）
- 新規 `docs/ai/context/operations/quory-health-monthly.md`
- 新規 `tests/test_quory_health_monthly.py`（20 tests）

## 設計判断の要点

- 収集対象は`control_nodes`グループ＝`quory`単体であることをplaybook起動時に`groups['control_nodes'] == ['quory']`でassertし、`add_host`で明示的に`quory`だけをtargetsへ加える。実行コンテキストが実際にquoryを見ているかの最終確認は配備時のreadback（計画002 検証・配備順序3）に委ねる。
- **健康判定とジョブ成否の分離をQHM-031どおり実装したが、`proxmox_storage_monthly`とは分岐点が違う。** `proxmox_storage_monthly`はNVMeコマンド失敗を例外にして`collection: error`へ畳んでいたが、本requirementのP0は「容量が正常でも『ディスク健全』と結論しない」ことを明示するため、filesystem/memoryが収集できていればNVMe取得不能だけでcollectionを`error`にせず、`health`軸を`UNKNOWN`にする設計にした。そのうえで`tasks/report.yml`の最終assertへ`health != 'UNKNOWN'`を明示的に追加し、AC2（取得不能時にジョブrc非0）とAC3（WARNING/CRITICALだけなら処理完了時rc0）を両立させている。この一致条件は`docs/ai/context/operations/quory-health-monthly.md`に理由を記録した。
- Notion親ページは`quory_health_monthly_notion_parent`既定空文字列。`quory_health_notion`モジュールは`parent`が空なら（check/suppress以外の通常実行でも）token読取前に`parent_unconfirmed`で失敗する。配備前readbackで値を入れるまで本番投稿は成立しない。tokenファイルは既存`homelab-report` Integration・Proxmoxストレージ月次点検と同じ`/etc/homelab/notion-storage.token`を既定で再利用する（計画002・ADR-014）。
- Semaphore templateのみ追加し、schedule（`roles/semaphore_templates/defaults/main.yml`の`schedules`セクション）は追加していない — NVMe取得ツール・Notion親ページ・schedule時刻が計画上「未確定」のため。

## 自己検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 20/20 OK（filesystem/memory閾値、NVMe取得不能=UNKNOWN、比較状態遷移baseline/compared/reset_suspected/replacement_or_added、history_error、archive round-trip・破損履歴検知・check-modeで無書込、Notion suppress/check、publish create→再利用、旧reportでの巻戻し拒否、parent未確定拒否）
- `python3 -m unittest discover -s tests -p "test_*.py"`: 38/38 OK（既存回帰含め regression なし）
- `ansible-playbook --syntax-check playbooks/quory_health_monthly.yml`: rc0
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `bash scripts/check-tester-gate.sh`: OK（62 playbooks）
- `git diff --check`: rc0
- ローカルスクリプト単体実行（Ansibleでホストを指定しない、ansy自身に対するdf/meminfo/lsblkのread-onlyコマンド）: `roles/quory_health_monthly/files/quory_collect.py`をこのマシンで直接実行し、実データで `build_report` → `short_summary` まで通した。この過程で **`df -P` と `--output` が併用不可という実バグを検出・修正した**（GNU df: "options -P and --output are mutually exclusive"）。修正後は正常な観測JSONが得られ、閾値判定（root使用率84%→WARNING）も正しく動くことを確認した。
- `ansible-playbook -i inventories/homelab/hosts.yml playbooks/quory_health_monthly.yml -e quory_health_monthly_operation=bogus -e skip_notifications=true`: play1のassertでrc非0、quoryへ到達せず（`add_host`未実行）。
- `... -e quory_health_monthly_operation=replay -e quory_health_monthly_report_id=not-a-valid-id ...`: play1のreport_id正規表現assertでrc非0。
- `... -e quory_health_monthly_operation=replay -e quory_health_monthly_report_id=<正しい形式・未保存のID> -e skip_notifications=true -e quory_health_monthly_report_dir=/tmp/...`: quoryへ到達せず（replayはtargetsを開かない）、archiveモジュールがread失敗でfail、pipeline_errorによりrc非0で終了。Slack通知はAIセッション検出で抑止（trigger3）。処理後に`quory_health_monthly_report_dir`が作成されていないことを確認済み（replayはlocked/mkdirを経由しない設計どおり）。

**`operation=collect`のplaybook実行はしていない。** これは実際にinventory上の`quory`ホストへAnsible接続を試みる経路であり、Implementer役の「実ホストへansibleを実行しない（状態を変えない確認も含む）」に該当するため。`tasks/collect.yml`のロジック自体は静的レビューと、collectorスクリプト単体のローカル実行（上記）で妥当性を確認した。

## 差し戻し対応（2026-09-13、独立Reviewer 005_diff_review.md Major #1〜#6）

005を現物確認し、Major 6件すべてを対象に修正した。

- **Major #1（dfの使用率再計算）**: `quory_health.py`の`filesystem()`を、`used_bytes/size_bytes`の再計算から`use_percent_raw`（dfの`pcent`列）の厳密parse（`^\d{1,3}%$`）へ変更。判定・表示とも`use_percent_raw`由来の値のみを使い、不正/欠損なら`collection: error`（UNKNOWN）にした。反例fixture: `test_uses_dfs_own_percent_even_when_it_disagrees_with_used_over_size`（pcentとused/sizeを意図的に矛盾させ、pcent側が採用されることを確認）、`test_malformed_df_percent_is_unknown_not_a_silent_pass`、`test_missing_df_percent_field_is_unknown`。
- **Major #2（前回比較がNVMeカウンタだけ）**: root/EFI使用率・使用量、メモリavailable、swap使用量について「直前の成功観測」との差分を`quory_health.py`の`filesystem()`/`memory()`に追加した。比較元は`archive.py`が`history`から算出する`previous_reports`（host別・最新の`collection==ok`な全文report）を新規に`build_report()`へ渡す形にした（deviceの`baseline`とは別の仕組み。deviceは物理デバイスの継続性を追うためfreeze/fill方式が必要だが、fs/memは値が1つしかないため直前reportそのものを参照すれば足りる）。閾値は新設の`quory_health_monthly_fs_growth_warning_points`(既定10pt)・`quory_health_monthly_mem_available_drop_warning_points`(既定10pt)・`quory_health_monthly_swap_growth_warning_bytes`(既定100MiB)で、絶対閾値未満でも悪化をWARNING化する。本文・短報とも差分と比較元日時を表示する。反例fixture: `test_filesystem_and_memory_compare_against_previous_successful_report`、`test_second_run_compares_filesystem_and_memory_against_previous_report`（archive経由）、`test_small_filesystem_and_memory_changes_do_not_trigger_growth_warnings`（過剰検知しないことも確認）。
- **Major #3（Slack短報にID・対象・値がない/重大事項が切り詰められる）**: `short_summary()`を再設計。先頭に`[health] 対象: <host> / Report ID: <id>`を必ず出し、各issueへ具体値を`detail`として埋め込む（issuesを`[level, code, detail]`の3要素へ変更）。CRITICAL/UNKNOWNは無条件に全件表示し、件数制限は残るWARNINGだけに適用（「ほか(WARNING) N件」）。反例fixture: `test_short_summary_never_truncates_critical_or_unknown_items`（CRITICAL 2件+UNKNOWN 1件超+WARNING多数でも全urgent項目が文字列に残ることを確認）、`test_short_summary_caps_only_warning_items`。
- **Major #4（lsblk不能とNVMeなしの混同）**: `quory_health.py`で`raw['lsblk']`のrc/JSON妥当性を明示的に検査し、不能なら`nvme_transport_observed=None`+UNKNOWN issueとし、health側もUNKNOWNへ波及させた。lsblkが健全で単に対象デバイスが無い場合は従来どおり`nvme_transport_observed=False`・OKのまま区別する。反例fixture: `test_lsblk_failure_is_unknown_not_confused_with_no_nvme_present`、`test_lsblk_invalid_json_is_also_unknown`、`test_no_nvme_transport_observed_with_working_lsblk_is_ok_not_unknown`（対照）。
- **Major #5（EFI失敗が他の成功観測を握りつぶす）**: `build_report()`のホスト単位処理を「例外で丸ごと中断」から「root/EFI/memory/NVMeそれぞれを独立にtry/exceptし、失敗しても他の処理を継続」する構造へ書き換えた。`entry['collection']`は依然としていずれかが失敗すれば`error`（rc非0は変わらない、AC4の「全体OKを出さない」を維持）だが、成功した部分（例: root fs、memory、devices）は`filesystems`/`memory`/`devices`にそのまま残る。反例fixture: `test_efi_failure_still_preserves_root_and_memory_and_devices`、`test_memory_failure_does_not_erase_filesystem_results`。
- **Major #6（EFI未mount時にrootを誤ってEFIとして計上）**: `quory_collect.py`の`df_entry()`に`findmnt --target <path>`による実マウント先の確認を追加し、要求パスと実際のTARGETが一致しない場合は`error: not_mounted`（`actual_mount`に実際の値を記録）としてdfを呼ばずに打ち切るようにした。反例fixture: `test_df_entry_reports_not_mounted_when_findmnt_disagrees`、`test_df_entry_reports_not_mounted_when_findmnt_itself_fails`、対照`test_df_entry_proceeds_when_findmnt_confirms_the_mount`（collector単体、`quory_health.filesystem()`側の反例は`test_efi_not_mounted_is_unknown_never_reported_as_root_values`）。

### 追加・変更ファイル（差し戻し対応分、元の変更許可範囲内）

- `roles/quory_health_monthly/files/quory_collect.py`（findmnt検証を追加）
- `roles/quory_health_monthly/module_utils/quory_health.py`（issues形式変更、前回比較拡張、lsblk健全性検査、partial-failure対応、short_summary/markdown再設計）
- `roles/quory_health_monthly/library/quory_health_archive.py`（`previous_reports`算出・`build_report`への追加引数）
- `roles/quory_health_monthly/defaults/main.yml`（成長閾値3件を追加）
- `roles/quory_health_monthly/tasks/report.yml`（thresholds dictへ成長閾値3件を追加）
- `tests/test_quory_health_monthly.py`（Major 1〜6それぞれの反例fixtureを追加、35 tests）

### 差し戻し後の再検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 35/35 OK
- `python3 -m unittest discover -s tests -p "test_*.py"`: 53/53 OK（既存回帰含め regression なし）
- `ansible-playbook --syntax-check playbooks/quory_health_monthly.yml`: rc0
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `bash scripts/check-tester-gate.sh`: OK（62 playbooks）
- `git diff --check`: rc0
- collectorをこのマシン上でローカル単体実行して`findmnt`による実mount確認後も正常JSONが得られることを再確認し、`build_report`→`short_summary`まで通した（短報に`Report ID`・対象host・具体値`84%`が含まれることを確認、Major #3の実データ確認）。
- `operation=bogus`・`operation=replay`（不正/未保存report_id）をquory実inventoryに対して再実行し、いずれもquory未到達のままrc非0で失敗することを再確認（`/tmp`配下の一時report_dirにも書込が発生しないことを確認）。

### 005レビューSuggestion（`docs/ai/status.md`更新）について

Suggestion 1（status.mdの工程現在地更新）はCoordinatorの担当範囲であり、Implementerの書込許可範囲外のため対応していない。

## 再差し戻し対応（2026-09-13、006_rereview.md 残存Major 3件）

006を現物確認し、残存Major 3件すべてを対象に修正した。005は履歴として保持し、006を編集していない。

- **006 Major#1（005 #2残存: 判定不能reportが比較元・baselineへ混入）**: 「前回の成功観測」判定を、host単位の`collection=='ok'`だけでなく`health!='UNKNOWN'`も要求する形へ変更した。NVMe tool不能（`device_health`のtool_unavailable経路）は従来`collection`を`error`にしないためこの抜け穴が生じていた。`quory_health.py`の`build_report()`へホスト単位の`entry['health']`フィールドを新設し（全体`health`と同じ優先度ロジックをホスト単位で算出）、`quory_health_archive.py`に共通判定`usable_as_comparison_basis(entry)`を追加して、`previous_reports`算出と`freeze_devices()`の両方（当月baseline新規作成時の過去月からの引継ぎ、および今回report自身のfreeze）に適用した。反例fixture: `test_unknown_health_report_is_excluded_from_future_fs_mem_comparison`、`test_unknown_health_report_does_not_seed_the_device_baseline`（いずれもarchive.archive()を2回連続実行し、1回目がNVMe tool不能でhealth=UNKNOWN・collection=okになることを確認した上で、2回目がその失敗reportを比較元に使わないことを検証）。
- **006 Major#2（005 #3残存: 絶対閾値異常のissueに比較元・差分がない）**: `filesystem()`/`memory()`を「比較状態を先に計算してから閾値issueを生成する」順序へ並べ替え、絶対閾値超過のCRITICAL/WARNING issueの`detail`にも「前回X%→今回Y%、+Zpt、比較元 日時」を必ず含めるようにした（従来は成長警告issueだけが差分を持ち、絶対閾値issueは現在値のみだった）。反例fixture: `test_absolute_threshold_issue_includes_comparison_source_and_delta`（前回90%→今回95%、成長警告閾値を意図的に高く設定して絶対閾値issue単体のdetailを検査）、`test_memory_absolute_threshold_issue_includes_comparison_source_and_delta`。
- **006 Major#3（005 #4残存: lsblk rc0+空payloadがNVMeなしのOKに畳まれる）**: 二層で独立に緩い判定をしていた構造そのものを解消した。`quory_collect.py`の`nvme_namespaces()`を「`blockdevices`キー欠損・行の型不正なら例外を投げる、空リストは正当な0件として許容する」形に書き換え、`collect()`が例外時に`lsblk_valid=False`・`nvme_transport_observed=None`を明示的に記録するようにした。`quory_health.py`側は`raw['lsblk']`のrc/JSON形状を自前で再判定するのをやめ、`raw['lsblk_valid']`という単一の正本（collectorだけが構造を検証する）を信頼する形に変更した（値の二重管理を解消）。反例fixture: collector単体`test_nvme_namespaces_raises_when_blockdevices_key_is_absent`・`test_nvme_namespaces_raises_on_malformed_row`・`test_collect_marks_lsblk_invalid_and_transport_unknown_on_empty_payload`、module_utils側`test_lsblk_rc0_with_empty_payload_is_unknown_not_zero_devices`。

### 追加・変更ファイル（再差し戻し対応分、元の変更許可範囲内）

- `roles/quory_health_monthly/files/quory_collect.py`（`nvme_namespaces`を例外ベースへ、`collect()`が`lsblk_valid`を出力）
- `roles/quory_health_monthly/module_utils/quory_health.py`（`filesystem`/`memory`の閾値issueに比較detail追加、ホスト単位`health`フィールド新設、`lsblk_valid`を信頼する形へ変更）
- `roles/quory_health_monthly/library/quory_health_archive.py`（`usable_as_comparison_basis()`を追加し`previous_reports`算出・`freeze_devices()`双方に適用）
- `tests/test_quory_health_monthly.py`（006 Major 1〜3の反例fixtureを追加、44 tests）

### 再差し戻し後の再検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 44/44 OK（005由来の35件は非回帰、006向け9件を追加）
- `python3 -m unittest discover -s tests -p "test_*.py"`: 62/62 OK（既存回帰含め regression なし）
- `ansible-playbook --syntax-check playbooks/quory_health_monthly.yml`: rc0
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `bash scripts/check-tester-gate.sh`: OK（62 playbooks）
- `git diff --check`: rc0
- collectorをこのマシン上でローカル単体実行して`lsblk_valid`・`nvme_transport_observed`・ホスト単位`health`フィールドが正しく出ることを再確認し、`build_report`→`short_summary`まで通した。
- `operation=bogus`・`operation=replay`（未保存report_id）をquory実inventoryに対して再実行し、いずれもquory未到達のままrc非0で失敗・一時report_dirへの書込なしを再確認。

## 最終再査読対応（2026-09-13、007_final_review.md 残存Major 3件）

007を現物確認し、残存Major 3件すべてを対象に修正した。005〜007は履歴として保持し、いずれも編集していない。

- **007 Major#1（006 #1残存: 履歴破損reportがhost health=OKだけで比較元/baseline候補になる）**: `usable_as_comparison_basis()`をhost単位のentryだけでなく`report`全体を見る形へ拡張した（シグネチャを`usable_as_comparison_basis(report, host)`へ変更）。`report.get('history_error')`が真、または`report.get('health')=='UNKNOWN'`、または`report.get('collection')!='ok'`のいずれかであれば、そのhostの`collection`/`health`が個別に見て健全であっても比較元・baseline候補から除外する。史実として、履歴破損時はhost自身のfilesystem/memory/deviceが正常に収集できていれば`entry['health']=='OK'`のままになり（history_errorは各項目の`comparison`状態を`history_corrupt`にするだけでissueを積まない）、host単位の判定だけでは検出できなかった。反例fixture: `test_history_corrupt_report_is_excluded_even_though_host_itself_looks_healthy`（1回目を破損履歴混在で実行しhost health=OK・report全体health=UNKNOWNを確認、破損ファイル除去後の2回目がその1回目reportを比較元に使わないことを検証）。
- **007 Major#2（006 #2残存: 異常issueに比較元report IDが出ない）**: `filesystem()`/`memory()`の`comparison_note`（絶対閾値issueと成長警告issueの両方が共有するdetail文字列）へ、日時に加えて比較元の`report_id`自体を埋め込むよう変更した。あわせてMarkdown本文の「前回比」行（fs/memory双方）にも比較元report IDを追加した。日時は分単位表示のため同分内の複数回実行では一意に特定できない、という007の指摘に対応。反例fixture: `test_short_summary_and_markdown_include_comparison_source_report_id`（比較元と当該reportに異なる明示的report_idを与え、両方が短報・Markdown本文に出ることを確認）。
- **007 Major#3（006 #3残存: `blockdevices: [{}]`が正常な空一覧になる）**: `quory_collect.py`の`nvme_namespaces()`が、lsblkへ`--output NAME,TYPE`を明示指定している前提のもと、各行が`name`/`type`を両方とも文字列として持つことを検証するよう変更した。`{}`のような「存在するが解釈不能な行」は例外を投げ、`collect()`が`lsblk_valid=False`として記録する。真に空の`blockdevices: []`（0件のリスト自体）は引き続き正当な「NVMeなし」として許容する。反例fixture: `test_nvme_namespaces_raises_on_row_missing_name_and_type`、`test_collect_marks_lsblk_invalid_when_row_missing_name_and_type`。

### 追加・変更ファイル（最終再査読対応分、元の変更許可範囲内）

- `roles/quory_health_monthly/files/quory_collect.py`（`nvme_namespaces`の行検証を`name`/`type`の型チェックへ強化）
- `roles/quory_health_monthly/module_utils/quory_health.py`（`comparison_note`へ比較元report_idを追加、Markdown前回比行へ比較元report_idを追加）
- `roles/quory_health_monthly/library/quory_health_archive.py`（`usable_as_comparison_basis`をreport全体を見る形へ拡張）
- `tests/test_quory_health_monthly.py`（007 Major 1〜3の反例fixtureを追加、48 tests）

### 最終再査読後の再検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 48/48 OK（005〜006由来の44件は非回帰、007向け4件を追加）
- `python3 -m unittest discover -s tests -p "test_*.py"`: 66/66 OK（既存回帰含め regression なし）
- `ansible-playbook --syntax-check playbooks/quory_health_monthly.yml`: rc0
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `bash scripts/check-tester-gate.sh`: OK（62 playbooks）
- `git diff --check`: rc0
- collectorをこのマシン上でローカル単体実行し`lsblk_valid`が正しく出ることを再確認、`build_report`→`short_summary`まで通した。
- `operation=bogus`・`operation=replay`（未保存report_id）をquory実inventoryに対して再実行し、いずれもquory未到達のままrc非0で失敗・一時report_dirへの書込なしを再確認。

## Coordinator追加指摘対応（2026-09-13、nvme_namespacesがrcを検査していない件）

Coordinatorが現物確認で、`nvme_namespaces(lsblk)`がJSON構造のみを見て`lsblk`自身の`rc`を検査していない点を指摘した。`decoded()`は現状rc=0のときしか`json`キーを付けないため実運用では連鎖的に守られていたが、`nvme_namespaces()`自身の契約としてrcを見ていないのは、他関数の実装詳細に暗黙に依存した脆い設計だった。

- `roles/quory_health_monthly/files/quory_collect.py`の`nvme_namespaces()`冒頭へ`if lsblk.get("rc") != 0: raise ValueError(...)`を追加し、rc非0はJSON構造が妥当（空`blockdevices: []`を含む）でも即座に取得不能として扱うようにした。
- 反例fixture4件追加: `test_nvme_namespaces_raises_when_rc_nonzero_even_with_well_formed_empty_json`、`test_nvme_namespaces_raises_when_rc_nonzero_even_with_well_formed_devices_json`（rc非0+構造上妥当なJSON、空/非空の両方）、`test_collect_marks_lsblk_invalid_when_lsblk_command_itself_fails`（collect()統合、lsblkコマンド自体の失敗）、`test_build_report_treats_lsblk_rc_failure_as_unknown_not_zero_devices`（build_report消費側での契約確認）。

### 再検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 52/52 OK
- `python3 -m unittest discover -s tests -p "test_*.py"`: 70/70 OK（regression なし）
- `ansible-playbook --syntax-check`・`check-doc-consistency.py`・`check-tester-gate.sh`・`git diff --check`: 全てOK
- collectorのローカル単体実行、`operation=bogus`のquory実inventoryに対する再実行（quory未到達）を再確認。

## 008再査読対応（2026-09-13、swap悪化短報のMajor 1件）

008を現物確認した。swap使用量が前回比で悪化した場合のissue detailが、swap自身の前回/現在/差分ではなくメモリavailable比率の`comparison_note`を流用していたため、短報に現在swap使用量が出ず、無関係なavailable%を誤ってswap比較として読める状態だった。

- `roles/quory_health_monthly/module_utils/quory_health.py`の`memory()`へswap専用の`swap_note`（前回swap使用量→今回swap使用量、差分bytes、比較元report_id・日時）を新設し、`swap usage grew notably since last comparison`issueのdetailをこの`swap_note`（と現在swap使用量）だけで構成するよう変更した。従来使い回していたmemory-available比較用`comparison_note`（%表記）とは完全に分離した。
- 反例fixture: `test_swap_growth_issue_shows_swaps_own_prior_current_delta_and_source`（008の実測どおりswap 50,000,000→250,000,000 bytesを再現し、detailと短報の両方に前回/現在swap値・差分・比較元IDが含まれ、`%`表記が混入しないことを検証）。

### 再検証

- `python3 -m unittest tests.test_quory_health_monthly -v`: 53/53 OK
- `python3 -m unittest discover -s tests -p "test_*.py"`: 71/71 OK（regression なし）
- `ansible-playbook --syntax-check`・`check-doc-consistency.py`・`check-tester-gate.sh`・`git diff --check`: 全てOK
- `operation=bogus`をquory実inventoryに対して再実行し、quory未到達を再確認。

## 未達AC・未解決事項（Coordinatorへ）

- **AC1・AC6（quory実ホストでの収集・Notion・Slack照合、schedule readback）は未検証。** Tester/配備工程が必要（計画002 検証・配備順序3・4）。
- **NVMe取得ツールの実機有無は未確認。** quory実行コンテキストに`nvme`コマンドが無い場合、collectorは`rc=-1`を返し、`build_report`は`reason=tool_unavailable`で`health=UNKNOWN`にする設計で対応済みだが、実機での実測はできていない。
- Notion親ページID・Integration権限は未確定のまま（`quory_health_monthly_notion_parent`既定空文字列）。配備前readbackが必要。
- `groups['control_nodes'] == ['quory']`によるinventory健全性チェックは静的なものであり、「Semaphore実行コンテキストが実際にquoryを見ている」ことの実行時証明ではない。計画002が求める配備時readbackで別途確認が必要。
- NVMe取得ツール導入用のquory限定setup playbook/roleは今回スコープ外（未着手、要求どおり）。
- `roles/semaphore_templates/defaults/main.yml`の`schedules`セクションへの追加は行っていない（要求どおり、readback待ち）。
