# Implementation: dispatch host-state vocabulary

実装日: 2026-11-14

## 変更

- class Qの`recovery-investigate-dispatch-quory.sh`へ、sudoなしの`kernel-status`と`kmod-list`を追加した。`stale-libs`は追加していない。
- class G/Pのdispatchへ`kernel-status`、`kmod-list`、`stale-libs`を追加し、class Pだけへ既存Q/Gと同一の`ports` (`ss -ltnup`)を追加した。
- `roles/recovery_exec/files/homelab-stale-libs`を追加した。Python標準ライブラリだけで`/proc/*/maps`を読み、PID・`comm`・重複除外した対象pathを出す。引数があれば走査前に無出力・rc 64で終了する。
- G/Pではroot所有`0755`で同スクリプトをcopy配備し、sudoersに絶対pathと空引数指定`""`だけの許可を1行ずつ追加した。`target_setup.yml`は配備後、target上で`recovery-exec`として引数付きsudoを実行し、rc 0/64以外（sudo層での拒否）をassertする。
- copy配備物を`deployment_drift_check`のTier 1カタログへ追加し、語彙カタログへ§11と更新後総数を追加した。

## 実装判断

- `kernel-status`は`nullglob`で`/boot/vmlinuz-*`を列挙する。0件、または`/boot`を読めずglobが展開できない場合は非ゼロにする。観測対象は**イメージのファイル名**であり、各イメージ内容のread権限ではない。ansyのUbuntuではイメージ本体が通常ユーザーに非readableだったため、個別`-r`を要件とするとQ/GのAC2を誤って失敗させる。このため、列挙できた名前はそのまま出す。
- `reboot-required.pkgs`は再起動要求がある場合にだけ読み、存在するが読めない場合は判定不能として非ゼロにする。
- `stale-libs`のmaps行は`split(maxsplit=5)`で第6欄以降を一つの文字列に保つ。` (deleted)`を外したpathが`/`始まりで、指定された除外prefixに当たらないものだけを採用する。追加の除外prefixは設けていない。
- PID列挙後に`comm`または`maps`が読めなくなった`OSError`は、そのPIDだけをスキップする。`/proc`自体を列挙できない場合は全体を非ゼロにして、空の成功にしない。
- sudo拒否assertはrootで実行したAnsible taskから`sudo -n -u recovery-exec sudo -n <script> x`をargv形式で起動する。スクリプト到達時の専用rc 64と成功rc 0をどちらも不合格とするため、引数がsudoで拒否されたことを配備時に検査できる。

## 配備経路

- Q: `playbooks/dev_investigate_setup.yml` → `roles/dev_investigate/tasks/main.yml`の`Deploy investigate dispatch script` copy task。
- G/P: `playbooks/recovery_exec_setup.yml` → `roles/recovery_exec/tasks/main.yml`のquory限定`target_setup.yml` include → `target_setup.yml`のdispatch template、`homelab-stale-libs` copy、sudoers template、拒否assert task。Pは既存のTCP probeで到達可能と判定されたnodeだけへ配備され、実行ログの「外したpveホスト」が`(なし)`であることが配備完了条件。

## 自己検証（ansyローカルのみ）

- `bash -n`をQ dispatch・P dispatch・ローカル描画したG dispatchへ実行し、成功した。G templateはfixtureの`target_item`でAnsible template描画してJinja構文も通した。
- Q/G/Pの`kernel-status`と`kmod-list`を引数なしで実行し、いずれもrc 0。ansyの観測値は稼働カーネル`7.0.0-38-generic`、`kmod-list`先頭は`algif_hash`だった。Pの`ports`もrc 0だった（ansyでは他ユーザーのプロセス名を読めずnetlink警告を出しうる）。
- Q/G/Pの`kernel-status x`・`kmod-list x`、G/Pの`stale-libs x`、Pの`ports x`はいずれも非ゼロかつ`denied:`で拒否された。Qの`stale-libs`もunknown commandとして非ゼロ・`denied:`で拒否された。
- `stale-libs`のfixtureとして、workspace配下の空白を含む名前の通常ファイルをmmap後にunlinkしたPythonプロセスと、`memfd` mappingを作った。同スクリプトは前者を`pid=<pid> process=python3 path=<空白を含む全path>`として出し、`/memfd:`を出さなかった。引数ありは無出力・rc 64だった。短命プロセス50本を並行終了させた走査もrc 0で完走し、fixture終了後の20回連続走査もrc 0だった。
- 既存drift probeの`totally-unknown-operation-xyz`と`operator-request-submit extra-unexpected-argument`は、Q dispatchで従来どおり非ゼロ・`denied:`だった。
- G/P sudoers templateをローカル描画し、各classで`homelab-stale-libs ""`の許可行が1本だけ、かつワイルドカードなしであることを確認した。ansyはsudo-rsでありclassic sudoの引数wildcard/空引数挙動の検証対象ではないため、`visudo`は実行していない。
- `ansible-playbook --syntax-check`を`dev_investigate_setup.yml`、`recovery_exec_setup.yml`、`deployment_drift_check.yml`へ実行し成功した。`git diff --check`と`python3 -m py_compile roles/recovery_exec/files/homelab-stale-libs`も成功した。
- `ansible-lint`は既存の`target_setup.yml:24,32,40,48,56`のrole-prefix命名違反5件で失敗した。今回追加したtask・catalogにはlint findingが出ていない。playbookを入口にしたlintも同じ既存違反を含む106件で失敗した。
- 一度、fixture cleanupに`rm -f`を含めた検証コマンドは安全機構により**実行前**に拒否された。削除を伴わない設計（childがunlinkし、空ディレクトリだけを`rmdir`）へ変更して上記の検証を完了した。

## 未確認・未解決

- 実ホストには接続・Ansible実行していない。AC1〜AC5の各ホスト実測、AC8aのclassic sudo拒否assert、PVEでの除外hostなし、AC9の日次driftが全host `checked`、配備後のdispatch実行は未確認であり、Tester/配備工程で確認する。
- ansyのローカル実行ではsandboxの`no new privileges`により`sudo -n`が拒否されるため、G/Pの`stale-libs` dispatchがsudoを通ってスクリプトを実行する成功経路は未確認である。これは上記のtarget配備時assertと実ホスト検証の対象である。

## 差し戻し対応（2026-11-14 diff review M1 / Minor）

- **M1を修正した。** G/Pそれぞれで引数なしの`sudo -n /usr/local/sbin/homelab-stale-libs`を、target上の`recovery-exec` identityとして先に実行し、rc 0をassertするtaskを追加した。既存の引数付きprobeはその後に実行し、引き続きrc 0とスクリプト到達を示すrc 64を不合格とする。従来記録した「負のprobeだけでsudo層を証明できる」という判断は誤りであり、この正の対照で置き換えた。

  - sudoers未適用・記述ミス・`recovery-exec`不在・外側sudo失敗・スクリプト未配置は、引数なしrcが0にならず正のassertで停止する。
  - 引数付き実行がsudoersを通ってスクリプトへ到達する（空引数制約が効かない）場合はrc 64となり負のassertで停止する。引数付きが成功した場合も同じく停止する。
  - したがって、両assertを通るのは「引数なしはsudo経由で正常完走し、引数付きはスクリプトへ到達せずに拒否される」場合だけである。

- ansyローカルの副作用なしAnsible playで、上の判定式を5ケース（正しい空引数rule、sudoers/外側sudo失敗、スクリプト未配置、引数がscriptへ到達してrc 64、引数付き成功）に当てた。正しいruleだけを合格、ほか4件を不合格に分類することを確認した。実際のclassic sudo挙動は引き続きAC8aの配備時検証対象である。

- Minor m1（`kernel_status`の3箇所複製）は対応しない。dispatchはclassごとに単独配備され、既存の`pkg_list`と同じ構造であるため、この差し戻しで共通helperを導入すると配備物・権限境界を広げる。将来の変更時は3箇所を同時に更新する。
- Minor m2（非UTF-8 path出力）は対応した。`emit()`を追加し、stdoutへUTF-8 + `backslashreplace`で書くようにした。surrogateを直接渡したテストで`UnicodeEncodeError`なく`\\udcff`へエスケープされること、削除済みの非UTF-8 filename mapping fixtureでrc 0になることを確認した。
- Minor m3（repo上のmode）は対応しない。配備taskがroot:root・`0755`を明示しており、repo checkout時のmodeは配備物の権限を決めない。
- Suggestion（`uname -r`を`/boot`検査より先に出す）は対応しない。`kernel-status`は3点を揃えて返すか、判定不能として非ゼロにする契約であり、部分出力を成功相当の観測値と誤読させない現在の順序を維持する。

追加検証後も`ansible-playbook --syntax-check playbooks/recovery_exec_setup.yml`、`python3 -m py_compile`、`git diff --check`は成功した。`ansible-lint --offline roles/recovery_exec/tasks/target_setup.yml`は従来どおり既存の5件（24/32/40/48/56行のrole-prefix命名）だけで失敗し、今回のtaskにはfindingがない。
