# Implementation: Proxmox週次パッチ後の古いkernel削除

日付: 2026-11-28 / Role: Implementer

## 変更内容と判断

- `proxmox_patch_apply_node` の `always` 節で、post-healthcheckの再試行後・final report作成前に `tasks/kernel_cleanup.yml` をincludeした。初期値は `unevaluated` とし、途中失敗でもreport/通知の未定義参照を起こさない。
- 収集shellは `uname`、`dpkg-query`、`proxmox-boot-tool kernel list` の収集とJSON化だけを行う。残す集合、対象、apt simulationの厳密照合は副作用のないPython純関数へ分けた。
- `dpkg --simulate --purge` と `apt-get -s purge` が同じ対象を示し、aptに`Inst`/`Conf`が無い場合だけ、名前を明示した `dpkg --purge` を実行する。R4不成立およびcleanup途中の失敗は `aborted`、削除後検証の不成立は `broken` とする。
- R7では`dpkg --audit`、起動用kernel集合の不変、running/keep kernel、`proxmox-ve`、`proxmox-default-kernel`、kernel meta package、hook失敗文字列を確認する。`broken`ではapplyをFAILEDにして既存weekly-fullの後続node停止経路へ渡す。
- reportへ新規 `kernel_cleanup` objectを追加した。既存の再起動前 `running_kernel` は変更していない。通知には成功時は削除件数・範囲・保持kernel、その他は理由を載せ、`aborted`はwarningとした。
- 配備物は通常apply roleのPhase 2で毎回 `/usr/local/sbin/` へcopyする。新規setup playbookは不要。ただし、Phase 2以前にapplyが止まる週はR1によりcleanupも実行されない。

## 自己検証

- `python3 roles/proxmox_patch_apply_node/tests/test_kernel_cleanup_evaluate.py`: PASS。boot-toolの実測形、`rc`混在、pin、不在/非最新running kernel、`Remv`/`Purg`、`Inst`/`Conf`を検証。
- `ansible-playbook roles/proxmox_patch_apply_node/tests/test_kernel_cleanup_task.yml`: PASS。productionと同じ `kernel_cleanup.yml` をlocalhostでincludeし、AC2〜AC6相当の `skipped`/`aborted`/`broken`/`removed` のreport objectと通知status/見出し値を確認。
- `ansible-playbook --syntax-check playbooks/proxmox_patch_apply_node.yml`: PASS。
- role内の既存 `tests/test_*.yml` 全件: PASS。
- `scripts/check-doc-consistency.py`、`scripts/check-tester-gate.sh`、`git diff --check`: PASS。`check-staged-yaml.py` は未stageの新規ファイルをindexから読めないためwarningでskipしたが、対象playbookと新規fixtureのsyntax checkは別途PASS。

## 未検証事項・残存リスク

- 実ホストには接続していない。実際の`dpkg` hook出力、apt simulation書式、初回一括purgeの所要時間、ESP/パッケージの最終状態、およびSlack本文の実長は次のkernel更新・再起動週にCoordinatorが確認する必要がある。
- requirement §7の「実測出力そのもの」は文書内に要約しか無く、fixtureはそこに明記されたkernel集合・状態・simulation事実から構成した。原文の完全なstdoutが別途必要なら、fixtureへ置換して再実行する。
- Policy、Role文書、`status.md`は変更していない。既存のPolicy差分SB-100とrequirement/plan-reviewは着手時からの変更であり、本実装では変更していない。

## 追記: 実測原文fixture (2026-11-28)

- `2026-11-28_001a_measured_output.md` の4つのtext code blockを、試験がファイルから直接読むfixtureへ追加した。値を試験へ再掲していない。
- 原文はstatus出力とkernel listを連結し、`None.` を使う。parserはlist見出し前のstatus行を無視し、`None`と`None.`の両方を空のmanual選択として受理するよう修正した。list節内の不正なkernel行は従来どおりfail-closedである。
- 原文fixtureで両nodeの保持集合を解析し、apt simulationの`Inst`/`Conf`による停止、およびdpkg simulationのエラーによる停止を確認した。

## 追記: 004/005差し戻しへの対応 (2026-11-28)

- Major M1 / D3: notification statusの優先順位を既存どおり「apply failure / abort type は `error`、それ以外のcleanup `aborted`またはpost-healthcheck異常は `warning`」へ戻した。
- Major M2: purge直前に`purge_started`を記録し、purgeの失敗・timeout・purge後の収集/解析/検証中の例外はrescueで`broken`にする。purge出力は最大3,000文字を`kernel_cleanup.purge_output`へ残す。`broken`は`kernel_cleanup_broken`としてapplyをFAILEDにし、件名にもkernel削除起因を明記する。
- Major M3: purgeだけは`proxmox_patch_apply_kernel_cleanup_purge_timeout: 1800`(30分)を使う。collect/simulationは従来の120秒のままである。
- Major M4 / D2: 前後の`ii`状態の`proxmox-kernel-<series>`および`proxmox-default-kernel`の名前集合を比較する方式へ変更した。正規表現のdotはAnsibleで安全に評価できる`[.]`とした。
- Major M5 / Minor 1: `proxmox_kernel_cleanup_fixture`と、その結果objectを注入するfixture試験を削除した。本番taskへ試験専用の結果注入口は残していない。command pathは通常値を既定とするrole変数化だけを行い、localhost stubから同じtaskを実行できる形にした。
- Minor: 削除範囲はPython側でversion順に作った`target_kernels`の最古〜最新を表示する。収集rc非0は`aborted`(warning)へ変更し、理由文字列は`trim`する。

再検証: Python parser試験4件、対象playbookのsyntax check、既存role YAML fixture全件、`git diff --check`はPASS。追加した`test_kernel_cleanup_task_flow.yml`は一時ディレクトリ内のcollector / timeout / dpkg / apt-get stubを使い、本番の`kernel_cleanup.yml`を直接includeして、評価成功→両simulation→purge→post-purge collection/evaluation→meta集合照合→`removed`までを通した。実ホスト・Slackへの接続は行っていない。

## 追記: 006/007と今回の引継ぎ依頼への対応 (2026-11-28、Implementer/Codex)

### 変更と判断

1. **恒常試験**: `test_kernel_cleanup_task_flow.py` は毎回 `main.yml` をYAMLとして読み、cleanupのinclude、final report作成、通知のsubject/status/channel/本文組立て、末尾のRe-raiseを実行する。cleanup本体は本番ファイルを直接includeし、結果objectは注入しない。各caseを新しいlocalhost playbookプロセスで実行し、収集・dpkg・aptだけを `/tmp` のstubへ向ける。`_eval_notify_case.yml` の通知式の複製と `_eval_notify_case_parity.yml` のgrep照合も廃止し、`extract_production_notify.py` / `_load_production_notify.yml` による本番taskの読み込みへ置換した。抽出対象にはSlack送信taskを含めない。
2. **30分purge**: `async: purge_timeout + 30` / `poll: 0` でSSH接続から切り離して起動し、`async_status`を5秒間隔で照会する。コマンド自身のtimeoutは既定1800秒、TERM後のkill猶予10秒で維持し、async側に30秒の余裕を与える。UNREACHABLEはrescueに入らないため、launch/poll結果を `ignore_unreachable` で受け、到達性・job id・完了・rcをassertして通常の失敗へ変換する。着手後の切断・timeout・検証失敗はすべて `broken` → `_apply_failed: true` / `kernel_cleanup_broken` → FAILED/終了コード2。完了済みのasync cacheだけを消す。
3. **skip理由の空白**: gateの理由へ `trim` を適用した。
4. **purge出力**: stdoutとstderrを合わせた末尾3000文字をreportへ保存する。hook検査は切り詰め前の全出力を使う。
5. **失敗taskと理由**: rescueは実際の `ansible_failed_task.name` を保存し、通知の失敗taskへ渡す。削除着手前のrescueは「削除着手前」、着手後は「削除開始後」と記録する。purge失敗後に追加観測も失敗した場合、最初の失敗理由/taskを保持する。
6. **版形式の異常の可視化**: numeric ABI (`major.minor.patch-build-pve`) のみ整数tupleで比較する。未対応形式は削除せず、版文字列を含む理由付き `aborted` (WARNING/warning/alerts) を返す。その他のR2不成立は理由付き `skipped` のまま。評価プロセス自体の失敗・空出力も `aborted` とし、毎週SUCCESSに埋もれる経路を閉じた。
7. **途中削除の記録**: purgeの成否にかかわらずalwaysで再収集し、事前のtargetsと事後一覧の差を `removed` に保存する。`rc`などの残存レコードはpurge完了と数えず、不在または `un`/`pn` を完了と数える。boot-toolやauditの検証より先に差分を保存する。再収集不能時は `removed: []` / `removal_observed: false` とし、削除ゼロと確認できた状態とは区別する。
8. **reportの肥大**: `packages` 全件と `boot_tool_output` をreport objectから除いた。検証に必要な `protected_packages` (iiのkernelメタ/default/veの名前集合)とkernel/target/removed一覧を保持する。boot-toolの生出力は内部収集factにだけ残し、前後比較する。

実行blockを `kernel_cleanup_run.yml`、削除後の観測/検証を `kernel_cleanup_verify.yml` に分けた。入口のincludeでgateを判定するため、実行中にstatusが `broken` に変わってもalways内の追加観測がgateによってskipされない。

### 自己検証と観測

- `ansible-playbook -i localhost, roles/proxmox_patch_apply_node/tests/test_kernel_cleanup_task_flow.yml`: PASS。25分岐 + 実際の `--check` 1件 + 通知status順序のmutation 1件、計27ケース。report JSONのresultとcleanup、通知4要素、終了コードまでassertする。
  - 正常: removed/ok/patches/終了0。削除2件・版範囲・保持3版が本文に載る。
  - purge rc非0・部分削除・timeout、メタ欠落・audit・hook・boot変更・事後収集失敗: broken/error/alerts/FAILED/終了2。部分削除とtimeoutは、対象2件中実際に消えた1件だけが `removed` に残り、出力末尾のTAILが保存される。
  - 起動応答/完了照会の接続喪失: localhost専用connection pluginで `AnsibleConnectionFailure` を発生させ、いずれもbroken/FAILED/終了2、reportと通知値の生成を確認。pluginはlocal connectionを継承し、SSHは使わない。stubの終了を確認してから接続喪失を返す。
  - 収集rc非0・不正JSON・simulation rc非0/timeout/空出力/Inst+Conf・未知の版形式: aborted/warning/alerts/終了0、purge未呼び出し。
  - 再起動なし・post-HC CRITICAL・適用失敗・abort typeのみ・failedのみ・対象なし: skipped。適用失敗/abort typeとpost-HC UNKNOWNの組合せでもstatusはerrorを優先する。
  - 本番から読み込んだ `_notify_status` のerror/warning分岐をメモリ上で逆転したmutationは、通常のassertが `warning != error` で失敗することを確認した(repoのmain.ymlは変更しない)。
- 同YAMLを `--check` 付きで実行: PASS。配下driverにも本物の `--check` を渡し、collector/dpkg/apt未呼び出し・package state不変・理由文字列の型/末尾空白をassertした。
- Python: `test_kernel_cleanup_evaluate.py` 6件、既存 `test_changelog_scope.py`: PASS。
- 既存roleの `test_*.yml`、`test_hc_collection_failure.sh`、対象playbookの `--syntax-check`、role内YAML全24ファイルのworking-tree parse、collectorの `bash -n`、`scripts/check-doc-consistency.py`、`scripts/check-tester-gate.sh`、`git diff --check`: 検証結果は末尾追記に記載する。indexは変更しておらず、新規include先もworking treeを直接構文検査した。

### 今回の変更ファイル (引継ぎ時の内容との差分)

すべて `roles/proxmox_patch_apply_node/` 配下、または本記録への追記。

- `defaults/main.yml` (非同期実行のtimeout説明)
- `files/proxmox-kernel-cleanup-evaluate.py`
- `tasks/kernel_cleanup.yml`、新規 `tasks/kernel_cleanup_run.yml`、新規 `tasks/kernel_cleanup_verify.yml`
- `tests/_eval_notify_case.yml`、`tests/_eval_notify_case_parity.yml`、新規 `tests/_load_production_notify.yml`
- 新規 `tests/extract_production_notify.py`、新規 `tests/kernel_cleanup_stub.py`、新規 `tests/connection_plugins/kernel_cleanup_local.py`
- `tests/test_kernel_cleanup_evaluate.py`、`tests/test_kernel_cleanup_task_flow.yml`、新規 `tests/test_kernel_cleanup_task_flow.py`
- `tests/test_notify_stop_reason.yml`、`tests/test_notify_warning_on_critical.yml` (旧parity説明を更新)

### 未検証・制約

実ホストへansible/ssh/apt/dpkgを実行せず、Slackにも送信していない。実際のSSH断・30分待機・dpkg/hook/ESPの挙動は未観測であり、既存の本番初回観測事項を維持する。接続喪失中の非同期purgeはホスト側timeoutまで動きうるため、その時点の再収集ができなければ最終削除一覧は確定できない (`removal_observed: false`)。今回のMinorはすべて修正し、修正見送りはない。

最終検証: role内 `test_*.yml` 全9件 (新しいflow試験を含む)、`test_hc_collection_failure.sh`、Python試験、syntax check、working-tree YAML検査、shell構文、文書整合 (126/4/115/6件比較)、tester-gate (63 playbook)、`git diff --check` はすべてPASS。起動した検証セッションはすべて終了した。Policy/Role/statusとscope外の着手時差分はbaselineとbyte一致、本記録の元本文もprefix一致を確認した。stage/commitは行っていない。

## 追記: 008 Minor 1 / 009 Minor 1のみの修正 (2026-11-28、Implementer/Codex)

- 変更ファイルは `tasks/kernel_cleanup_run.yml`、`tasks/kernel_cleanup_verify.yml`、`tests/test_kernel_cleanup_task_flow.py` (いずれも `roles/proxmox_patch_apply_node/` 配下)、および本記録への追記のみ。
- **009 Minor 1**: stdoutとstderrの区切りを、エスケープ文字列から `'%c' | format(10)` による実際のLF生成へ変更した。末尾3000文字の保存は維持する。本番taskを実行する既存のpurge rc非0/部分削除ケースに、`'x\nPURGE FAILURE TAIL'` の存在とリテラル `r'x\nPURGE FAILURE TAIL'` の不在をassertする試験を追加した。修正前の本番taskで新しいassertが落ちることを再現し、修正後は実際のAnsible実行→report JSON読込まで通してPASSを確認した。
- **008 Minor 1**: purge着手後、完了が確認できない、または完了照会が到達不能の場合、rescueの理由へ「host側のpurgeが継続している可能性があります」を追記する。既存の通知本文・reportは同じ理由を使うため両方へ表示される。取得できた起動結果のjob idをreportの `kernel_cleanup.async_job_id` へ保存し、起動応答断で取得できなかった場合は空文字列にする。区分・終了コード・待機/削除制御は変更していない。
- 局所試験で、起動応答断は `broken`/FAILED/終了2・継続可能性の文言あり・job id空、完了照会断は同じ区分/文言かつ取得済みjob idあり、を確認した。恒常試験はreportと通知本文の文言、job idの文字列型と起動結果との一致もassertする。完了が確認できたpurge失敗・検証失敗へは継続可能性の文言を付けないこともassertする。

自己検証: 本番task/通知式を通すflow全27ケース (3テスト、98.6秒)、既存YAML試験8件、parser試験6件、既存changelog試験、`test_hc_collection_failure.sh`、対象playbookの `--syntax-check`、role内YAMLのworking-tree parse、文書整合検査、tester-gate検査、`git diff --check` はすべてPASS。起動した検証セッションはすべて終了した。今回の指定2点以外に変更はなく、本記録の元本文は保持し、Policy/Role/statusとその他の着手時差分はbaselineとbyte一致を確認した。実ホストへansible/ssh/apt/dpkgを実行せず、Slack送信・stage/commitもしていない。今回分の未解決事項なし (実SSHの挙動は引き続き未観測)。
