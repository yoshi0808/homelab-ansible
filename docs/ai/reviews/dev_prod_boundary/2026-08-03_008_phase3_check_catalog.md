# Phase 3 追加チェック カタログ(D5 承認対象)

日付: 2026-08-03 (JST)
plan: `2026-08-03_007_plan_phase3.md` §1.1 の確定版
requirement: `2026-08-02_001_requirement.md` R11 / R12 / R13b / R14c、AC9

**このファイルが「何を露出させるか」の正本である。** Implementer はここから実装し、Reviewer は AC9(書込が1つも露出していないこと)をここに対して検査する。

**2026-08-03、Yoshinobu が本カタログを D5 として承認した。** 「read only ということだし、対象ノードも考慮されている」。以降、ここに無いチェックを実装へ足す場合は再度承認を要する。

## 0. 全体に効く不変条件

| # | 不変条件 |
|---|---|
| I-1 | **すべて read。** `pvesh create`/`set`/`delete`、`systemctl start`/`stop`/`restart`/`enable`、`qm start`/`stop`、リダイレクト、`tee`、`rm`、`mv`、`cp` を1つも露出しない |
| I-2 | **`eval` を使わない。** `SSH_ORIGINAL_COMMAND` をシェルへ再解釈させない(既存 dispatch の AR-048 / AR-088 規律) |
| I-3 | **operand からパスを組み立てない。** ファイルを指すチェックは name→絶対パスの対応表を script 内に持つか、固定 BASE + enum 済みファイル名のみで組む |
| I-4 | **固定 arity。** `read -r check p1 p2 p3 extra` で受け、宣言数を超えた token があれば実行前に `denied:` |
| I-5 | **改行・復帰を含むコマンドは即拒否**(既存と同一) |
| I-6 | 拒否は必ず `denied: ...` を stderr へ出し**非ゼロ終了**する(AC8 / AC20) |
| I-7 | quory 側の wrapper は first-line filter に過ぎず、**forced command が唯一の授権境界**(R14 で確認済み) |

## 1. 新設 class Q — quory(`recovery-investigate-dispatch-quory.sh`)

受け口は新規ユーザー `dev-investigate`。**sudo を1つも持たない**(`/etc/sudoers.d/` 配下にこの identity のファイルを作らない)。

このユーザーへ与える権限は次の**4つだけ**である。当初この節は `/home/yoshi` の traverse しか挙げておらず不完全だった。**2026-08-03、独立レビューの指摘(M1)を受けて Yoshinobu が全4件を承認し、ここへ明記した。**

| 付与 | 何のために要るか | 前例 |
|---|---|---|
| `/home/yoshi` に ACL traverse(`--x`) | Q1〜Q7 が `reports/` 配下を自分の UID で読む | `recovery-exec` / `incident-inspect` に同一のものが付いている |
| `/var/lib/semaphore` に ACL traverse | Q11 | `recovery-exec` に同一 |
| `semaphore.db` に ACL read | Q11 | `recovery-exec` に同一 |
| **`systemd-journal` グループ所属** | **Q9 `journal-unit` / Q-C `journal-system` / `dmesg`。sudo を持たないこの identity が journal を読む唯一の手段** | authy / monnie の `recovery-exec` に同一 |

**`systemd-journal` の粒度はこの表より粗い。** グループ所属が与えるのは「enum で絞った unit の journal」ではなく**全 journal の読取**である。絞っているのは *何を尋ねられるか*(dispatch の enum)であって、*何が読めるか* ではない。これを承認したうえで、次の2つを境界として数えている — ①forced command 以外の入口が無いこと ②`no-pty` を含むオプションで対話 shell が得られないこと。**この identity へ sudo を足す変更は、この前提を崩すので再承認を要する。**

### Q-A 障害バンドル参照(R14c。**必須**。`incident_sync` 退役の前提)

| # | check | operand と検証 | 実行内容 |
|---|---|---|---|
| Q1 | `bundle-list` | 無し | `reports/incidents/` 直下で `^semaphore-[0-9]{1,9}$` に一致するディレクトリ名を列挙 |
| Q2 | `bundle-show <id> <file>` | `id`: `^semaphore-[0-9]{1,9}$`<br>`file`: enum `summary.json` \| `semaphore-log.log` \| `semaphore-hosts.log` \| **`semaphore-errors.log`** | `cat -- <BASE>/<id>/<file>` |
| Q3 | `investigation-list` | 無し | `_investigations/` の `<id>` を(拡張子を落として)重複なく列挙 |
| Q4 | `investigation-show <id> <ext>` | `id`: 同上<br>`ext`: enum `md` \| `json` | `cat -- <BASE>/_investigations/<id>.<ext>` |

- `BASE=/home/yoshi/homelab-ansible/reports/incidents` は script 内の固定値。operand から一切組み立てない
- `_spool/` と `_runs/` は**露出しない**(消費用ローカル入力であり調査の対象ではない)
- **`bundle-grep`(横断検索)は初期リリースから外す。** R14c が明示的に許容している。任意文字列を operand に取る唯一のチェックになるため、必要性が実運用で確認できてから別途起票する

### Q-B レポート参照(R13b + 配備物ハッシュ。**必須**)

| # | check | operand と検証 | 実行内容 |
|---|---|---|---|
| Q5 | `report-playbooks` | 無し | `recovery-reports-helper list-playbooks` |
| Q6 | `report-list <playbook> [target]` | 各 `^[a-zA-Z0-9_-]+$` | 同 `list-reports` |
| Q7 | `report-show <playbook> [target] <file>` | `playbook`/`target`: 同上<br>`file`: `^[a-zA-Z0-9_+-]+\.json$` | 同 `show-report` |

**この3本で R13b と「配備物ハッシュを返すチェック」の両方が成立する。**

- ラダー実行レポート → `report-show recovery_investigations sandbox 20260803_053711+0900.json`
- 日次ドリフト検査の結果(期待値との突合済み) → `report-show drift latest.json`

**前提となる修正(plan G1)**: 既存 helper の `FILE_RE='^[a-zA-Z0-9_-]+\.json$'` は `+0900` を含む JST タイムスタンプ名を弾いており、**現状ラダーレポートもドリフトレポートも Codex から読めない**。`+` を1文字だけ足す。`.` は足さない — 名前部に `.` を許すと `..` が入りうるため、traversal が構造的に不可能である性質を崩さない。

### Q-C 共通 system check — 既存 generic class から**そのまま移植**(8種)

`failed` / `disk` / `memory` / `load` / `network` / `ports` / `journal-system` / `dmesg`

**実装を書き換えず、既存 `recovery-investigate-dispatch.sh.j2` と同一の中身にする。** R11「Codex と Claude Code で内容を同一とする」を、class をまたいでも同一語彙に保つ形で満たす。

### Q-D quory 固有(5種)

| # | check | operand と検証 | 実行内容 |
|---|---|---|---|
| Q8 | `status` | 無し | 下表 unit 群の `systemctl status --no-pager -l`(失敗は `|| true` で飛ばす。既存 `status` と同型) |
| Q9 | `journal-unit <unit> <window>` | `unit`: 下表 enum<br>`window`: `30m`\|`1h`\|`2h`\|`6h`\|`12h`\|`24h` | `journalctl -u <unit> --since ... -n 300 --no-pager` |
| Q10 | `unit-cat <unit>` | 下表 enum | `systemctl cat <unit>`(配備された unit 本体の現物確認。R12 が例示) |
| Q11 | `semaphore-query <query> <n>` | `query`: enum `recent-failed`\|`running`\|`task-errors`\|`task-hosts`\|`task-output`\|`task-time`\|**`template-list`**<br>`n`: `^[0-9]+$` | `homelab-semaphore-query <query> <n>` |

**`running` は2026-08-03に追加(D5承認、`docs/ai/reviews/quory_worktree_sync/` OQ-7)。** 終端でないstatusのタスクを新しい順に返す。**「実行中」をstatusの肯定的な列挙で書いていない** — Semaphoreが実行中に使う値はこの環境で観測されておらず、列挙すると観測漏れが「動いていない」という誤答になるため、終端3値(`success` / `error` / `stopped`、実測済み)の否定で書いてある。書込語彙は増えず、既存の「クエリ名 + 整数」契約も変えていない。
| Q12 | `deployed-hash <name>` | 下表 enum | `sha256sum <対応する絶対パス>` |

#### unit enum(実機で存在を確認済み。2026-08-03)

`recovery-probe.service` / `recovery-probe-sandbox.service` / `recovery-io.service` /
`homelab-incident-capture.service` / `homelab-incident-capture.timer` /
`homelab-incident-investigate.service` / `homelab-incident-investigate.timer` /
`semaphore.service` /
`ansible-cert-renew-quory.service` / `.timer` /
`worktree-sync.service` / `worktree-sync.timer` /
`ansible-authy-healthcheck.timer` / `ansible-monitoring-healthcheck.timer` /
`ansible-proxmox-healthcheck.timer` / `ansible-proxmox-hw-check.timer` / `ansible-proxmox-patch-dryrun.timer`

`status` が一括表示するのは先頭8つ(復旧パイプライン + Semaphore)に絞る。

**`worktree-sync.service` / `.timer` は2026-08-03に追加(D5承認、`docs/ai/reviews/quory_worktree_sync/`)。** 同期の稼働はSlack通知だけでは判断できない — 異常系の通知は抑止つきで、**「鳴らない」は正常と抑止中の両方を意味する**。journalが唯一の一次情報になる。配備直後に気づいたため、dispatchの再配備を1回で済ませられた(Phase 4 D6と同じ判断)。

#### `deployed-hash` name→パス表(class Q)

| name | パス |
|---|---|
| `recovery-probe` | `/usr/local/sbin/recovery-probe.py` |
| `incident-capture-collector` | `/usr/local/sbin/incident-capture-collector.py` |
| `incident-investigate` | `/usr/local/sbin/incident-investigate.py` |
| `recovery-push-dispatch` | `/usr/local/sbin/recovery-push-dispatch.sh` |
| `reports-helper` | `/usr/local/sbin/recovery-reports-helper` |
| `bundle-helper` | `/usr/local/sbin/incident-bundle-helper`(本Phaseで新設) |
| `semaphore-query` | `/usr/local/bin/homelab-semaphore-query` |
| `investigate-dispatch-quory` | `/usr/local/sbin/recovery-investigate-dispatch-quory.sh`(自分自身) |

**`/etc/sudoers.d/` は表に入れない。** 実機で `0440`/`0640 root:root` を確認しており、読むには sudo が要る。そこまでして得るものが無く、template 由来で repo 側の期待値も無い(Tier 2 の壁と同じ)。

## 2. 既存 class G — authy / monnie(`recovery-investigate-dispatch.sh`)への追加

| # | check | operand と検証 | 実行内容 |
|---|---|---|---|
| G1 | `deployed-hash <name>` | 下表 enum | `sha256sum <パス>` |
| G2 | `unit-cat <unit>` | 既存 `investigate_services` + `recovery-trigger@.service` | `systemctl cat <unit>` |

#### `deployed-hash` name→パス表(class G)

| name | パス | 対象 |
|---|---|---|
| `recovery-push` | `/usr/local/sbin/recovery-push.sh` | authy / monnie |
| `recovery-trigger-unit` | `/etc/systemd/system/recovery-trigger@.service` | authy / monnie |
| `investigate-dispatch` | `/usr/local/sbin/recovery-investigate-dispatch.sh` | authy / monnie |
| `action-script` | `/usr/local/sbin/recovery-action.sh` | authy / monnie |
| `authorized-keys` | `/home/recovery-exec/.ssh/authorized_keys` | authy / monnie |
| `loki-helper` | `/usr/local/sbin/recovery-loki-helper` | **monnie のみ** |

`authorized-keys` はハッシュのみを返し中身は返さない。中身は公開鍵だが、**「forced command が付いているか」という構造検査は日次ドリフト検査が既に持っている**(`deployment_drift_check_forced_command_keys`)ため、こちらは版の同一性だけを見る。

## 3. 既存 class P — pve1 / pve2(`recovery-investigate-dispatch-pve.sh`)への追加

| # | check | operand と検証 | 実行内容 |
|---|---|---|---|
| P1 | `deployed-hash <name>` | 下表 enum | `sha256sum <パス>` |
| P2 | `unit-cat <unit>` | 既存 `journal-unit` と**同一 enum**(`pvescheduler` / `pvestatd` / `pve-cluster` / `corosync` / `pvedaemon`) | `systemctl cat <unit>` |

#### `deployed-hash` name→パス表(class P)

| name | パス |
|---|---|
| `investigate-dispatch-pve` | `/usr/local/sbin/recovery-investigate-dispatch-pve.sh` |
| `authorized-keys` | `/home/recovery-exec/.ssh/authorized_keys` |

pve 側の配備物は dispatch と sudoers と authorized_keys しか無く、いずれも template 由来である。**repo 側の期待値と自動比較はできない**(Tier 2)。それでも「前回見たときと変わっていないか」は追えるため2件だけ露出する。

## 4. 総数

| class | 既存 | 追加 | 計 |
|---|---|---|---|
| Q(quory・新設) | 0 | **20**(A4 + B3 + C8 + D5) | 20 |
| G(authy / monnie) | 既存のまま | **2** | — |
| P(pve1 / pve2) | 既存のまま | **2** | — |

**新しく露出する語彙は `cat` / `sha256sum` / `systemctl status` / `systemctl cat` / `journalctl -u` / `sqlite3 -readonly` / `find` / `df` / `free` / `uptime` / `ip` / `ss` の12種のみで、すべて read である。**

## 5. 承認後に変わらないこと(念のため)

- **Codex 側の既存チェックを1つも削らない。** G1(`FILE_RE`)の修正は Codex の読める範囲を**広げる**方向のみ
- **action 面(`recovery-action.sh` / `homelab-recover-*` / mute set・clear)は Claude Code へ一切露出しない。** requirement 4.5 のとおり共用しない
- **pve / authy / monnie の script 本体は Codex と同一のまま。** 鍵エントリが1行増えるだけで、呼び出し元による分岐は入れない(AC10)

---

# 6. 追加チェック(D6、2026-08-03 承認)

**Phase 4 で ansy の任意 read が消える前に足すもの。** 承認の根拠は「Phase 3 の作業で**現に必要になった**確認であり、想像上の需要ではない」こと(`2026-08-03_015_plan_phase4.md` D6)。§0 の不変条件 I-1〜I-7 はこの4件にもそのまま適用される。

| # | check | class | operand と検証 | 実行内容 |
|---|---|---|---|---|
| X1 | `acl-status <path>` | **Q のみ** | 固定 enum: `yoshi-home` \| `semaphore-dir` \| `semaphore-db` \| `reports-root` | 対応する固定パスへ `getfacl -p`。**パスは operand から組み立てない** |
| X2 | `users` | Q / G / P | 無し | ローカルユーザーの一覧。**uid 1000〜64999 に限り、`name:uid:shell` の3項目だけ**を出す。`/etc/shadow` には一切触れない |
| X3 | `unit-files` | Q / G / P | 無し | `systemctl list-unit-files --no-pager`。ディレクトリ走査ではなく systemd に問う(パス操作を持ち込まない) |
| X4 | `forced-command-keys` | Q / G / P | 無し | **自分自身の** `authorized_keys` について、エントリ数と、各行の「forced command のパス」「コメント欄」だけを出す。**鍵本体は出さない** |

## 6.1 なぜこの4件なのか

| # | Phase 3 で何に使ったか |
|---|---|
| X1 | `dev-investigate` に ACL が正しく付いたかの確認。**ACL は「付いているつもりで付いていない」が最も起きる形**で、症状は「helper が読めない」という間接的なものになる |
| X2 | 新設ユーザーの存在確認と、既存 inbound ユーザー(`trigger` / `incident-inspect` 等)の棚卸し |
| X3 | unit の実在確認。`journal-unit` / `unit-cat` の enum は**実在する unit しか受け付けない**ため、enum を直すには先に一覧が要る |
| X4 | 配備後にエントリが期待どおり増えたかの確認。**日次ドリフト検査も同じことを見ているが、あちらは1日1回で、配備直後に確かめる手段が別に要る** |

## 6.2 設計上の注意(実装時に確かめること)

- **X1**: `getfacl` が `/home/yoshi`(`0711` + ACL)に対して、dispatch の実行 identity で読めるか。読めない場合、この check は成立しない — **成立しないなら実装せず報告すること**(sudo を足して通すのは `dev-investigate` の契約を壊す)
- **X2**: uid 範囲の下限・上限を script 内の定数に持ち、operand から変えられないようにする
- **X4**: class ごとに「自分自身の `authorized_keys`」が指す先が違う(Q=`dev-investigate`、G/P=`recovery-exec`)。**他ユーザーの `authorized_keys` を読めるようにしない**
- 4件とも**書込語彙をひとつも増やさない**。`getfacl` / `getent` / `systemctl list-unit-files` / 自分のファイルの読み取りだけである

## 6.3 総数の更新

| class | §1〜§3 | §6 | 計 |
|---|---|---|---|
| Q(quory) | 20 | +4 | **24** |
| G(authy / monnie) | +2 | +3(X2 / X3 / X4) | +5 |
| P(pve1 / pve2) | +2 | +3(X2 / X3 / X4) | +5 |

**新しく露出する語彙は `getfacl` / `getent` / `systemctl list-unit-files` の3種のみ。いずれも read である。**

---

# 7. 追加チェック(D7、2026-08-03 承認)— `journal-ssh`

**Yoshinobu が承認した。** 起票の根拠は `2026-08-03_023_test_result_phase4.md` の Coordinator 追記 —
再掃引中に出た `kex_exchange_identification: read: Connection reset by peer` の原因を、
レート制限か経路の揺れかで**判定できなかった**。**現在の調査面は、境界そのものが乗っている
transport(SSH)のログを1行も見られない。** Phase 4 で ansy から保護対象ホストへ届かなくなった
以上、調べる手段は dispatch にしか無い。

§0 の不変条件 I-1〜I-7 はそのまま適用される。**書込語彙は1つも増えない**(`journalctl -u` は既出)。

| # | check | class | operand と検証 | 実行内容 |
|---|---|---|---|---|
| S1 | `journal-ssh <window>` | Q / G / P | `window`: 既存 `journal-unit` と**同一 enum**(`30m`\|`1h`\|`2h`\|`6h`\|`12h`\|`24h`)。**unit は operand に取らない** | 下表(class で異なる) |

## 7.1 なぜ `journal-unit` の enum への追加ではないのか

**当初案は「enum に `sshd` を足す」だった。実機を測って取り下げた。**

`unit-files`(X3)で5ホストを実測した結果(2026-08-03):

| ホスト | `ssh.service` | `ssh.socket` | 接続ごとのログの出先 |
|---|---|---|---|
| pve1 / pve2 | enabled | **disabled** | `ssh.service`(古典的な常駐デーモン) |
| quory / monnie | enabled | **enabled** | **`sshd@<N>.service` の個別インスタンス** |
| authy | **disabled** | **enabled** | 同上(socket activation のみ) |

**全ホストで `sshd.service` は alias であり、実体は `ssh.service` である。** したがって素朴に
`journalctl -u sshd` を引くと、socket activation のホストでは接続ログがほぼ空で返る。
**これは本項目の起票理由そのもの**(「`journal-system` は `-p warning..err` で絞るため、
空であることは何の証明にもならない」)**と同じクラスの欠陥**で、しかも空振りしたことが
呼んだ側に分からない。

専用チェックにした理由はもう2つある。

- **3つの class は unit の持ち方が違う。** P は `case` 直書き、Q は `_is_valid_unit` の共有配列、
  G は inventory 由来の Jinja ループである。既存 enum へ混ぜると3箇所で別々の壊れ方をする。
- **class Q の unit enum は `unit-cat` と共有されている。** `sshd@*` のようなグロブを enum へ
  入れると `systemctl cat` 側が壊れる。グロブはあの enum に入れられない。

## 7.2 class ごとの実行内容(意図的に同一ではない)

| class | 実行内容 | sudo |
|---|---|---|
| Q(quory) / G(authy・monnie) | `journalctl -u ssh.service -u ssh.socket -u 'sshd@*' --since <window> -n 300 --no-pager` | 不要(`systemd-journal` グループ) |
| P(pve1 / pve2) | `sudo -n /usr/bin/journalctl -u ssh.service -u ssh.socket --since <window> -n 300 --no-pager` | **要。sudoers に1行追加** |

**チェック名・operand・契約は3 class で同一であり、R11 はそこで満たしている。** 実行内容が
割れるのは、ホストの SSH 起動方式が実際に割れているためである。**同一に揃える方を選ぶと、
socket activation のホストで空振りする。**

- **P で `sshd@*` を外すのは意図的である。** `ssh.socket` が disabled であり個別インスタンスが
  存在しない。加えて sudo の fnmatch は `*` が空白をまたぐため、引数側にグロブを持ち込むと
  許可が実質的に広がる(sudoers ファイル自身が既にこの性質を警告している)。
- **pve が socket activation へ移ったら、このチェックは盲になる。** 気づく手段は「`journal-ssh`
  が常に空で返る」ことだけである。その旨を dispatch と sudoers の両方へコメントで残した。
  直すときは `-u 'sshd@*'` を**両方**へ足し、sudoers 側ではアスタリスクを `sshd@\*` と
  エスケープすること。

## 7.3 unit 選択子を operand にしない理由

`ssh.service` / `ssh.socket` / `sshd@*` はいずれも**スクリプト内のリテラル**である。
operand は window 1つだけで、既存 enum で検証する。I-3(operand からパスを組み立てない)と
同じ理由 — 選択子を呼び手に選ばせると、上の「どれを引けばよいか」の知識が呼び手側へ移り、
**間違ったものを引いて空を得た**という失敗が再び可能になる。

## 7.4 あわせて追加 — `deployed-hash` の class Q 対応表(1件)

| name | パス |
|---|---|
| `worktree-sync` | `/usr/local/sbin/worktree-sync.sh` |

commit `58fc343` が「単独では足さず、**次に dispatch を触る機会にまとめる**」と申し送っていた件
(配備に commit → pull → Semaphore の一巡が要るため。Phase 4 D6 と同じ判断)。
パスは `unit-cat worktree-sync.service` の `ExecStart` で実測した。

**timer の生存は日次ドリフト検査が見ているが、スクリプト本体の内容は template 由来で repo 側に
期待値が無い(Tier 2)。** このハッシュは「配備物が変わったか」を追える唯一の手段である。

## 7.5 総数の更新

| class | §1〜§3 | §6 | §7 | 計 |
|---|---|---|---|---|
| Q(quory) | 20 | +4 | **+1** | **25** |
| G(authy / monnie) | +2 | +3 | **+1** | +6 |
| P(pve1 / pve2) | +2 | +3 | **+1** | +6 |

**新しく露出する語彙はゼロ。** `journalctl -u` は §1〜§3 で既に露出しており、read である。

## 7.6 配備後の実測(2026-08-03)と、この検査自身の限界

配備後、5ホストすべてで `journal-ssh 24h` が `rc=0` で実データを返すことを Coordinator が確認した
(quory / authy / pve1 / pve2 は300行上限に達し、monnie は246行)。**空で返ったホストは無い。**
pve 側は `sudo` 経由であり、sudoers の追加行も効いている。`deployed-hash worktree-sync` も sha256 を返した。

**初回の実行で、起票の原因だった `Connection reset by peer` の正体が判明した** —
OpenSSH 9.8 以降の PerSourcePenalties である(詳細は `..._023_test_result_phase4.md` の「決着」)。
**このチェックは、作った当日に作った理由を解いた。**

**限界: `-n 300` の上限に対し、調査のための接続自身が新しい行を積んで古い行を押し出す。**
実際、続けて2回叩いたところ、1回目に見えていた約6時間前の行が2回目には窓から外れていた。
**古い事象を追うときは窓を短く切る(`30m` / `1h`)ほうが確実である** — 長い窓を指定しても、
返るのは常に「直近300行」であって「その窓の全体」ではない。この性質は `journal-unit` にも同じくある。
