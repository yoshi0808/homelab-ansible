# review: Round 2 close(marker drift是正 + tester-gate-condition2新設)

日付: 2026-07-31
Reviewer: 独立subagent(実装記録 `2026-07-31_020_round2_close_implement.md` の著者とは別体)
使用Skill: `skills/document-norm-review/SKILL.md`(主)、`skills/code-review/SKILL.md`(出力型)

## 対象

- `docs/ai/policies/ansible_test_safety_policy.md`(TS-034 / TS-035新設)
- `scripts/check-tester-gate.sh`(条件2マーカー検査の追加)
- `playbooks/cloudkey_cert_deploy.yml` / `playbooks/proxmox_backup_restore_verify.yml` / `playbooks/unifi_backup_fetch.yml`(ヘッダ是正 + `# tester-gate-condition2:` 付与)

`docs/ai/status.md` と `docs/ai/reviews/check_mode_semantics/2026-07-31_019_*` は依頼のscope外のため対象外とした(diffに残存を確認したが未読・未評価)。

## Code Review: check_mode_semantics Round 2 close

### Summary

Policy改訂(TS-034/TS-035)は既存条項(TS-006/TS-009/TS-019/TS-026/TS-030)と矛盾せず、機械検査の限界もscript本文3箇所・Policy 1箇所に明記されている。3本のヘッダ書き換えも実際の`pre_tasks`停止assertおよび`cloudkey_cert_deploy`の条件2記述(issue.yml/deploy.ymlの現物)と一致することを確認した。lintの両方向(弾く/通す)を自分で実行し検証した。唯一の実質的な欠陥は、`roles/cloudkey_cert_deploy/tasks/main.yml`に残る、TS-030導入前の前提(「`--check`込みで常に本実行」)を述べた重複マーカーが今回のscope外として未修正のまま残っていること。これは実装者自身も未解決事項として記録済みだが、working tree上には現存しており、TS-026が禁じるmarker driftの実例であるため finding として報告する。

### Critical Issues

なし。

### Major Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | roles/cloudkey_cert_deploy/tasks/main.yml | 12-16 | `# tester-gate: risk-accepted — worst case of running this unconditionally (incl. under --check) is a broken/unverified CloudKey Web UI TLS cert ... there is no dry-run distinction for this playbook.` が、今回の3本ヘッダ是正後も未修正のまま残存している。TS-030(`--check`は停止assertで止まる)導入後、この記述は事実と逆(`--check`は"unconditionally"実行されず、`playbooks/cloudkey_cert_deploy.yml`のpre_tasks assertで実行前に停止する)。TS-026「分類名、理由文、実際の抑止guard名、実行経路が一致しているか」に照らして典型的なmarker drift。lint(`scripts/check-tester-gate.sh`)は`playbooks/`配下のみを検査するためこの行は機械検査の対象外であり、放置しても再発検知されない。 | Major |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | docs/ai/policies/ansible_test_safety_policy.md | 169 | §8変更履歴に新設した行が、テーブルの他行(直前の168行目を含め本diffで`\|`終端に統一済み)と異なり末尾の`\|`を欠く(`... _020_round2_close_implement.md\`` で行末、閉じ`\|`なし)。GFMは寛容だが同一テーブル内で表記が割れており是正が望ましい。 | style |
| 2 | roles/cloudkey_cert_deploy/tasks/main.yml | 12-16 | Major #1の恒久対応として、他role(`roles/incident_sync/tasks/install_timer.yml`、`roles/ubuntu_vm_full_upgrade/tasks/main.yml`)が採る「分類・理由を複製せずplaybookヘッダを参照するだけ」の書き方に合わせるか、内容を更新して両者を同期させるかをCoordinatorに判断してもらう。 | consistency |
| 3 | playbooks/proxmox_backup_restore_verify.yml | 25-33 | ヘッダは「`--check`を渡すとpre_tasksの停止assertにより変更を一切行わずに停止する」と書くが、実際にPlay3(`brv_restore_targets`、変更を行うplay)自体には停止assertが無く、Play2のassert失敗により`add_host`が実行されずグループが空になる(=0ホストで自動的にno-op)という間接的な機構で止まっている。TS-030は「変更を行うplayすべて」にpre_tasks assertを要求しており、Play3単体はこの文言を字義通りには満たさない。現状は安全に機能しており今回のdiffが持ち込んだ新規の問題ではないが(構造は変更前から存在)、書き換えたヘッダが「pre_tasksの停止assert」を単数形で述べることで、読み手が「各playにassertがある」と誤読しうる。実装記録(`2026-07-31_020_round2_close_implement.md`)の(1)節はこの機構を正確に説明しているが、playbookヘッダ本体には反映されていない。低優先度だが、TS-030の字義とのギャップとして記録しておく。 | documentation-gap |

### What Looks Good

- **TS-034 / TS-035と既存条項の整合**: TS-034はTS-006(マーカー形式)の直後、TS-035はTS-019(機械チェック)の直後に置かれ、既存条項の意味を変更せず追加条件として積んでいる。TS-009の条件2の文言をそのまま参照しており、新しい定義を作っていない。TS-030(停止assert)・TS-026(marker drift照合)とも矛盾しない。TS IDの重複も無いことを`grep -o "<!-- TS-[0-9]* -->" | sort | uniq -c`で確認した(全ID出現1回)。
- **機械検査の限界の明示**: `scripts/check-tester-gate.sh`のヘッダコメント・エラー時ガイダンス・Policy TS-035の3箇所すべてで「著者が条件2を述べたことの確認であり、主張の正しさの確認ではない」という限界が明文化されている。本リポジトリが過去に「効かない検査が誤った安心を生む」ことを理由に検査自体を見送った経緯を踏まえると、この書き方は実質的な要求を満たしている。
- **3本のヘッダと実際の挙動の一致**: 3本すべてで`pre_tasks`の`ansible.builtin.assert: that: not (ansible_check_mode | bool)`の実在を確認した(`cloudkey_cert_deploy.yml` L31-43、`proxmox_backup_restore_verify.yml` Play2 L66-78、`unifi_backup_fetch.yml` Play2 L59-71)。ヘッダの「`--check`を渡すと停止する」「`--check`なしでは常に本実行する」という記述は3本とも実装と一致している。旧文の「community.general.slackはcheck_mode対応モジュールで...」という、TS-030導入前提の説明(Slack通知taskへ到達しうる設計だった名残)も正しく削除され、TS-031への参照に置き換わっている。
- **`cloudkey_cert_deploy`の条件2記述の現物照合**: `roles/cloudkey_cert_deploy/tasks/issue.yml`を読み、更新要否判定task(`cert_needs_renewal`相当)が存在せず無条件で新規のRSA鍵生成・CSR発行・署名を行うことを確認した。`tasks/deploy.yml`も読み、login→CSRF導出→upload(`register: cloudkey_upload`→`cloudkey_new_id`/`cloudkey_new_fp`を後続taskが直接参照)→activate→`community.crypto.get_certificate`による実TLSハンドシェイクでの被served証明書検証→検証OK時のみ旧証明書削除、という一直線の非冪等`uri`/`get_certificate`連鎖であることを確認した。ヘッダの条件2記述はこの現物と一致している。
- **他roleの`tester-gate`言及との比較**: `grep -rn "tester-gate" roles/`で全4件を洗い出し、`cloudkey_cert_deploy/tasks/main.yml`以外(`incident_sync/tasks/install_timer.yml`、`ubuntu_vm_full_upgrade/tasks/main.yml`、`incident_sync/templates/incident-sync.service.j2`)はいずれも分類・理由文を複製せず「playbookのtester-gateマーカーを参照」する形で書かれていることを確認した。分類・理由文を丸ごと複製しmarker driftを起こしているのは`cloudkey_cert_deploy/tasks/main.yml`のみ(Major #1)。
- **撤回した文言の掃引**: 旧文言「`--check`の有無にかかわらず常に本実行する」をrepo全体(`.yml`/`.md`/`.sh`)でgrepし、変更履歴表(履歴として残すべき記述)以外に残存が無いことを確認した。

### Role側マーカーについての判定

`roles/cloudkey_cert_deploy/tasks/main.yml`の`# tester-gate:`様の記述は、Policy(TS-005〜TS-035)がいずれも`playbooks/`配下のマーカーだけを一次情報・検査対象と定義しているため、**Policy上は非権威(TS-002「判断はplaybook先頭のマーカーを一次情報とする」)だが、`scripts/check-tester-gate.sh`が`playbooks/`しか見ない結果、role側に残った同型記述はlintの外に存在し続けられる**。今回の現物確認で、その死角に実際の陳腐化した記述(Major #1)が存在することを確認した。他roleは分類・理由を複製せずplaybook参照に留めているため、「role側にマーカー相当の記述があってよいか」への回答は「複製せず参照に留める形なら問題ないが、分類・理由文を複製すると機械検査の外でmarker driftが再発する」。恒久対応(削除して参照形にする/内容を同期する)はCoordinatorが判断する事項として残す。

### Verdict

Request Changes — Major #1(role側marker driftの残存)の解消をCoordinatorへ返す。他の3項目(Policy改訂・lintスクリプト・3本のヘッダ本体)はApprove相当。

## 自己検証で確認したこと

- **lintの両方向**: 使い捨てディレクトリ(`mktemp -d`)へ`scripts/check-tester-gate.sh`をコピーし`repo_root`のみ書き換えて実行。
  - 弾く方向: (B)条件2マーカー無し、(C)`# tester-gate-condition2:`のみで理由が空、(D)コロン後が空白のみ、(E)マーカーがインデントされ行頭`#`でない、の4パターンいずれも`ERROR: ... risk-accepted なのに '# tester-gate-condition2:' マーカー...がありません`でrc=1になることを確認。
  - 通す方向: risk-accepted + 停止assert + 非空`# tester-gate-condition2:`を持つfixtureで`[tester-gate-lint] OK`・rc=0を確認。
  - 検証用の一時ディレクトリは検証後に削除済み(作業ツリー外に残存物なし)。
- 本体`scripts/check-tester-gate.sh`をリポジトリ直下で実行し`[tester-gate-lint] OK (46 playbooks)`・rc=0を確認(`ls playbooks/*.yml | wc -l`も46で一致)。
- `grep -h "^# tester-gate:" playbooks/*.yml | sort | uniq -c`で`risk-accepted`が3本(cloudkey_cert_deploy / proxmox_backup_restore_verify / unifi_backup_fetch)のみであることを確認。3本とも`# tester-gate-condition2:`を持つことを確認。
- 3本の`pre_tasks`停止assertの実在を現物ファイルで直接確認(実行はしていない。read-onlyのRead)。
- `roles/cloudkey_cert_deploy/tasks/issue.yml`・`tasks/deploy.yml`を現物で読み、実装記録の条件2主張を裏取りした(鵜呑みにしていない)。
- `grep -rn "tester-gate" roles/`で役割側の全言及を洗い出し、`cloudkey_cert_deploy`以外は参照形であることを確認。
- Policy全文を読み、TS-034/TS-035それぞれのマーカーコメントが1回ずつのみ出現すること(`<!-- TS-034 -->`/`<!-- TS-035 -->`のgrep -c`)、他TS IDとの重複が無いことを確認。
- 撤回文言「`--checkの有無にかかわらず常に本実行する`」をrepo全体でgrepし、変更履歴表以外への残存が無いことを確認。
- ansibleコマンドは`--syntax-check`も含め一切実行していない(実行記録は実装者側の`2026-07-31_020_*`にあり、本レビューでは対象playbookをrunしていない)。

## 未解決事項

- **Major #1**: `roles/cloudkey_cert_deploy/tasks/main.yml` L12-16の重複・陳腐化したtester-gate記述の扱い(削除して参照形にするか、内容更新するか)をCoordinatorが判断する必要がある。
- Suggestion #1: 変更履歴表169行目の`\|`終端統一。
- Suggestion #3: `proxmox_backup_restore_verify.yml`のPlay3がTS-030の字義(「変更を行うplayすべて」にpre_tasks assert)を厳密には満たさず、Play2経由の間接ゲート(空ホスト化)に依存している件。今回のdiffが持ち込んだ新規問題ではないが、ヘッダの新しい文言が単数形で「pre_tasksの停止assert」と書くことで誤読の余地が生じている。棚卸し文書側で扱うか、Play3へも明示的なassertを足すかはCoordinator判断。
- `docs/ai/status.md`と`2026-07-31_019_round2_batchC_quory_test_result.md`の並行更新については、依頼の対象外として本レビューでは評価していない(実装者記録の未解決事項欄にも同旨の記載あり)。
