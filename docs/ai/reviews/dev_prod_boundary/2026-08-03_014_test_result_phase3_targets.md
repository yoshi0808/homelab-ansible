# test_result: Phase 3 保護対象4ホスト(class G / class P) 受入条件検証

日付: 2026-08-03 (JST)
対象: `roles/recovery_exec` により authy / monnie(class G)、pve1 / pve2(class P)へ配備された `recovery-investigate-dispatch.sh` / `recovery-investigate-dispatch-pve.sh`
基準: `2026-08-03_008_phase3_check_catalog.md` §2(class G追加分)・§3(class P追加分)、`2026-08-02_001_requirement.md` §9(AC8/AC9/AC10)
先行記録: `2026-08-03_013_test_result_phase3_quory.md`(quory側は検証済・対象外。本記録では重複させない)
検証者: Tester
実装コミット: `5328ff7`(作業ツリーclean、検証によるrepo変更なし)

## 実行環境・手段

- **Claude Code側**: `ssh authy-investigate '<check>'` / `monnie-investigate` / `pve1-investigate` / `pve2-investigate`(`~/.ssh/config` の forced-command dispatch alias。鍵は `id_claude_investigate` / `id_claude_investigate_pve`)。これがClaude Code側の実経路そのもの。
- **Codex側(AC10比較用)**: quoryへ `ssh quory`(`ann` 鍵、非保護ホストのため状態を変えない確認として使用)で入り、`sudo -n -u recovery-exec ssh -i /home/recovery-exec/.ssh/id_recovery_investigate[_pve] recovery-exec@<host>.internal '<check>'` を実行した。Codexの秘密鍵の**中身は一度も表示・複製していない**(`ls -la` で存在とパーミッションのみ確認し、`sudo -u recovery-exec ssh -i <path>` で鍵ファイルを直接使わせる形を取った)。この経路は Codex が `homelab-investigate-<target>` ラッパー経由で最終的に到達する forced-command dispatch と同一のもの(ラッパー自体は `deployed-hash` / `unit-cat` をまだ許可リストへ持たないため、AC10が問う「dispatch scriptが呼び出し元で挙動を変えていないか」を検証するにはこの直接比較が適切と判断した。詳細は AC10 の項)。
- 保護対象4ホストへは forced command 経由の read チェックのみを実行した。quoryへは `ann` 鍵で read-only確認(`ls -la`、`sudo -u recovery-exec ssh`)のみを行い、状態変更コマンドは実行していない。
- 実行コマンド・生出力・rc は `/tmp/claude-1000/-home-yoshi-homelab-ansible/15e32143-f25b-4572-9e96-6267ce11e96c/scratchpad/test_log_phase3_targets.txt`(セッション終了後に失われるtmpのため、以下に実測を転記する)。**内部IPアドレスが一部生出力に含まれていたため、本ファイルへの転記では該当箇所を伏せた**(`docs/ai/core.md`「内部IPアドレスを…リポジトリ内へ直接記載しない」に従う)。
- rcは常に `ssh ... "$cmd"` の直接の終了コードを読んでおり、パイプ越しに測っていない(`cmd | head` の `$?` 問題を回避)。

## 判定一覧

| AC | 判定 | 根拠 |
|---|---|---|
| AC8 | **PASS** | 4ホストすべてで未許可文字列(`this-is-not-a-check`)と `rm -rf /` を送り、全件 `denied:` とともに **rc=1** で終了。コマンド未実行(出力に実行結果が含まれない) |
| AC9 | **PASS** | class Gで17パターン(`pvesh create/set/delete`、`systemctl start/stop/restart/enable/disable`、`qm start/stop`、`;`/`\|\|`/`\|`/`&&`によるコマンド結合、`cp`/`mv`、`eval status`)×2ホスト、class Pで12パターン(pvesh書込、`qm start/stop`、`ha-manager crm-command relocate`、有効operand内への `;`/`&&`/`\|` 混入、`eval`、リダイレクト)×2ホストを実行し**全件 `denied:` で非ゼロ終了**。有効checkの文字列へ書込語彙を後続結合した場合も、`case` の完全一致判定または `read` によるarity超過検出で実行前に止まることを確認した |
| AC10 | **PASS(実測比較)** | quory側test_resultと異なり、**class G/Pではclass Q特有の制約(quoryにCodex鍵が無い)が無いため、実際の鍵2本での出力比較ができた**。class G(authy)9チェック、class G(monnie)11チェック、class P(pve1)11チェック、class P(pve2)4チェックで、Claude Code鍵経由(直接forced-command dispatch)とCodex鍵経由(quoryのrecovery-exec識自身がforced-command dispatchへ到達する経路)を実行しdiffを取った。**新設チェック(`deployed-hash`・`unit-cat`)を含む大半は完全一致**。一致しなかったもの(authyの`status`/`memory`、pve1/pve2の`cluster-status`/`ha-status`)はすべて**時刻・生きた計測値(uptimeの経過分・空きメモリのKB単位・pvesh JSON配列の順序)による自然なドリフト**であることを個別diffで確認した(下記詳細参照)。呼び出し元で分岐する実装は見当たらなかった |
| 回帰(既存Codexチェック) | **PASS** | AC10比較の対象に `failed`/`disk`/`load`/`network`/`ports`/`journal-system`/`dmesg`(class G共通)、`storage-status`/`zpool-health`/`zfs-list`/`cluster-quorum`/`journal-unit`(class P)を含めており、いずれも一致(生きた値を含まないチェックは完全一致、含むものは上記と同様の性質の差のみ)。既存チェックが変更されていないことを確認した |

## AC10 詳細 — 一致しなかった4件の内訳

| チェック | 差分の性質 | 確認方法 |
|---|---|---|
| authy `status` | `systemctl status` の "Active: active (running) since ... Xh Ymin ago" の経過時間表記が、2回の呼び出し間隔(数秒〜数十秒)ぶんズレる | 差分行が経過時間の数値のみであることを目視確認 |
| authy `memory` | `free -h` の `free`/`available` 列がMB単位で微増減(999Mi→1.0Gi等) | 差分がメモリ値のみであることを目視確認 |
| pve1 `cluster-status` | `pvesh get /cluster/status --output-format json` が返すJSON配列の**要素順序**が呼び出しごとに入れ替わる(内容は同一集合)。Proxmox API側の非決定的な順序で、スクリプト側の分岐ではない | 2回の出力をkey単位で比較し、集合として同一であることを確認 |
| pve2 `ha-status` | `ha-manager status` の `lrm pve2 (idle, watchdog standby, <timestamp>)` の時刻表記が呼び出し間隔ぶんズレる(5秒差を実測) | `diff` で該当行のみが時刻表記の差であることを確認 |

いずれも「同一のコマンドを同一の権限・スクリプトで実行した結果、実行時刻や実行順序に依存する部分だけが変わった」ものであり、**dispatch scriptが呼び出し元(鍵)によって挙動・出力内容を変えている根拠にはならない**。むしろ非決定的な部分を除けば完全一致しており、AC10の「scriptが呼び出し元で挙動を変えていない」はPASSと判定した。

## deployed-hash / unit-cat の正経路・負経路(class G / class P)

### class G(authy / monnie)

| check | 正経路 | 負経路 |
|---|---|---|
| `deployed-hash` | 5 name(`recovery-push`/`recovery-trigger-unit`/`investigate-dispatch`/`action-script`/`authorized-keys`)を authy・monnie 両方で取得成功。`loki-helper` は **monnie でのみ成功(rc=0)**、**authy では `denied: invalid name for deployed-hash` で rc=1**(カタログ§2「monnieのみ」の要求どおり) | 未列挙name(`not-a-name`)、パス風operand(`/etc/passwd`)、traversal(`../../etc/passwd`)、arity超過(`recovery-push extra`)、operand無し、いずれも `denied:` で rc=1 |
| `unit-cat` | `freeradius`(既存 `investigate_services`)と `recovery-trigger@.service` を authy で取得成功 | 未列挙unit(`sshd.service`)、パス風operand、arity超過、operand無し、いずれも `denied:` で rc=1 |

### class P(pve1 / pve2)

| check | 正経路 | 負経路 |
|---|---|---|
| `deployed-hash` | `investigate-dispatch-pve`・`authorized-keys` を pve1・pve2 両方で取得成功 | 未列挙name(`recovery-push` = class G側のname)、パス風operand、arity超過、いずれも `denied:` で rc=1 |
| `unit-cat` | 既存 `journal-unit` と同一enum(`pvescheduler`/`pvestatd`/`pve-cluster`/`corosync`/`pvedaemon`)を全件 pve1 で取得成功 | 未列挙unit、パス風operand、arity超過、operand無し、いずれも `denied:` で rc=1 |

## I-1〜I-6(カタログ§0 不変条件)の確認

- I-1(read限定): AC9の全結果に加え、`status > /tmp/x` / `status \| tee /tmp/x` 等のリダイレクト・パイプを**含む文字列全体**を送っても、`case` の完全一致にヒットせず `denied:` になることを確認(`eval`していないため文字列全体が1つのトークンとして扱われる)
- I-2(`eval`不使用): ソース確認(`recovery-investigate-dispatch.sh.j2` / `-pve.sh.j2`)。`eval` は使用されていない。`eval status` という文字列も未知コマンドとして拒否されることを実測確認
- I-3(パス組立禁止): ソース確認。`deployed-hash` は `case "$name" in ... target_path=<固定パス> ;; esac` 形式でoperandから直接パスを組み立てていない。class Pの `deployed-hash` も同型
- I-4(固定arity): `read -r check p1 p2 extra <<<"$cmd"`(pve)/ 個別 `read -r _ name extra`(authy/monnie)を確認。extra付き呼び出しがすべてdeniedになることを実測(上記負経路)
- I-5(改行即拒否): 実測(`I5_authy_newline` rc=1、`I5_pve1_newline` rc=1)
- I-6(denied+非ゼロ終了): 全AC8/AC9/負経路テストで確認済み

## 残存リスク

- **AC10はサンプリング**であり、全27 check(class G既存分含む)×2ホストの全数比較ではない。新設2 check(`deployed-hash`/`unit-cat`)と既存代表チェック(computed値を含むもの・含まないもの双方)を選んで実行した。全数比較は行っていない。
- **`homelab-investigate-<target>` ラッパー(quory上、`homelab-investigate.sh.j2`)の許可リストは、本Phaseで追加した `deployed-hash`/`unit-cat` を含んでいない**(ソース確認)。これはCodexが実際に `homelab-investigate-authy deployed-hash recovery-push` のような呼び出しをしても、quory側ラッパーが `denied: unknown check` で止め、target側dispatchへ到達しない状態を意味する。**AC10文言(「Codex用の鍵とClaude Code用の鍵で同じチェックを実行し、同一の出力が得られること」)は dispatch script 自体の検査であり、本検証はそちらをPASSと判定した**が、Codexが実運用でこの2 checkを使うにはラッパー側の許可リスト追加が別途必要である。カタログ・requirementはラッパー側の追随を明示的には要求していないため欠陥ではなく未実施として記録する。
- **AC9の「有効checkの操作(operand)経由での書込語彙混入」は代表パターンのみ**。全operand位置×全書込語彙の組み合わせ網羅ではない。ただし固定arity(I-4)とcase完全一致の構造上、この種の網羅は構造的に不要と判断した(quory側test_resultと同じ判断)。
- **`sudo -n -u recovery-exec ssh -i <Codexの鍵>` という比較手段は、Codexのsandbox実行環境(bwrap等)の権限・UIDそのものを再現していない**。quoryのrecovery-exec識自身のUIDでSSH鍵を使わせているため、鍵の識別による認証結果とdispatch側の挙動は実測できたが、Codex CLIプロセス自体が持つ制約(実行環境差)までは再現していない。

## 今回確認できなかったこと

- **`homelab-investigate-<target>` ラッパーへ`deployed-hash`/`unit-cat`を実際に流した動作確認**(上記残存リスクのとおり、現状のラッパーはこの2 checkを許可リストに持たないため、Codexの実運用経路としては到達しない。dispatch script自体の検証はAC10として実施済み)。
- **AC10の全チェック網羅比較**(上記のとおりサンプリング)。
- **AC1〜AC7、AC11〜AC20**(Phase 1/2/4対象、または既にquory側test_resultで判定済みのAC19/AC20)は本タスクの範囲外。

## 到達してはいけない状態への抵触

- 保護対象ホスト(pve1/pve2/authy)の状態変更: なし。forced command経由のread専用語彙(`systemctl status`/`cat`/`sha256sum`/`journalctl`/`pvesh get`/`ha-manager status`/`pvesr`/`pvecm status`/`pvesm status`/`zpool status`/`zfs list`/`stat`/`tail`)のみを実行した。
- sophos-fw / UniFi への到達: なし。
- 本番Slackへの通知: なし(通知経路を持つplaybook・コマンドを一切実行していない。本検証はAnsible playbookを一切実行せず、SSH forced-command dispatchのみを対象とした)。
- リポジトリ内ファイルの変更: 本ファイル以外の変更なし(`git status --short` で確認済み)。
- Codexの秘密鍵の内容: 一度も表示・複製していない(存在とパーミッションのみ `ls -la` で確認し、`sudo -u recovery-exec ssh -i <path>` で鍵ファイルへ直接アクセスさせる形で使用した)。

---

## Coordinator の処置 — 残存リスク「Codex の実経路が wrapper で塞がる」(2026-08-03)

**指摘を再現し、直した。** 検証時点では dispatch は両鍵で同一に振る舞っていたが、**Codex が実際に通る経路(quory の `homelab-investigate-<target>` wrapper)の許可リストに `deployed-hash` / `unit-cat` が無く**、target へ届く前に拒否されていた。

```
$ sudo -u recovery-exec /usr/local/bin/homelab-investigate-authy deployed-hash recovery-push
denied: unknown check 'deployed-hash'   (rc=1)
```

これは requirement R11「Codex と Claude Code で内容を同一とする」に反する。**dispatch が同一であることは、Codex から到達できることを意味しない** — 授権境界(dispatch)と実経路(wrapper)は別物であり、同一性は両方で要る。

### 直したもの

| ファイル | 変更 |
|---|---|
| `roles/recovery_exec/templates/homelab-investigate.sh.j2` | `deployed-hash` / `unit-cat` の arm を追加。enum は dispatch と鏡写し(`loki-helper` は `'loki' in target.investigate_services` で monnie のみ) |
| `roles/recovery_exec/templates/homelab-investigate-pve.sh.j2` | 同上(name は2種、unit は `journal-unit` と同一 enum) |
| `roles/recovery_exec/templates/AGENTS.md.j2` | 両 class の節へ追記。**Codex がこれを何に使うか**(「repo は直った」と「その変更がこのホストへ届いた」を切り分ける)を書いた |

quory へ再配備済み(`recovery_exec_setup.yml -l quory -e recovery_exec_setup_targets=false`、changed=3)。**wrapper は quory ローカルのため保護対象ホストへの再配備は不要。**

### 再検証(Coordinator が実施。AC の判定ではなく事実の収集)

| 確認 | 結果 |
|---|---|
| Codex 経路で新チェックが通る | `authy deployed-hash recovery-push` / `monnie deployed-hash loki-helper` / `pve1 deployed-hash investigate-dispatch-pve` / `pve2 unit-cat corosync` — すべて rc=0 |
| class 固有の name が他 class で通らない | `authy deployed-hash loki-helper` → `denied: invalid name` rc=1 |
| パスを operand に渡せない | `authy deployed-hash /etc/shadow` → `denied: invalid name` rc=1 |
| **両鍵の出力一致(AC10 の新チェック分)** | `authy deployed-hash action-script` / `monnie unit-cat loki` / `pve1 deployed-hash authorized-keys` / `pve2 unit-cat pvestatd` の4件で**完全一致** |

**この修正は Phase 3 の承認済みカタログの範囲内である** — 新しいチェックは1つも増えておらず、承認済みのチェックを Codex から到達可能にしただけである。D5 の再承認は要さない。
