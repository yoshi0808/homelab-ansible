# Group A実装 自己検証記録(2026-08-25)

対象: `2026-08-25_004_fix_scope.md`「Group A: policies + core.md」表のP1-1〜P3-2(14項目)。findingsの一次根拠は`2026-08-25_001_findings_policies.md`。

## 変更ファイル

- `docs/ai/policies/cert_renew_policy.md`
- `docs/ai/policies/time_sync_check_policy.md`
- `docs/ai/policies/unifi_backup_fetch_policy.md`
- `docs/ai/policies/execution_boundary_policy.md`
- `docs/ai/policies/proxmox_operations_policy.md`
- `docs/ai/policies/cert_renew_cloudkey_policy.md`
- `docs/ai/policies/incident_capture_policy.md`
- `docs/ai/policies/autonomous_recovery_policy.md`
- `docs/ai/core.md`
- `docs/ai/roles/coordinator.md`(80行目の1箇所のみ)

いずれもPolicy本文を改訂したファイル(core.md/coordinator.mdを除く)には、既存書式に合わせて§8等の変更履歴表へ1行追加した。ルールID(CERT-xxx等)の新設・退番は行っていない。

## 項目ごとの充足

| finding | 対応 | 現物確認 |
|---|---|---|
| P1-1 | cert_renew_policy.md CERT-013末尾の「両経路とも force_renew=true の月次強制再発行とする」を削除し、「定常運用での起動頻度・強制再発行の要否はCERT-024を正本とする。」へ置換 | CERT-024マーカーは同ファイル176行に実在 |
| P1-2 | time_sync_check_policy.md TIME-017の分類実値複製を削除し、「各playbookのtester gate分類は各ファイル先頭のマーカーを正本とする(TS-007)」へ | TS-007マーカーは`ansible_test_safety_policy.md:34`に実在 |
| P1-3 | unifi_backup_fetch_policy.md UNIFI-019を「`--check`は停止assertにより変更を一切行わず停止する(TS-030)」へ改訂 | TS-030マーカーは`ansible_test_safety_policy.md:79`に実在 |
| P1-5 | execution_boundary_policy.md EXEC-010「それ以外」行から`monnie`を除去 | 「到達手段が無い」行にのみ`monnie`が残る状態を確認 |
| P1-6 | proxmox_operations_policy.md SB-011冒頭・SB-038本文へ「両nodeが利用可能なときの順序制約」の条件句を追加(§1・2026-08-01変更履歴の既存表現を鏡像) | 参照先SB-028・SB-032・§2.2は実在(131行・142行・37行) |
| P1-7 | cert_renew_cloudkey_policy.md CCK-003の「実行元(開発)=ansy」「実行権限の実体はSSH鍵ann」を削除し、「開発側(ansy)からの実行経路は無い。実行はquoryのSemaphore Task Templateのみ」+EXEC-005参照へ。§1比較表の同項目、§5自動実行例の「開発(ansy)/本番(quory)共通」コメントも同じ食い違いとして合わせて修正 | EXEC-005マーカーは`execution_boundary_policy.md:35`に実在 |
| P1-9(一部) | cert_renew_policy.md CERT-024表の「毎月1日 00:35」を`roles/systemd_timers/defaults/main.yml`の`cert-renew-quory`エントリへのポインタへ。unifi_backup_fetch_policy.md UNIFI-014の深夜帯参考実値(01:00/02:00/03:00/03:30)を削除しポインタへ | `roles/systemd_timers/defaults/main.yml:63-67`に`cert-renew-quory`(schedule: `*-*-01 00:35:00`)実在確認 |
| P2-1 | coordinator.md:80の参照先を`docs/ai/status.md`「載せていないもの」から`docs/ai/memory/decisions/rejected-proposals.md`へ | ファイル実在確認(`ls`)、移設commit `a830672`実在確認(`git log`) |
| P2-2 | incident_capture_policy.md冒頭「状態:」行の改訂権限参照先を`coordinator.md`から`execution_boundary_policy.md`(EXEC-030)へ | EXEC-030マーカーは`execution_boundary_policy.md:70`に実在 |
| P2-3 | core.md:49の括弧書き参照先を`coordinator.md`から`execution_boundary_policy.md`へ | 同Policyの4.1表・EXEC-010が「届く/届かない」の区分を実際に持つことを確認済み |
| P2-4 | autonomous_recovery_policy.md AR:152の未定義識別子「P4」を削除し「条件を満たす段だけを実行する」へ | flag: 元finding記載どおり、P4の由来は文書内から特定できず削除で対処(確定度が一段落ちる指定どおり) |
| P2-5 | unifi_backup_fetch_policy.md UNIFI-014から`ubuntu_vm_patch_policy.md`「深夜リブートスケジュール」参照を除去(P1-9と一体で実施) | `ubuntu_vm_patch_policy.md`側は既にUV-079でOperations Contextへ委譲済み(値を持たない)であることをfindings記載どおり確認 |
| P2-6 | time_sync_check_policy.md「§3参照」×2箇所を「TIME-007参照」へ置換 | TIME-007マーカーは同ファイル40行に実在。置換後`§3参照`の残存は0件(grep確認) |
| P3-2 | time_sync_check_policy.md TIME-005の500ms/5000ms実値を削除し`roles/time_sync_check/defaults/main.yml`へのポインタへ(「他ホストより大きい専用閾値」の意味論は維持)。unifi_backup_fetch_policy.md UNIFI-010(世代数8)・UNIFI-012(60秒、pve2側500ms参照)・§11既定パラメータ表(208-219相当)の実値を削除し`roles/unifi_backup_fetch/defaults/main.yml`(pve2側同期監視の閾値は`time_sync_check_policy.md` TIME-005)へのポインタへ | 両role defaultsファイルで該当変数の実在確認(`time_sync_check_threshold_ms`/`time_sync_check_sophos_threshold_ms`/`unifi_backup_keep_generations`/`unifi_backup_freshness_max_seconds`) |

## 自己検証の結果

- 14項目すべてについて、修正後の文が指す参照先(ファイル・節・ルールID)の実在をgrep/lsで確認した(上表右列)。
- 実値を落とした箇所の同一文書内での取り残しを確認:
  - cert_renew_policy.md: 「00:35」「毎月1日」の残存は0件。
  - time_sync_check_policy.md: 「500ms」「5000ms」の残存は0件。「§3参照」の残存は0件。
  - unifi_backup_fetch_policy.md: 「8 世代」「既定 60」「既定 8」「500ms」の現行規範箇所での残存は0件。ただし§12「実機検証状況(2026-06-15, pve1)」に「8 世代超の実削除は…」という記述が残る — これは日付付きの実機検証記録であり、当時の設定値を記録した歴史的事実の記述であるため、現行仕様を語る箇所とは区別してscope外(未変更)とした。
  - execution_boundary_policy.md: 「それ以外」行からの`monnie`除去後、`monnie`が「到達手段が無い」行にのみ属する状態を確認。
  - cert_renew_cloudkey_policy.md: 「ansy」を実行元として述べる箇所を全文検索し、§1比較表・§2 CCK-003・§5自動実行例の3箇所すべてを修正済み(認証方式比較表のcert_renew側「ann鍵」は無関係な別記述のため変更していない)。
- `python3 scripts/check-doc-consistency.py` 実行結果: `[check1] OK (114 compared)` / `[check2] OK (8 compared)` / `[check3] OK (102 compared)`、exit 0。
- `git status --porcelain`で変更ファイルを確認し、上記10ファイル以外に自分による変更が無いことを確認した(他に多数のファイルが変更状態にあるが、これらは並行稼働中の別agent[Group B]によるものであり、自分は一切触れていない)。

## scope外と判断して触れなかったもの

- Group B(context/skills/agents/分類3本/coordinator.mdの他行)は依頼のとおり一切編集していない。並行変更中の未追跡ファイルにも触れていない。
- 第2束(P1-4、P1-8/P5-3、P3-1、P5-1/P5-2、S2-3、C5-1〜C5-5、S5-2、C3-3、未確認11件)は依頼scope外のため未着手。
- P1-9のうち本表(Group A)に明記されていないcert_renew_policy.md §5「scheduleもrepoにある」節(`cert_renew.yml`のSemaphoreスケジュール正本ポインタ)は、finding時点で既にポインタ化済みであり修正不要と判断し変更していない。

## 未解決事項

- なし。14項目すべて完了。ansible/ssh実行なし、git add/commit/pushなし。
