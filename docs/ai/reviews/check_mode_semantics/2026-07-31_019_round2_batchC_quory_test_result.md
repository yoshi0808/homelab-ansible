# test_result: Round 2 バッチC — quory checkoutからの実物検証(AC1・AC3のみ)

日付: 2026-07-31
requirement: `docs/ai/reviews/check_mode_semantics/2026-07-31_006_round2_requirement.md` §6 AC1・AC3
前回記録: `docs/ai/reviews/check_mode_semantics/2026-07-31_018_round2_batchC_test_result.md`(ansyから実物へ到達できなかった記録。本ファイルはその続き・上書きではない)
対象: `playbooks/cert_renew.yml`、`playbooks/codex_update_check.yml` のみ。AC2/AC4/AC5はやり直していない。

## 実行環境

- 起動元: quory(`ssh quory` → OS identity `ann`)。作業ツリー `/home/yoshi/homelab-ansible`(owner: yoshi)。
- 事前確認: `.git/HEAD` → `ref: refs/heads/main`、`.git/refs/heads/main` → `ff77b5b49ce768aa5129402f62fde6a3df105c1d`。ローカル(ansy)の`git log -1`と一致。`git`コマンド自体はdubious ownershipで拒否されるため、`.git`配下のrefファイルを直接読んで確認した(`git config --global --add safe.directory`は行っていない)。
- 両playbookの`# tester-gate:`を確認し、いずれも`check-mode-native`であることを直接ファイル読み取りで確認した。

## 新たに判明した構造的制約(依頼文にあった前提の続き)

依頼文は「vault_password_fileは起動ユーザーのHOME配下を指す」ことと「gitがdubious ownershipで拒否される」ことを既知情報として渡していた。実行してみると、**同じ「HOME相対パス」構造に起因する制約がもう1段あった。**

1. **vault_password_file**: `ansible.cfg`の`vault_password_file = ~/.ansible/vault/homelab_vault_pass`は`ann`のHOME(`/home/ann`)相対に解決され、該当ファイルは存在しない(`yoshi`のHOME側にのみ存在する)。このため`--syntax-check`すら起動できなかった。**リポジトリ内に vault 暗号化コンテンツは1件も存在しない**(`grep -rn "!vault"` / `ANSIBLE_VAULT` がリポジトリ全体でヒットなしを確認済み)ため、実際に復号すべき秘密は無い。起動を通すためだけに、実際のパスフレーズとは無関係な**捨て文字列**(`dummy-unused-because-no-vault-content-in-repo`)を1行書いたファイルを`--vault-password-file`でCLI指定した。このファイルは`/tmp`(quory、作業ツリー外)に作成し、各実行後に削除した。実在の秘密は一度も読んでいない。
2. **SSH到達性(新規判明)**: `ansy` / `proxmox` / `monnie` グループの`ansible_ssh_private_key_file: ~/.ssh/id_ann`も同様にHOME相対で、`yoshi`が起動したときの`~/.ssh/id_ann`(yoshiの鍵)を指す設計になっている。`ann`のHOME(`/home/ann/.ssh/`)には`authorized_keys`しかなく、対象ホストへの秘密鍵も`known_hosts`エントリも無い。実測: `ansy` / `pve2` / `monnie` はいずれも最初のリモートtaskで`Host key verification failed`によりUNREACHABLE、`pve1`は`No route to host`(こちらは承認済み前提どおり停止中と一致)。**`ann`識別子ではこの4ホストへ一切接続できない。**
   - `yoshi`の鍵・`known_hosts`を読む/コピーする、対象ホストの`authorized_keys`を変更する、`sudo`で`yoshi`に成り代わって実行する、のいずれも行っていない(鍵の複製・identity昇格は行わない/2026-07-28に記録されたscope creepの再発になるため)。`ann`はpasswordless sudoを持つが、**使用したのはCA証明書ファイルの読み取り専用stat/sha256sumのみ**(後述、playbook自身が`become: true`で行うのと同じ権限)。identityを`yoshi`へ昇格して`ansible-playbook`を実行することはしていない。
3. **UNREACHABLEが実行全体を止める**: このAnsible環境(ansible-core 2.20.1)では、**あるホストがUNREACHABLEになると、そのタスクが属するplayだけでなく、以降の残りplay全てが実行されずに停止する**ことを3通りの実行で確認した(全inventory実行→`ansy`で停止/`ansy`を`--limit`除外→`pve1`で停止/`pve1`も除外→`pve2`で停止、`monnie`のplayヘッダにすら到達しない)。前回記録(`_018_`)が「play1の失敗が以降を止める」と記録した現象は、play1固有ではなく**UNREACHABLE全般に及ぶより一般的な性質**だったとわかった。このため、各playを個別に実物検証するには、未到達ホストを`--limit`で1つずつ除外する必要があった。

## AC1(`--check`で完走・破壊的taskがskippedに現れる)

### `codex_update_check.yml` — `--limit "localhost,quory"`(`ansy`を除外)

```
$ scripts/safe-ansible-check.sh playbooks/codex_update_check.yml -i inventories/homelab/hosts.yml \
    --vault-password-file /tmp/dummy_vault_pass --check --diff --limit "localhost,quory"
...
TASK [codex_update_check : Update Codex CLI to the latest version] ...... skipping: [quory]
TASK [codex_update_check : Update npm itself to the latest major version] skipping: [quory]
PLAY RECAP
localhost : ok=3  changed=0 unreachable=0 failed=0 skipped=0
quory     : ok=21 changed=0 unreachable=0 failed=0 skipped=4
RC=0
```

**合格**(quoryを対象とする実物のplaybook・実物のrole・実際の本番quoryホストで、終了コード0・破壊的task 2件がskippedであることを確認)。npm registryへの実クエリの結果、quoryは実際に`codex: current=0.145.0, latest=0.146.0, status=would_update`・`npm: current=12.0.0, latest=12.0.2, status=minor_patch_skip`という「更新が必要な状態」を本物として踏んだ(合成データではない)。

参考: `ansy`を含むフルinventoryで実行すると`ansy`がUNREACHABLE(上記SSH制約)になり、後続の`Fail if any host failed collection or update`タスク(`roles/codex_update_check/tasks/main.yml:304`、`when: codex_update_check_all_failed_hosts | length > 0`)が発火してRC=4になる。この`when`条件は`ansible_check_mode`を一切参照しておらず、**本バッチの差分とは無関係の既存ロジック**(ホスト収集失敗時は`--check`でも通常実行でも同じくfailする設計)であることをファイルを読んで確認した。check-mode-native変換の欠陥ではない。

### `cert_renew.yml` — `--limit "localhost,quory"`(`ansy`/`proxmox`/`monnie`を除外)

```
$ scripts/safe-ansible-check.sh playbooks/cert_renew.yml -i inventories/homelab/hosts.yml \
    --vault-password-file /tmp/dummy_vault_pass --check --diff --limit "localhost,quory"
...
(prepare_ca_check: Stat CA certificate source / Stat CA private key source / Check intermediate CA certificate days remaining — すべて ok)
TASK [homelab_cert_renew : Create CA staging directories on tmpfs] ...... skipping: [quory] (x3 items含む)
TASK [homelab_cert_renew : Copy CA certificate to tmpfs] ................ skipping: [quory]
TASK [homelab_cert_renew : Copy CA private key to tmpfs] ................ skipping: [quory]
...
TASK [[tester_mode] Show notification instead of sending] ... ok: [localhost] =>
  "message : ... ansy: check FAILED\npve1: check FAILED\npve2: check FAILED\nmonnie: check FAILED\nCA cleanup: not applicable (check-mode preview)\n"
PLAY RECAP
localhost : ok=11 changed=0 unreachable=0 failed=0 skipped=9
quory     : ok=3  changed=0 unreachable=0 failed=0 skipped=8
RC=0
```

**合格**(guard play・quoryのprepare_ca play・cleanup play・notify playの4つについて、実物のplaybook・実物のrole・実物のquoryホスト・yoshiの実CAファイル(`/home/yoshi/.cert/ca/home_tls_ca.{crt,key}`、`become: true`経由で読み取り)で、終了コード0・破壊的task 3件がskippedであることを確認)。notifyの分岐も、check-mode preview("[tester_mode] 通知スキップ")が正しく選ばれ、Slackへは送信されなかった。summary中の`ansy/pve1/pve2/monnie: check FAILED`は、これらを`--limit`で除外した結果であり、check-mode-native変換の不具合ではない。

### `cert_renew.yml` の `ansy` / `proxmox` / `monnie` play — **未検証(接続不能)**

`--limit`で1ホストずつ切り分けて実行した結果、いずれも最初のリモートtask(`Check cert file exists on remote host`)で接続に失敗し、それ以降の一切のtask(diagnostic・destructiveいずれも)が実行されていない。

| host | 結果 |
|---|---|
| `ansy` | `Host key verification failed`(UNREACHABLE) |
| `pve1` | `No route to host`(UNREACHABLE、承認済み前提どおり停止中の可能性と一致) |
| `pve2` | `Host key verification failed`(UNREACHABLE) |
| `monnie` | `Host key verification failed`(UNREACHABLE) |

これら4 playについては、**AC1の「終了コード0・destructiveがskipped」を観測すること自体ができていない**(接続不能のため、そもそもcheck-mode分岐に到達していない)。前回(`_018_`)の「実物に一度も到達できない」状態から、guard・quory・cleanup・notifyの4 playへは前進したが、issue/deploy系3 playは今回も実物では検証できていない。

## AC3(`--check`前後でホスト状態が変化していない)

- `/run/semaphore-ca`(prepare_ca_applyが作成するtmpfsステージング領域): 全実行後も**存在しない**ことを確認(作成された形跡なし)。
- CA証明書/秘密鍵の実ファイル(`sudo stat` / `sudo sha256sum`、playbook自身の`become: true`と同じ権限での読み取りのみ):
  ```
  home_tls_ca.crt  mtime=2026-06-12 17:12:00  size=769  mode=644  sha256=6c807c...ee2979
  home_tls_ca.key  mtime=2026-06-12 17:12:00  size=359  mode=600
  ```
  mtimeが本セッション開始日(2026-07-31)より遥かに前であり、今回の一連の`--check`実行で一切書き換えられていないことを確認した。
- `codex_update_check.yml`: quory上の`npm ls -g --depth=0` / `npm --version`は `@openai/codex@0.145.0` / `npm@12.0.0` のまま不変(実行前後で比較し、かつ前回バッチ(`_018_`)が独立に記録した値とも一致)。
- `ansy` / `pve1` / `pve2` / `monnie`: いずれも最初のリモートtaskで接続自体が失敗しているため、モジュールが一度も実行されていない。状態変化の余地がそもそも無い(自明にAC3を満たす)。

**AC3は合格**(到達できたホスト・到達できなかったホストのいずれについても、変更が生じていないことを確認した)。

## 後片付け

- `/tmp/dummy_vault_pass`、`/tmp/ansible-remote-ann`、`/tmp/ansible-local-ann` は各実行後に削除し、quory上に残っていないことを確認した。
- quoryの作業ツリー(`/home/yoshi/homelab-ansible`)へは読み取り操作のみを行い、ファイルの追加・編集は行っていない。`git add` / `git commit` / `git push` は行っていない。
- ローカル(ansy、このTesterセッションの作業ツリー)側`git status`もクリーン(本作業による変更なし)。

## 未実施項目とその理由

- **`cert_renew.yml`の`ansy` / `proxmox`(pve1・pve2) / `monnie` の各play**: `ann`識別子がこれらのホストへSSH接続する手段(秘密鍵・known_hosts)を持たないため、接続不能のまま。`yoshi`の鍵を読む、対象ホストの`authorized_keys`を変更する、`sudo`で`yoshi`に成り代わるのいずれも行っていない(identity昇格・鍵複製は既知のscope creepパターンのため回避した)。
- **`codex_update_check.yml`の`ansy`側**: 同じSSH制約により未検証。`quory`側のみ実物検証できた。
- **pve1の実挙動**: 停止中(`No route to host`)のため未確認。承認済み前提どおりの観測として記録するのみ。

## 残存リスク

1. **`cert_renew.yml`のissue/deploy系3 play(ansy/proxmox/monnie)は、今回も実物のend-to-end検証ができていない。** 前回(`_018_`)はplay1のquory起動ガードで止まり全plays未到達だったが、今回はガードとquory・cleanup・notifyの4 playへは実物で到達できた。残る3 playを実物検証するには、(a) `yoshi`識別子での実行(Testerの権限外、identity昇格になる)、または(b) Coordinator/Yoshinobuが承認した形でSemaphore経由の`--check`ジョブを走らせる、のいずれかが必要。
2. **codex_update_check.ymlのansy側も同じ理由で未検証。**
3. **pve1稼働時の実挙動は今回も未確認**(承認済み前提どおり)。
4. **vault_password_fileのCLI上書きに使った捨て文字列ファイルは、この検証セッション専用の一時ファイルであり、リポジトリにもquoryの永続領域にも残っていない。** 今後同種の検証を行う場合、同じ回避が毎回必要になる(vault機構自体の設計課題であり、本バッチのスコープ外)。
5. **`ann`のpasswordless sudoは今回CA証明書ファイルの読み取り専用確認にのみ使用した。** この特権の存在自体は本タスクで新たに気づいた事実であり、Coordinatorが把握しておくべき環境情報として記録する(本タスクでは読み取り以外に使用していない)。

以上、AC1は**guard・quory(prepare_ca)・cleanup・notifyの4 play(cert_renew.yml)および localhost+quory(codex_update_check.yml)について合格**、ansy/proxmox/monnie側の各playは接続不能のため未検証。AC3は到達できた範囲・できなかった範囲のいずれについても合格(状態変化なし)。AC2/AC4/AC5はやり直していない。

---

## Coordinatorによる検算(2026-07-31)— 副次的所見の訂正

本ファイルは「ansible-core 2.20.1 では UNREACHABLE ホストが1台でもあると**残りのplaybook実行全体が中断する**」と一般化しているが、**この一般化は広すぎる。**

`proxmox_readonly_check_single_node`(2026-07-30)は、pve1停止中に read-only 点検3本が **rc=0・他ホスト継続** で完走することを確認している。両者は矛盾するため、Coordinatorが実測して切り分けた(`hosts: localhost` + 実在ホストの2 play構成、scratchpadで実行後に削除)。

| 構成 | 結果 |
|---|---|
| play1 が **pve1のみ**(そのplayの全ホストが到達不能になる) | play2 は**実行されない**。Ansible標準の "NO MORE HOSTS LEFT" による run 全体の中断 |
| play1 が **proxmox グループ**(pve1が到達不能、pve2は到達可能) | play2 は**実行される**。`rc=4`(`RUN_UNREACHABLE_HOSTS`)、pve2 のtaskは正常完了 |

**正しい記述**: 中断の条件は「UNREACHABLEが1台でもあること」ではなく、**「あるplayの対象ホストが全て失われること」**である。1台でも残れば run は継続し、終了コードだけが 4 になる。

`cert_renew.yml` の `--limit localhost,quory` 実行で後続playへ進めなかったのは、`--limit` によって当該playの対象ホストが空または全滅したためであり、UNREACHABLE の一般的性質ではない。**この区別は、pve1停止運用下でどのplaybookが動き続けるかの判断に直接効く**ため、一般化した形で記録に残さない。
