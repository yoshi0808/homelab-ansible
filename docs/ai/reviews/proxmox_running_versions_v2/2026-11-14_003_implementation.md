# implementation: Proxmox Watch 稼働バージョン v2

対象は`roles/proxmox_running_versions/`、`playbooks/proxmox_running_versions.yml`、`playbooks/README.md`および本案件記録である。実ホスト、Semaphore、Notion、Slackへは接続していない。Policy本文と週次patch関連ファイルは変更していない。

## 実装判断

- 対象playは`proxmox`、`control_nodes`、`radius_servers`、`monitoring_servers`の和集合とした。quoryは既存host_varsの実行元判定を再利用し、自己SSHを新設しない(Q2)。
- 5ホストの`role`はdefaultsの明示対応表を正本にした。hostnameから役割を推測しない。
- collectorはread-only commandだけを使い、apt metadataを更新しない。PVE packageのoriginは`apt-cache policy`の、installed版またはcandidate版に対応するsource行に`proxmox`が現れることから判定する。installed版がmetadataから消えていてもcandidate版がProxmox originなら含める。両方が違えば含めない。
- stale libraryは`homelab-stale-libs`と同じdeleted mappingと`/dev/`等の除外契約で収集する。systemd unitを安全に引けない場合はprocess名だけを出す。補助値の取得失敗は`unknown`で、必須のkernel/package収集失敗だけをnode `error`にする。
- apply reportの`reboot_required`は、`reboot_trigger: none`を`false`、`reboot-required-file`または`kernel-version-mismatch:`を`true`、その他・欠落を`unknown`へ変換する。週次patch roleには手を入れていない。
- Q1: Notion APIのrich text `text.content`上限(2,000文字)を越えないよう、package blockを1,900文字以内で分割する。各block先頭を`part: i/n`とする。現在のAPI children requestの100件上限を越える本文は`managed_blocks_too_many`でfail-closedにする。既存blockはheaderを`updating`にしてから更新し、余剰blockの削除を含めて成功後だけ`complete`にする。

## Policy表の文案（未反映）

SB-020の`proxmox_running_versions.yml`行を次の文面へ替える案である。Policy改訂の承認・反映はCoordinatorとYoshinobuの工程であり、本実装では編集していない。

> `proxmox_running_versions.yml` | pve1 / pve2 / quory / authy / monnie の稼働中kernel・package版、再起動待ち、直近apply補助情報のread-only収集と、固定Notionページの上書き。host変更なし。pve1/pve2両方の不達、全host不達、必須収集不能、Notion失敗は非0。 | 自動可

## 自己検証

- `python3 roles/proxmox_running_versions/tests/test_logic.py`: 10 fixture tests成功。dpkg版比較によるkernel選択、originの正負例、kernel実体除外とmeta残留、candidate表示、`part`分割と`package_count`、apply trigger、apt履歴、補助値`unknown`、partial / pve全系不達 / 全host不達、固定role、Notion 401/404の秘密非露出、更新失敗後の`updating`からの再実行回復、抑止時のtoken未読を確認した。
- `python3 -m py_compile ...`: collector、整形module、Notion moduleの構文成功。
- `ansible-playbook --syntax-check -i inventories/homelab/hosts.yml playbooks/proxmox_running_versions.yml`: 成功。
- `scripts/check-tester-gate.sh`: 63 playbook成功。
- `git diff --check`: 空。週次patch playbook・import先・`roles/proxmox_patch_apply_node`に差分がないことを確認した。
- `ansible-lint playbooks/proxmox_running_versions.yml roles/proxmox_running_versions`: 成功。role-local変数はrole prefixへ揃え、`common_slack`の定義済み入力4件だけはinclude taskの局所的なlint除外で明示した。custom module_utilsをansible-lintがimportできないというArgsRuleの警告は出るが、lint結果はproduction profileで成功した。

## 受入条件の自己評価

AC4 / AC4a / AC4b / AC5 / AC6 / AC6a / AC6b / AC7 / AC8a / AC8b / AC8c / AC9 / AC10はfixture・静的検査で確認した。AC1〜AC3は実機、実Notion、実Slackを必要とするため未実施であり、Testerへ渡す。

未解決事項は、実Notionのページ共有権限・実block数上限までの稼働時挙動、実host上のorigin出力とQEMU process照合、実Slack captureを含む配備後検証である。

## 差分査読 2026-11-14_004 の差し戻し対応

前節の「AC4 / AC6 / AC8 をfixture・静的検査で確認」の記述は過大だった。apply reportとapt historyのfixtureが実物の書式ではなく、QEMUは未実装で、report taskを通したrc・通知検査も無かったため、当該の達成記述を撤回する。

- apply reportの`run_timestamp`はpatch roleの実値`YYYYMMDDTHHMMSS`(JST)を受理し、ページでは`+09:00`付きISO 8601に変換する。apt historyは実書式`Upgrade: package:arch (旧, 新)`を`旧->新`へ整形し、`history.log.1.gz`相当と`history.log`相当の両方をfixtureで連結して検査する。
- `vms_on_old_qemu`は`qm list`のrunning VMと`ps`の`-id VMID`を照合し、各QEMU executableのdpkg版を`pve-qemu-kvm` installed版とDebian版比較する。process欠落・所有package解決失敗は補助値`unknown`に倒す。
- node blockも1,900文字以内へ収める。長いservices/apply upgradeは`(+N more)`で縮め、servicesの先頭へ`count=N;`を置いて継続行を判別可能にした。
- role内local fixture playは実接続なしでproductionの`report.yml`を通す。partial、pve両系不達、全不達のrc・本文status・fake Slack 1通、および`--check`/`skip_notifications`/`CLAUDECODE`の3抑止経路で本文出力・token未読を検査する。

Minor #1(Ubuntuのkernel実体混入)は既知meta packageのallowlistへ限定して対応した。#2(Ubuntuの`corosync`混入)は固定一覧から除いた。#3(repoの部分一致)はPVE apt source行とsuite名の一致だけで判定するよう修正した。#4は全生成時刻を`+09:00`の拡張ISO形式へ揃えて対応した。#5(stale-libsの複製)は対象host上で既存scriptが配備される保証が無く、同じ観測契約をcollector内に置く必要があるため本件では維持する。Suggestionの複数行値には`count=N;`を加え、継続行であることを明示した。

差し戻し後のfixture testは16件成功した。AC4 / AC4a / AC4b / AC5 / AC6 / AC6a / AC6b / AC7 / AC8a / AC8c / AC9 / AC10は、実物書式fixtureまたはlocal fakeで再確認した。AC8bはfake 401/404でHTTP静的エラー化とtoken非露出を確認したが、report.ymlまで通したfake API失敗の通知captureは未確認である。AC1〜AC3は引き続きTesterの実機確認が必要である。

## 差分再査読のN1対応

前節の`vms_on_old_qemu`は、QEMU executableの所有package版と現行`pve-qemu-kvm`版を比べる方式だった。しかし更新後も旧binaryを保持するプロセスでは`/proc/<pid>/exe`が` (deleted)`となり、dpkg所有照合ができない。一方、生きたpathを照合しても常に現行packageになるため、どちらも「古いQEMU」を検出する根拠にならない。前節の版比較による達成記述は撤回する。

R3の追記どおり、`qm list`のrunning VMと`ps`の`-id VMID`を対応させ、各`/proc/<pid>/exe`の参照先が` (deleted)`かで判定する方式へ替えた。deletedのVM 2台、現行pathのVM、process不足、QEMU観測失敗時の`unknown`と、観測失敗が`pve_manager`/`repo`を`unknown`へ巻き込まないことをfixtureで確認した。

再査読Minorの`node_block_too_large`は対応した。render時の`ValueError`をmoduleが`render_invalid`という静的エラーとして`fail_json`し、未捕捉tracebackを出さない。AC8bは、productionの`report.yml`をimportするlocal fake roleとfake Notion moduleで401/404を注入し、両方でrc非0、fake Slack通知1通、`reason=http_401`/`http_404`、token path非露出を確認した。fakeはrole library解決だけを差し替え、実ホスト・Notion・Slackへ接続しない。

最終fixture testは19件成功した。AC4 / AC4a / AC4b / AC5 / AC6 / AC6a / AC6b / AC7 / AC8a / AC8b / AC8c / AC9 / AC10をlocal fixtureまたは静的検査で確認した。AC1〜AC3は実機・実Notion・実Slackを要するため、引き続きTesterの確認対象である。

## 差分再査読2のR1対応

前節の19件成功だけでは、v2が変更していないv1のNotion公開保護を検査できていなかった。`test_logic.py`に、pve1の40 package行を分割して生成するv2 fixtureを追加し、header・5 node block・分割後のpackage blockからなる管理block列を`render_blocks`の実出力で検査する形で、次の5件を復元した。

- 空のNotion paragraph placeholderを削除し、v2の全管理code blockをappendする。block数、headerの`complete`、すべてのappendが`retry=False`であることを確認する。
- 最初のappendがサーバ側で成功した後に応答だけ失われた場合、appendをretryせず失敗にし、次回実行で既存headerを使って残りだけをappendする。最終block数とappend回数がv2の期待block数と一致し、重複しないことを確認する。
- 文字を持つparagraph、およびchildrenを持つ空paragraphを、管理placeholderと誤認して削除しない。どちらも`managed_blocks_invalid`で停止し、API呼び出しが0回であることを確認する。
- 同一lock directoryで二重にpublisherを起動すると`publication_busy`で拒否する。

これらはそれぞれplaceholder判定、appendの`retry=False`、既存blockの再利用、人間が書いたparagraphの拒否、non-blocking lockを外すと失敗するfixtureである。`python3 roles/proxmox_running_versions/tests/test_logic.py`は24件成功した。

再査読2 Minorの`running_qemu_executables`については、ansy上の実`/proc`・QEMUプロセスをfixtureとして仮定しない。`qm list` / `ps` / readlink結果の対応と` (deleted)`判定は純関数fixtureで検査済みだが、実プロセスの観測値と権限は実PVEに依存するため、実機確認はTesterに残す。実ホストへの接続を伴う追加検査は行っていない。

## 差分再査読3のT1対応

v1の`test_unreachable_and_error_have_unknown_versions`に相当する検査が欠けていたため、`normalize`のnode異常分岐をfixtureで直接検査した。`ok: false`、必須`kernel_installed`の欠落、`kernel_reboot_required`の不正値、`collected_at`の非ISO値、パッケージ選別結果0件の5形態について、pve1が`status: error`、全体が`error`かつ`execution_error: true`、固定node keyの値が`unknown`、`package_count: 0`、roleが維持されることを確認した。これにより必須値の失敗を補助値の`unknown`扱いへ緩めると失敗する。

同じfixtureでauthyを`unreachable`にし、全体が`partial`・rc 0のまま、authyの固定node keyが`unknown`、`package_count: 0`、roleが`radius`のまま保持されることを確認した。さらに`report_fixture.yml`へauthyの`kernel_reboot_required: invalid`を注入する`required_error`ケースを追加し、productionの`report.yml`経由でheader `status: error`、rc非0、fake Slack通知1通、error node本文の`kernel_running: unknown`と`package_count: 0`を確認した。

`python3 roles/proxmox_running_versions/tests/test_logic.py`は25件成功した。実ホスト、Notion、Slack、Semaphoreへの接続は行っていない。
