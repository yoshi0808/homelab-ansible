# 第3家族: default(x, true) の走査

## 走査進捗

指定grepの90ヒット。走査済み90/90（grep順、playbooks/incident_investigate_notify.yml:96〜roles/unifi_backup_fetch/tasks/main.yml:59）、未走査0。第2引数なしdefaultは対象外。task/関数/play内、呼出元1段までの契約で調べる。

## 判定を誤らせる（壊れていても問題なしに見える）

確定0件。

## 例外で落ちる（気づける）

確定0件。

## 未確定

- `roles/semaphore_templates/tasks/resolve.yml:29,37,56,64,83,91`: 正当なID=0なら空へ変わり未解決failとなるが、現在のAPIが有効なID=0を発行する経路はtask範囲で確認できず、findingには含めない。

## 除外・確認結果

- `playbooks/incident_investigate_notify.yml:96,98,103`、`playbooks/knowledge_review.yml:61`: 理由・エラー・前回通知日の本文表示なので対象外。
- `playbooks/proxmox_backup_restore_verify.yml:148`: regexで抽出した候補ホスト名のfirstが入力。空文字は復元先未解決を意味し、同じ空文字への置換で意味は変わらない。156行で未解決をfail。
- `roles/alloy/tasks/main.yml:791,906,914,921,928,937`: backup_fileはパスまたは未作成。正当な空パスが存在するbackupを意味する経路なし。785〜786行にbackupなしならPromtail復元の意図を明記、928行は表示。
- `roles/codex_update_check/tasks/main.yml:62,63,174,175`: 入力はversion文字列。正当なメジャー0も文字列「0」/「0.x.y」でtruthy、消えない。空文字は収集不成立で、176〜180行はrcと数字形式を要求。
- `roles/common_slack/tasks/notify.yml:55`: 環境変数lookupは文字列、空文字の置換先も空文字。正当な「0」「false」はtruthyのまま。53行は環境変数によるsession検出意図を明記。
- `roles/deployment_drift_check/tasks/evaluate.yml:38,45,52,74,82,90,108,119,127,198,205,212,219`、`tasks/report.yml:161`: findingに付記する手動実行先と直し方の表示。実行分岐でなく対象外。
- `roles/knowledge_review/tasks/incident_metrics.yml:61,77,250,266`: 診断文字列の記録、空文字の置換先も空文字または説明文。`:301` の正当値0（bundleなし）はdefault(0,true)でも0のまま、NO_DATA判定は変わらない。
- `roles/prometheus_update_check/tasks/main.yml:410,494`、`tasks/notify.yml:15,16,19,22,47,58,60,63,66,70,71,72,77,83`: 失敗理由・バージョン・診断本文の表示/記録であり対象外。

- `roles/proxmox_backup_restore_verify/tasks/main.yml:358`: regex_searchの一致結果は非空文字列、未一致はNone。正当なfalse/0/空listを受け取って別の意味にする経路はない（未一致時のownership方針そのものは本家族のAC5を満たさず、今回のfinding対象外）。
- `roles/proxmox_patch_dryrun/tasks/main.yml:142,379,421,465`: 空のreachability本文を正規化する修正意図が130〜139行に明記。正当な空文字は空のままで判定は変わらない。後3行は本文表示・追記。
- `roles/semaphore_templates/tasks/apply.yml:146`、`tasks/read.yml:71`: descriptionの正当な空文字は置換先と同一。APIのfalse/0が正当なdescriptionという根拠は当該taskにない。
- `roles/semaphore_templates/tasks/schedules_timezone_check.yml:26,27`: タイムゾーン/バージョン文字列の正当な空値が有効設定を意味する経路なし。timezoneは後続の期待値比較で拒否、versionは記録用。
- `roles/semaphore_update_check/tasks/main.yml:122`: URLの正当なfalsy値なし。空は空のままで、140〜141行のstr/trim非空検査に通らない。`:203,204`、`tasks/notify.yml:13,14,17,29,33` は本文表示・診断記録として除外。
- `roles/time_sync_check/tasks/check_chrony.yml:33`: 正当なゼロoffsetはregexの文字列「0」/「0.0」でtruthy。未一致時の0は同taskの_offset_found必須条件で正常判定から外れる（20,25行）。
- `roles/time_sync_check/tasks/main.yml:168,170,172,174,175,176,224,226,228,230`: regexの正当なrc=0/時刻0/offset0は文字列でtruthy。before/afterの正当な数値0はdefault(0,true)でも0。検出失敗はcollected/syncedが拒否（158〜161,216〜219行）。
- `roles/ubuntu_vm_full_upgrade/tasks/evaluate_nonapt_product.yml:11,15`: バージョンの正当な数値0/false/空listを意味する経路なし。「0.0.0」はtruthy。後続33〜50行でsemver不成立をfailedへ分ける。`tasks/main.yml:202,247` は通知本文正規化であり対象外。
- `roles/unifi_backup_fetch/tasks/main.yml:59`: 正当な空headerは認証token欠落を意味する。別header/JWTを使う意図が67〜69,88行に明記。空文字が有効tokenという経路はなく、最終token/CSRF非空assertもある（99〜100行）。

## 最終報告

90ヒットを全件走査。誤判定0件、例外0件、未確定1項目。正当なfalsy入力の到達と判定変更を両方示せる追加所見はなかった。未確定は正常の証明ではない。実装・実ホスト操作・stage/commitは行わず、変更は本成果物のみ。走査プロセスは残していない。
