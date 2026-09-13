# quory NVMe取得ツール配備 — 実装記録

要求追補012、計画追補013（査読014 Approve）、既存`docs/ai/policies/quory_health_monthly_policy.md`に基づく初期実装。実ホスト・quory・外部APIには一切到達していない。

## 変更ファイル

- 新規 `playbooks/quory_nvme_setup.yml`（`# tester-gate: check-mode-native`、`hosts: quory`）
- 新規 `roles/quory_nvme_setup/`
  - `defaults/main.yml`（`quory_nvme_setup_package: nvme-cli`）
  - `tasks/main.yml`（apt冪等導入＋`when: not ansible_check_mode` + `tags: [destructive]`のCLI readback block）
- 更新 `roles/semaphore_templates/defaults/main.yml`（`quory_nvme_setup.yml`用template 1件を追加、既存R7の9本setupと同じ引数なしパターン。scheduleは追加していない）
- 更新 `playbooks/README.md`（`quory_health_monthly.yml`の直後へ追加）
- 更新 `docs/ai/context/operations/quory-health-monthly.md`（「NVMe取得ツールの配備」節を新設、入口節の記述を更新、未確定リストを実機readback待ちへ整理）
- 本記録 `docs/ai/reviews/quory_health_monthly/2026-09-13_015_nvme_setup_implementation.md`

**既存`playbooks/quory_health_monthly.yml`・`roles/quory_health_monthly/`は変更していない。**

## 設計判断の要点

- `hosts: quory`は既存の`dev_investigate_setup.yml`・`worktree_sync_setup.yml`・`operator_request_channel_server_setup.yml`と同じ、quory限定setup系の確立済み慣習（実host名をinventoryに直接書く。decoyではない）。inventory側の`control_nodes`グループが`quory`単体である現状と矛盾せず、`quory_health_monthly.yml`側で採用した`groups['control_nodes']`照合guardは踏襲していない（この慣習ではplayの`hosts:`自体がguardであり、二重にguard taskを持たせると既存setup系との一貫性が崩れる）。
- role本体は`ansible.builtin.package_facts`（read-only、導入状態の確認）→`ansible.builtin.apt`（`update_cache`をpackage_facts結果から導出、`state: present`はAPTモジュール自身のcheck_modeサポートにより`--check`ではパッケージ変更なしに「導入見込み」を表示）→readback（`nvme version`）の3タスク構成。TS-014の「read-onlyな診断taskには`check_mode: false`、破壊的task（またはblock）には`when: not ansible_check_mode` + `tags: [destructive]`」の型に従い、実際にコマンドを実行するreadbackだけを明示的にcheck_modeから外した（`package_facts`・`apt`はいずれもcheck_mode下で安全に動作するため個別のゲートを要しない）。
- readbackタスクは`failed_when`を上書きしていない。`ansible.builtin.command`モジュールの既定動作（rc≠0で失敗）がAC-S2の「コマンドが使えなければ成功扱いしない」を素直に満たすため、追加のassertは冗長と判断し置いていない。
- Semaphore templateはR7の9本setup系と同じ引数なしパターンに合わせ、survey_varsを持たせていない。scheduleは要求P0で明示的に対象外（`nvme-cli`導入をSemaphore自身の定期処理へ自動で載せる判断は別途）。

## 自己検証

- `ansible-playbook --syntax-check playbooks/quory_nvme_setup.yml`: rc0
- `bash scripts/check-tester-gate.sh`: OK（63 playbooks、新規1件を含む）
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `git diff --check`: rc0
- `ansible-lint playbooks/quory_nvme_setup.yml roles/quory_nvme_setup`: `Passed: 0 failure(s), 0 warning(s)`（profile production）。参考として既存`roles/quory_health_monthly`にも同コマンドを実行し、var-naming等の指摘があることを確認した——本リポジトリはansible-lintをゲートに使っていない（`.ansible-lint`設定なし、`check-tester-gate.sh`/`check-doc-consistency.py`のいずれにも含まれない）ため必須検証には数えていないが、新規追加分は指摘ゼロであることを併せて記録する。
- `python3 -m unittest discover -s tests -p "test_*.py"`: 71/71 OK（quory_health_monthly側の既存回帰、今回の変更でファイルを触っていないことの確認）。

**`operation`の実行・`--check`の実行はしていない。** `hosts: quory`は実際にAnsible接続を試みる経路であり、Implementer役の「実ホストへansibleを実行しない（状態を変えない確認も含む）」に該当するため。ロジックはapt moduleの標準check_mode契約と、既存のcheck-mode-native設計パターン（`sandbox_auto_patch`等）への静的な準拠確認で検証した。

**tests/は追加していない。** 本roleはPythonロジックを持たず（`ansible.builtin.apt` + `ansible.builtin.command`のみ）、単体テストで検証できる独自の分岐・パース処理が無い。ローカルでapt実行を伴う検証（decoy含む）はansy自身のパッケージ状態を実際に変更するため、requirement/plan・execution_boundary_policyのいずれも許可していない範囲と判断し行っていない。

## 差し戻し対応（2026-09-13、016_nvme_setup_diff_review.md Major #1/#2）

016を現物確認し、blocking Major 2件を修正した。016は編集していない。

- **Major #1（対象不在時の空成功）**: `hosts: quory`だけで、`quory`を欠くinventoryでは0台マッチ・rc=0の空成功になり得た（`--list-hosts`で確認済みの実測どおり）。`playbooks/quory_nvme_setup.yml`の先頭へ`hosts: localhost` + `connection: local`のpreflight playを追加し、`'quory' in hostvars`をassertするようにした。quoryが存在しなければこの時点でrc非0となり、後続playへ進まない。
  - 検証: `ansible-playbook -i 'localhost,' playbooks/quory_nvme_setup.yml`（Ansible組み込みの合成inventory、`localhost`しか存在しない）を実行し、preflight assertがfailしてrc=2で全体停止すること、2番目のplayが一切実行されないことを確認した。実ホストへは一切接続していない。
  - 対照検証: `ansible-playbook -i inventories/homelab/hosts.yml --limit localhost playbooks/quory_nvme_setup.yml`（実inventoryだが`--limit localhost`で対象を`localhost`だけに絞る）を実行し、`quory`が実inventoryに存在する場合はpreflight assertが`ok`で通過し、2番目のplay（`hosts: quory`）は`--limit`によって"skipping: no hosts matched"となり**quoryへ一切接続しない**ことを確認した。preflightのpositive経路とnegative経路の両方を、実ホスト非接触のまま実測した。

- **Major #2（apt cache_valid_time既定0による非冪等な再実行）**: レビューが指摘したローカルの`ansible/modules/apt.py`1404-1406行の判定ロジック（`mtimestamp + tdelta >= now`が成立しなければ`cache.update()`を実行）をそのまま複製したPythonシミュレーションで、`cache_valid_time=0`（従来値）では直前の更新からの経過時間に関わらず常に`True`（毎回cache更新）になることを再現した。`roles/quory_nvme_setup/tasks/main.yml`の`ansible.builtin.apt`タスクへ`cache_valid_time: "{{ quory_nvme_setup_cache_valid_time }}"`（新設default、既定3600秒=1時間）を追加し、同シミュレーションで直近1時間以内の再実行ではcache更新が発生しない（`False`）ことを確認した。既存の"導入から間が空いた場合は再取得する"安全網（2時間経過時は`True`）も維持されている。
  - 実quoryでのapt実行・変更は行っていない（実ホスト非接触の制約のため）。検証はレビューと同じ、ローカルにインストール済みの`ansible-core`パッケージが持つ実モジュールソースを根拠にした静的推論とシミュレーションに限定した。

### 追加・変更ファイル（差し戻し対応分、元の変更許可範囲内）

- `playbooks/quory_nvme_setup.yml`（quory存在確認のpreflight playを追加、ヘッダコメント更新）
- `roles/quory_nvme_setup/defaults/main.yml`（`quory_nvme_setup_cache_valid_time: 3600`を新設）
- `roles/quory_nvme_setup/tasks/main.yml`（aptタスクへ`cache_valid_time`を追加）

### 差し戻し後の再検証

- `ansible-playbook --syntax-check playbooks/quory_nvme_setup.yml`: rc0
- `bash scripts/check-tester-gate.sh`: OK（63 playbooks）
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `git diff --check`: rc0
- `ansible-lint playbooks/quory_nvme_setup.yml roles/quory_nvme_setup`: `Passed: 0 failure(s), 0 warning(s)`（production profile）
- `python3 -m unittest discover -s tests -p "test_*.py"`: 71/71 OK（quory_health_monthly側の既存回帰、無関係であることの確認）
- 上記のpreflight negative/positive実測（`localhost,`合成inventoryでのrc2確認、実inventory+`--limit localhost`でのpositive確認・quory非接触確認）
- apt cache_valid_timeロジックの数値シミュレーション（before/after比較）

## 再差し戻し対応（2026-09-13、017_nvme_setup_rereview.md Major #1/#2残存）

017を現物確認し、残存Major 2件を根本から作り直した。017は編集していない。

- **Major #1（対象欠落の一部経路のみ解消・実際の後段対象を確認していない）**: 016の`'quory' in hostvars`チェックは「inventoryにquoryが定義されている」ことしか確認せず、`--limit`等で後段playが実際に0台にされても検出できなかった（017の実測どおり）。**起動条件と限界を明記した2段構えへ作り直した**：
  1. 従来どおりのpreflight（`'quory' in hostvars`）はinventory定義の有無を確認する第1段として残す。
  2. インストールplay（`hosts: quory`）の最後に`set_fact: quory_nvme_setup_play_ran: true`を追加し、**このplayが実際にquoryに対して実行されたことをhostvars上に痕跡として残す**（check_mode下でも実行される、set_factは状態変更を伴わないため）。
  3. 新設のpostflight play（`hosts: localhost`）で`hostvars['quory'].quory_nvme_setup_play_ran | default(false)`をassertする。インストールplayが`--limit`・`-l`・tagフィルタ等いかなる理由であれ0台マッチだった場合、このfactが立たずrc非0で停止する。
  - **明記した限界**（fail_msgに埋め込み）: この機構が検出できるのは「playが0台マッチだった」ことのみ。quoryという名前ではない別名で到達可能なホストの取り違えや、quory自身がタスク途中で失敗するケース（これは各roleタスク自身の失敗で既にrc非0になる）は対象外。
  - 検証（decoy inventory、実host名なし・`ansible_connection: local`のみ、set_fact/assertしか使わない）: 3-play構成の縮小版を`decoyhost`という架空名で作り、(a) インストールplayのhostパターンが実際に`decoyhost`へマッチする場合はpostflightがpassすること、(b) `--limit localhost`でインストールplayが"skipping: no hosts matched"になる場合はpostflightがfail・rc非0になることの両方を実測した。
  - 実playbook（`inventories/homelab/hosts.yml`使用、`--limit localhost`）でも同じ結果を再現: インストールplayは"skipping: no hosts matched"、postflightのassertが`quory_nvme_setup_play_ran`未設定を検出してfail・rc=2。**quoryへは一切接続していない。**

- **Major #2（cache_valid_timeでは時間経過後の再実行が非冪等）**: 016の`cache_valid_time: 3600`は時間軸に依存する対症療法であり、017が指摘したとおり期限超過後は同じ問題が再発する構造だった。**時間依存を完全に廃止し、`ansible.builtin.package_facts`（read-only、`--check`でも同一）でパッケージの現在状態を確認したうえで、`update_cache`をその場で導出する設計へ作り直した**: `update_cache: "{{ quory_nvme_setup_package not in ansible_facts.packages }}"`。パッケージが既に導入済みなら`update_cache`は常に`false`となり、apt moduleはcacheチェック分岐（`if p['update_cache'] or p['cache_valid_time']:`）へ一切入らない——`cache_valid_time`という値自体が意味を持たなくなるため、経過時間に関する非冪等性が構造的に発生しない。`roles/quory_nvme_setup/defaults/main.yml`から`quory_nvme_setup_cache_valid_time`を削除した（もはや使われないため）。
  - 検証（`--check`のみ、ansy自身の実パッケージ状態を対象、状態変更なし）: `package_facts`＋条件付き`update_cache`のprobeを作成し、(a) 未導入パッケージ（`nvme-cli`、ansyには未導入）では`update_cache=true`となり`changed=true`・`cache_updated=true`（導入見込みを正しくpreview）、(b) 導入済みパッケージ（`coreutils`）では`update_cache=false`となりcacheチェック分岐へ入らず`changed=false`・`cache_updated=false`（時間経過や`cache_valid_time`の値に一切依存しない）ことを実測した。
  - 補足として、016の`cache_valid_time`修正当時に実施した`ansible.builtin.apt`のcheck-mode probe（`coreutils`、`cache_valid_time=0` vs 巨大値）では、両方とも`changed=false`だった一方`cache_updated`はそれぞれ`true`/`false`と分かれた——**`cache_updated`は`changed`へ合流しない別フィールドであることをローカルの`ansible/modules/apt.py`のコード追跡と実測の両方で確認した**。この事実そのものは016/017の懸念を否定するものではなく（`changed`に現れなくても`apt-get update`自体は実行され続ける非冪等性は残るため）、今回の`package_facts`ゲート方式で時間依存を完全に断つ判断に至った根拠として記録する。

### 追加・変更ファイル（再差し戻し対応分、元の変更許可範囲内）

- `playbooks/quory_nvme_setup.yml`（postflight playを新設、ヘッダコメント更新）
- `roles/quory_nvme_setup/defaults/main.yml`（`quory_nvme_setup_cache_valid_time`を削除）
- `roles/quory_nvme_setup/tasks/main.yml`（`package_facts`タスクを追加、`update_cache`をpackage_facts条件式へ変更、set_factタスクを追加）

### 再差し戻し後の再検証

- `ansible-playbook --syntax-check playbooks/quory_nvme_setup.yml`: rc0
- `bash scripts/check-tester-gate.sh`: OK（63 playbooks）
- `python3 scripts/check-doc-consistency.py`: check1/2/3 OK
- `git diff --check`: rc0
- `ansible-lint playbooks/quory_nvme_setup.yml roles/quory_nvme_setup`: `Passed: 0 failure(s), 0 warning(s)`（production profile）
- `python3 -m unittest discover -s tests -p "test_*.py"`: 71/71 OK（quory_health_monthly側の既存回帰、無関係であることの確認）
- 上記のdecoy inventory実測（postflightのpositive/negative両方）、実inventory+`--limit localhost`での再現、`package_facts`ゲートのcheck-mode probe実測（未導入/導入済みの両方）

## 未達AC・未解決事項（Coordinatorへ）

- **AC-S1・AC-S2・AC-S3は未検証。** 実quoryでのtemplate/setup check→apply→readback、月次ヘルスジョブ`--check`再実行はいずれもYoshinobuのSemaphore実行とTester/配備工程が必要（計画013）。
- **AC-S4のうち「schedule増えていないこと」の静的検査**はcatalog差分（新規template追加のみ、`schedules:`未変更）で確認できるが、Semaphore実機でのreadbackは別途必要。
- `nvme-cli`導入後に`nvme id-ctrl`/`nvme smart-log`が実際に成功するかは要求012のオープンクエスチョンのまま未確認。
