# test_result: Phase 4 — 鍵の削除(AC11 / AC12 / AC13 / AC16)

日付: 2026-08-03 (JST)
実施: Tester
対象: `2026-08-02_001_requirement.md` §9 AC11 / AC12 / AC13 / AC16、`2026-08-03_015_plan_phase4.md` §5
実施環境: ansy(`/home/yoshi/homelab-ansible`)。すべて状態を変えない確認(`id` / 各種readチェック)のみ実行。書込・再起動・patchは一切行っていない。

## 0. 判定一覧

**この表は再判定後の最終値。経緯(初回判定→解消後の再判定)は0.1節に残す。**

| AC | 判定 | 一言 |
|---|---|---|
| AC11 | **PASS** | `ann` 認証は成立せず、専用鍵は接続可・コマンド拒否(要求どおり)。`id_ansible` によるpve1/pve2への root到達は解消を実測。書込に到達する経路は現時点で確認できていない |
| AC12 | **判定保留**(変更なし) | Semaphore起動はYoshinobuの操作。今回未実施。何を確認すればPASSかを2節に記載 |
| AC13 | **PASS** | `.claude/settings.json` と `docs/ai/roles/coordinator.md` の「ansyは認証情報を1つも持たない」という記述が、再実測(5鍵×4ホスト×root/ann)と一致することを確認 |
| AC16 | **判定保留**(変更なし) | 同上。Semaphore起動が必要 |

付随確認: monnieは意図どおり全権残置(PASS)。class Qの24チェックは全通過(PASS)。

### 0.1 経緯(初回判定→再判定)

| 時点 | AC11 | AC13 | 根拠 |
|---|---|---|---|
| 初回(本ファイル §1〜8、削除前) | 条件付きPASS(重大な残存リスクあり) | FAIL | `id_ansible` 鍵がforced commandなしでpve1/pve2へroot到達を保持していることを実測(1.3節)。詳細は`2026-08-03_024_finding_unenumerated_credential.md` |
| 対処 | — | — | ansy側 `id_ansible`/`.pub` をCoordinatorが削除。pveの`root`の`authorized_keys`(`/etc/pve/priv/`配下、pmxcfsでクラスタ共有)から該当行をYoshinobuが削除(pve1で実施、pve2にも伝播) |
| 再判定(本節、9節) | **PASS** | **PASS** | 9節の再掃引で到達ゼロを確認 |

**§1〜8は初回検証の記録としてそのまま残す(削除・書き換えしない)。最新の判定根拠は9節。**

---

## 1. AC11 — `ann` 認証不成立、専用鍵は接続可・コマンド拒否

### 1.1 `ann` としての認証

`~/.ssh/id_ann`(公開鍵コメント `ann@homelab-ansible`)を明示指定し、4保護対象ホストへ接続を試みた。

```
ssh -i ~/.ssh/id_ann -o IdentitiesOnly=yes ann@pve1.internal 'id'   → Permission denied (publickey)  rc=255
ssh -i ~/.ssh/id_ann -o IdentitiesOnly=yes ann@pve2.internal 'id'   → Permission denied (publickey)  rc=255
ssh -i ~/.ssh/id_ann -o IdentitiesOnly=yes ann@authy.internal 'id'  → Permission denied (publickey)  rc=255
ssh -i ~/.ssh/id_ann -o IdentitiesOnly=yes ann@quory.internal 'id'  → Permission denied (publickey)  rc=255
```

4ホストとも認証段階で拒否。**実測PASS**(公開鍵がauthorized_keysから削除されている状態と一致)。

`~/.ssh/config` にも `Host pve1` / `pve2` / `authy` / `quory` の `ann` 経由エントリは存在しない(削除済み、`config` 冒頭コメントで確認)。`ssh pve2 'id'`(Hostエントリなしの生ホスト名)は `Host key verification failed`(rc=255)で、これも到達しない側の結果。

### 1.2 専用鍵(`*-investigate`)は接続可、コマンドは拒否・非ゼロ終了

`~/.ssh/config` の4エントリ(`pve1-investigate` / `pve2-investigate` / `authy-investigate` / `quory-investigate`)を使い、許可リストに無い任意コマンド `id` を送った。

```
ssh pve1-investigate 'id'   → denied: unknown command 'id'   rc=1
ssh pve2-investigate 'id'   → denied: unknown command 'id'   rc=1
ssh authy-investigate 'id'  → denied: unknown command 'id'   rc=1
ssh quory-investigate 'id'  → denied: unknown command 'id'   rc=1
```

4ホストともSSH認証は成立(forced commandが起動している)、`SSH_ORIGINAL_COMMAND` が許可リストに無いため `denied:` を出し非ゼロ終了。シェルは得られない。**実測PASS**。

念のため、許可リスト内のコマンドが正常に通ることも確認した(exit codeはパイプを介さず変数へ捕捉して測定)。

```
ssh pve2-investigate 'cluster-status'  → rc=0、quorate=1 を含むJSON
ssh quory-investigate 'bundle-list'    → rc=0、55行(バンドル一覧)
```

dispatchは壊れておらず正常に機能している。

### 1.3 【初回検証時点のfinding。9節で解消を確認済み】`id_ansible` 鍵が pve1 / pve2 へ root到達を保持していた

到達してはいけない状態の確認項目「dispatch以外の入口がansyに残っていないか」を洗うため、`~/.ssh/` 配下の他の鍵(`id_ansible`、コメント `ansy-to-proxmox`。指紋 `SHA256:CZ0qSZip4R6mNdspY2wcVagDhO8T05GpjT3L6V1ETi0`)を対象ホストへ試した。

```
ssh -i ~/.ssh/id_ansible -o IdentitiesOnly=yes root@pve1.internal 'id'  → uid=0(root) gid=0(root) groups=0(root)  rc=0
ssh -i ~/.ssh/id_ansible -o IdentitiesOnly=yes root@pve2.internal 'id'  → uid=0(root) gid=0(root) groups=0(root)  rc=0
ssh -i ~/.ssh/id_ansible -o IdentitiesOnly=yes root@authy.internal 'id' → Permission denied (publickey)  rc=255
ssh -i ~/.ssh/id_ansible -o IdentitiesOnly=yes root@quory.internal 'id' → Permission denied (publickey)  rc=255
ssh -i ~/.ssh/id_ansible -o IdentitiesOnly=yes ann@{4ホスト}'id'        → 全てPermission denied
```

**pve1 / pve2 へ `root` として、forced commandなしの通常シェルで到達できる。** 実行したのは `id` のみ(状態を変えない確認)で、これ以上の探索・操作は行っていない。

- この鍵はrepo内のどのgroup_vars/inventoryからも参照されていない(`grep -rln "id_ansible\|ansy-to-proxmox"` はrepo内0件)。Ansibleの接続には使われておらず、`proxmox.yml` の `ansible_ssh_private_key_file` は `id_ann` を指す。
- **Phase 4の作業はこの鍵に一切触れていない**(requirement/planのF1〜F6、Step5のいずれにも登場しない)。`ann@homelab-ansible` の削除だけでは境界が閉じないことの実例である。
- pve1/pve2の `root` の `authorized_keys` にこのエントリがいつから存在するかは未確認(pve側のファイルを直接読む手段がない。dispatchの `forced-command-keys` は呼び出し元自身の鍵しか見せない設計のため対象外)。

**この鍵の由来・要否はTesterの権限外。** Coordinator/Yoshinobuへの至急エスカレーション事項として扱うことを推奨する(4節)。

---

## 2. AC12 — 判定保留(quory Semaphoreからの本番Ansible実行)

**未実施。** Semaphoreジョブの起動はYoshinobuの操作であり、Testerの権限・到達範囲の外(ansyから`ann@quory`経路には触れない/触れられない)。

**何を確認すればPASSか**:

1. quoryのSemaphore UIまたはCLIから、`ann@quory` を使う本番テンプレート(保護対象ホスト向けのplaybook)を1本実行する。
2. ジョブが**成功終了**すること(Semaphoreのjob status、または `homelab-semaphore-query recent-failed` で失敗リストに現れないこと)。
3. 対象ホスト側で意図した変更が反映されていること(playbookの内容に応じた最小限の確認)。
4. 実行後、`quory-investigate` 経由の `semaphore-query task-time <n>` 等で当該job IDのレコードが読めること(dispatchが正常に機能していることの副次確認)。

今回はこの1〜4のいずれも実施していない。

---

## 3. AC13 — 初回検証時点の判定(FAIL)。9節で解消を確認しPASSへ改定

`.claude/settings.json` の `autoMode.soft_deny` に次の記述がある。

> UNREACHABLE (2026-08-03): ansy holds no credential for pve1, pve2, authy, quory, or sophos-fw.

`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」にも同旨の記述がある。

> `pve1` / `pve2` / `authy` / `quory` / `sophos-fw` へは、ansyが認証情報を1つも持たない。届くのは read 専用の forced command dispatch だけで、そこに書込の語彙は1つも無い。

1.3 のとおり、**`id_ansible` 鍵がpve1/pve2へforced commandなしのroot到達を保持しており、この記述は実測と一致しない。** AC11で要求している「`ann`としての認証不成立」自体は文書の主張と一致するが、AC13が問うているのは「記述された到達範囲がAC11の実測と一致するか」であり、AC11の実測(1.3の新規finding込み)全体で見ると一致しない。

**判定: FAIL。** `ann@homelab-ansible` の削除と、pve1/pve2/authy/quoryの記述更新(R17)は行われたが、`id_ansible` という別経路が未確認のまま「認証情報を1つも持たない」と言い切っている点が実測と食い違う。

authy / quoryについては `id_ansible` が届かないことを確認済みであり、その2ホストに限れば記述は実測と一致する。不一致はpve1/pve2の2ホストに限定される。

---

## 4. AC16 — 判定保留(quory Semaphoreからの `--check` 実行)

**未実施。** 理由はAC12と同じ(起動はYoshinobuの操作)。

**何を確認すればPASSか**:

1. quoryのSemaphoreで `--check` 系テンプレート(SAFE系 / dry-run系。例: `SAFE: Monitoring healthcheck` または `proxmox_patch_dryrun` 系)を1本実行する。
2. ジョブが**成功終了**すること。
3. 実行ログに `--check` が付与されていること、かつ対象ホストの状態が変化していないこと(playbookの性質上、dry-runなら自明だが念のため)。

今回はこの1〜3のいずれも実施していない。

---

## 5. 付随確認

### 5.1 monnieの残置(意図どおり)

```
ssh monnie 'id'  → uid=1001(ann) gid=1001(ann) groups=1001(ann)  rc=0
```

`~/.ssh/config` に `Host monnie`(`ann` / `id_ann`)が残っており、フルアクセスが維持されている。**PASS**(削除対象外のとおり)。

### 5.2 カタログ24チェック(class Q・quory)全通過

`docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md` の class Q 24チェックすべてを `quory-investigate` 経由で実行し、すべて `rc=0` で応答を得た。

無引数系15件: `bundle-list` `investigation-list` `report-playbooks` `failed` `disk` `memory` `load` `network` `ports` `journal-system` `dmesg` `status` `users` `unit-files` `forced-command-keys`

引数あり9件: `bundle-show <id> summary.json` `investigation-show <id> json` `report-list recovery_investigations` `report-list recovery_investigations sandbox` `report-show recovery_investigations sandbox <file>` `journal-unit semaphore.service 30m` `unit-cat semaphore.service` `semaphore-query recent-failed 3` `deployed-hash recovery-probe` `acl-status yoshi-home`

合計24件、全て `rc=0`。**PASS**(Phase 4の削除でカタログは壊れていない)。

class G(authy/monnie)・class P(pve1/pve2)は全数ではなくサンプル確認に留めた(`failed`/`users`/`unit-files`/`forced-command-keys`)。authy/monnieは`failed`含め通過、pve1/pve2は`failed`が未定義(`denied: unknown command 'failed'` — class Pのカタログに `failed` は無く、想定どおり)。`users`/`unit-files`/`forced-command-keys`(X2/X3/X4)は4ホストとも `rc=0`。**未実施**: G/Pの全チェック(deployed-hash各name、unit-cat各unit等)の悉皆確認は行っていない。時間的制約による部分確認である。

### 5.3 書込系・traversal拒否の再確認

```
quory-investigate 'pvesh create /foo'                          → denied: unknown command 'pvesh'  rc=1
quory-investigate 'systemctl restart semaphore'                 → denied: unknown command 'systemctl'  rc=1
quory-investigate 'bundle-show ../../../etc/passwd summary.json' → denied: invalid id for bundle-show  rc=1
quory-investigate 'bundle-show semaphore-abc summary.json'      → denied: invalid id for bundle-show  rc=1
quory-investigate 'foobar-check'                                → denied: unknown command 'foobar-check'  rc=1
```

すべて非ゼロで拒否。AC9/AC20相当は健全。

### 5.4 dispatch以外の入口の洗い出し

- ansyの `~/.ssh/config`: 保護対象向けの `ann` 経由エントリは無い(monnieのみ)。`*-investigate` 5本のみ。
- ansyのSemaphore(`/var/lib/semaphore/semaphore.db` を `sqlite3 -readonly` で読取): テンプレート1本(`SAFE: Monitoring healthcheck`)、スケジュール1件で `active=0`。D9のとおり縮小済み。
- ansyのsystemd timer: `ansible-incident-sync.timer` は存在しない(退役済み、Step2どおり)。残るAnsible関連は `ansible-knowledge-review.timer`(localhost完結)のみ。`recovery-io.service` / `recovery-probe.service` のunitファイルは存在するが `inactive`/`disabled`(実害なし、由来未確認)。
- **`id_ansible` 鍵**(5.5 = 1.3で既述): pve1/pve2へのroot到達が生きている。**唯一かつ最大の未閉鎖経路**。

`id_rsa_sophos` は削除済み(ファイル不在、`~/.ssh/config` からもエントリ削除済み)、OQ9のD7どおり。

---

## 6. 未実施項目(理由つき)

| 項目 | 理由 |
|---|---|
| AC12(Semaphoreでの本番Ansible実行) | 起動はYoshinobuの操作。Testerの到達範囲外 |
| AC16(Semaphoreでの`--check`実行) | 同上 |
| class G/Pの全チェック悉皆確認(deployed-hash各name、unit-cat各unit等) | 時間的制約。サンプルのみ実施し正常動作は確認済み |
| pve1/pve2の `root` `authorized_keys` の中身の直接確認(`id_ansible`エントリの由来・追加日時) | 対象ファイルを直接読む手段がない(dispatchは自分自身の鍵しか見せない設計)。到達可能性そのものは `id` の実行で確認済み |
| CloudKey / UniFi、vaultパスワード経由の到達(OQ9/OQ10) | 本Phaseのスコープ外(非ゴール)。requirement記載のとおり未着手 |

## 7. 残存リスク

| # | リスク | 深刻度 |
|---|---|---|
| 1 | **`id_ansible` 鍵がpve1/pve2へforced commandなしのroot到達を保持** | **重大**。AC11/AC13が要求する「能力の不在による境界」がpve1/pve2について未完成。この鍵はrepoのどこにも参照が無く、Ansibleの接続経路としても使われていない。Phase 4の設計・実装のどのステップもこの鍵を検討していない。**至急、この鍵の要否をYoshinobuが判断し、不要なら削除、必要なら理由をrequirementへ追記する必要がある** |
| 2 | AC12/AC16が未検証のまま | Semaphore経路(`ann@quory`)が実際に無傷かは推測に留まる。F2/F3(plan 002 §1)の静的確認はあるが、実行しての確認ではない |
| 3 | pve1/pve2の`root`authorized_keysの全量が不明 | `id_ansible`以外にも未知のエントリが残っている可能性を否定できない。今回は`id_ansible`が「たまたまansyの`~/.ssh/`に残っていたから」見つかった。同種の見落としが構造的に起こりうる |
| 4 | class G/Pの一部チェックは悉皆確認していない | 動作している可能性が高いが未確認分は「未確認」として扱う |

## 8. 確認した手段(箇条書き)

- `ssh -i <鍵> -o IdentitiesOnly=yes <user>@<host>.internal 'id'` によるauthorized_keys実効性の直接確認(状態を変えない)
- `~/.ssh/config` / `~/.ssh/` 配下ファイルの目視
- `.claude/settings.json` / `docs/ai/roles/coordinator.md` の目視
- `sqlite3 -readonly /var/lib/semaphore/semaphore.db` によるansy側Semaphoreテンプレート/スケジュールの読取
- `systemctl list-timers --all` / `list-unit-files` によるansy側の登録状態確認
- `grep -rln` によるrepo内の `id_ansible` 参照有無の確認
- dispatch経由(`*-investigate`)の24+サンプルチェック実行、すべて終了コードを変数捕捉(パイプ越しに測っていない)

**確認していないもの**: pve1/pve2の`root`/`ann`の`authorized_keys`の中身そのもの(直接読む手段が無い)、AC12/AC16の実行、class G/Pの悉皆チェック、CloudKey/UniFi/vault経路。

---

## 9. 再判定(2026-08-03、`id_ansible` 対処後)

Coordinatorから、`id_ansible`(ansy側の秘密鍵/公開鍵)の削除と、pveの`root`の`authorized_keys`からの該当行削除(Yoshinobu、pve1で実施)が完了した旨の連絡を受け、AC11/AC13を独立に再検証した。経緯と教訓は`2026-08-03_024_finding_unenumerated_credential.md`にまとめられているが、そこに書かれた判断は以下の実測で自分で裏を取った(引き継いでいない)。

### 9.1 `id_ansible` ファイルの不在確認

```
ls ~/.ssh/id_ansible*  → No such file or directory
```

秘密鍵・公開鍵とも ansy から削除されている。

### 9.2 保有する全鍵 × 4保護対象ホスト × (root / ann) の掃引

ansyが現在保有する鍵は5本(`id_ann` / `id_claude_investigate` / `id_claude_investigate_pve` / `id_claude_investigate_quory` / `id_ed25519`)。`id_ansible`はもう無いため直接は再試行できないが、**目的は「pve1/pve2へforced commandなしで入れる鍵が他に無いか」の確認であり、保有する全鍵を全保護対象ホストへ試すことでこれを満たす。**

5鍵 × 4ホスト(pve1.internal / pve2.internal / authy.internal / quory.internal) × 2ユーザー(root / ann)= 40通りを実行した。

```
id_ann                          × {root,ann} × 4ホスト            → 全8件 Permission denied (publickey)
id_claude_investigate           × {root,ann} × 4ホスト            → 全8件 Permission denied (publickey)
id_claude_investigate_pve       × {root,ann} × 4ホスト            → 全8件 Permission denied (publickey)
id_claude_investigate_quory     × {root,ann} × 4ホスト            → 全8件 Permission denied (publickey)
id_ed25519                      × {root,ann} × 4ホスト            → 全8件 Permission denied (publickey)
```

**40件すべて `Permission denied (publickey)`。root/annとしての到達は1件も成立しない。**

途中、`id_claude_investigate_pve` / `id_claude_investigate_quory` の一部で `kex_exchange_identification: read: Connection reset by peer`(rc=255、認証段階に達する前のTCP/SSHレベルの切断)が出た。これは40件を短時間に連続実行したことによるレート制限(fail2ban等)由来と判断し、5秒以上の間隔を空けて該当分を再実行したところ、全件 `Permission denied (publickey)` に置き換わった。**認証成立を示す兆候ではないことを確認済み。**(終了コードはすべてパイプを介さず変数へ捕捉して測定)

### 9.3 AC11再判定 — PASS

- `ann`としての認証: 4ホストとも不成立(初回検証と変わらず)。
- 専用鍵(`*-investigate`)は接続可・許可リスト外コマンドは`denied:`で非ゼロ終了(初回検証と変わらず)。
- **`id_ansible`によるroot到達は解消を実測。** 9.2の掃引で、保有する鍵のいずれもroot/annとしてpve1/pve2/authy/quoryへ到達しない。

「到達してはいけない状態」の確認項目である「書込に到達する経路が1つも無いこと」について、**現時点で保有する鍵の範囲では反証が無い。** これをもってAC11を**PASS**とする。

**留保**: `2026-08-03_024_finding_unenumerated_credential.md` 5節が指摘するとおり、この境界は「能力の列挙が完全であること」に依存する。今回の掃引はansy側の`~/.ssh/`配下という限られた場所を対象にしており、**それ以外の経路(例: 別マシンに置かれた鍵、vault経由、pve側に残る未知のエントリ)の不在までは証明していない。** 完全性の証明ではなく、既知の攻撃面に対する反証の不在である。

### 9.4 AC13再判定 — PASS

`.claude/settings.json`(`autoMode.soft_deny`)と`docs/ai/roles/coordinator.md`の「ansyはpve1/pve2/authy/quory/sophos-fwへの認証情報を1つも持たない」という記述は、**文書側を変更せず**、9.2の再実測がこの記述と一致することを確認した。**PASS**。

### 9.5 pve側の伝播確認について(未実施・理由)

pveの`root`の`authorized_keys`から該当行が削除され、それがpve1・pve2の両方に効いていることの直接確認(ファイル内容そのものを読む)は、**制約どおり実施していない** — dispatchのカタログに`root`の`authorized_keys`を読むチェックが無いため。9.2のとおり**到達性の実測で代替した**(到達しなければ、ファイルの中身がどうであれ実害は無い)。「`/root/.ssh/authorized_keys`が`/etc/pve/priv/`配下のシンボリックリンクでpmxcfsにより共有される」というYoshinobuの現物確認の内容そのものは、Testerの到達範囲外のため直接検証していない(引用のみ)。

### 9.6 残存リスクの更新

7節の残存リスク表のうち、**#1(`id_ansible`の残存)は解消と判定する。** #2〜#4は変更なし(未実施のまま)。加えて次を追加する。

| # | リスク | 深刻度 |
|---|---|---|
| 5 | **列挙の完全性は証明できていない** | 中。9.3の留保のとおり、ansy側`~/.ssh/`以外の経路(pve側に残る他の未知エントリ、別ホスト経由等)は今回の掃引の対象外。「見つかったものは塞いだ」以上のことは言えない |
| 6 | pve側`root`の`authorized_keys`の伝播(pve1→pve2)はTester自身が現物確認していない | 低。到達性の実測(9.2)で実害は否定できているが、ファイル内容そのものの一致はYoshinobuの目視に依拠 |

### 9.7 総括

初回検証で検出した重大な残存リスク(`id_ansible`によるpve1/pve2への無制限root到達)は、独立した再検証により**解消を確認した**。AC11・AC13はいずれも**PASS**へ改定する。AC12・AC16は引き続き判定保留(Semaphore起動がYoshinobuの操作であるため)。

---

## Coordinator の追記(2026-08-03)— `Connection reset by peer` の原因(**同日中に特定。下の「決着」を先に読むこと**)

本記録は再掃引中に出た `Connection reset by peer` を「**急速な連続接続によるレート制限**」と記している。**この因果は確かめられていない。**

Yoshinobu から別の可能性が示された — **同時刻にスマートフォンのVPNが切れていた**。ansy → pve は内部ネットワーク上のサーバ間接続であり、利用者のVPNセッションが直接切る経路は考えにくいが、**VLAN間ルーティングを sophos-fw が担っているならVPNの張り直しで一瞬揺れうる**。

**どちらかを判定する手段が現時点で無い。**

| 試したこと | 結果 |
|---|---|
| pve1 / pve2 の `journal-system`(dispatch経由) | sshd 関連の行は0件。**ただしこのチェックは `-p warning..err` で絞っており、sshd の MaxStartups throttling は通常 info レベルで出るため、空であることは何の証明にもならない** |
| pve の `journal-unit` で sshd を見る | **enum に `sshd` が無く、実行できない** |

**判定への影響は無い。** 原因がどちらであれ、間隔を空けた再実行で全40通りが `Permission denied (publickey)` を返しており、AC11 / AC13 の根拠は再実行の結果に置かれている。**訂正するのは因果の記述であって、判定ではない。**

### 拾った穴

**現在の調査面は、境界そのものが乗っている transport(SSH)のログを見られない。** カタログ(`..._008_phase3_check_catalog.md`)を組んだとき、復旧・クラスタ系の unit だけを列挙し、SSH デーモンを入れていなかった。Phase 4 で ansy から保護対象ホストへ届かなくなった以上、**「なぜ SSH が切れたのか」を調べる手段は dispatch にしか無い**。`docs/ai/status.md` の Next へ起票した。

### 決着(2026-08-03、`journal-ssh` 配備後)

**原因は OpenSSH の PerSourcePenalties である。VPN 説は否定された。**

カタログ §7 の `journal-ssh` を配備した直後、pve1 の SSH journal に次の形の行が並んでいた
(送信元は ansy。IP は本リポジトリへ書かない)。

```
sshd[…]: drop connection #0 from [ansy]:… on [pve1]:22 penalty: failed authentication
```

同一秒に7件、数分後にもう一群。**OpenSSH 9.8 以降は、認証に失敗した送信元へ罰則を課し、
以後の接続を認証が始まる前に切る。** クライアント側での見え方が
`kex_exchange_identification: read: Connection reset by peer` である。

**再掃引は「40通りすべてを `Permission denied (publickey)` にする」ことが目的であり、
認証失敗を意図的に大量生成していた。** sshd は設計どおり反応したにすぎない。検査自身が
引き起こした現象である。

- **機構は確定。** 罰則メッセージが現物として存在し、送信元を ansy と名指ししている。
  経路の揺れであれば送信元を特定した罰則メッセージは出ない。
- **あの掃引への帰属は、時刻の一致による推定である。** 本記録に時刻が書かれておらず
  突き合わせられなかった。ただし Phase 4 以降 ansy から失敗認証を出すものは掃引以外に無く、
  同一秒7件という形も走査の形である。

**§292 の表の1行目が言っていた「空であることは何の証明にもならない」は正しかった。**
`journal-system` が沈黙していたのは事象が無かったからではなく、罰則メッセージが
`-p warning..err` の外(info)で出ていたからである。**この行は、絞り込み条件つきの検査で
空を得たときに何を結論してよいかの実例として残す。**
