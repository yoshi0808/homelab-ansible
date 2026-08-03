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
| Q11 | `semaphore-query <query> <n>` | `query`: enum `recent-failed`\|`task-errors`\|`task-hosts`\|`task-output`\|`task-time`<br>`n`: `^[0-9]+$` | `homelab-semaphore-query <query> <n>` |
| Q12 | `deployed-hash <name>` | 下表 enum | `sha256sum <対応する絶対パス>` |

#### unit enum(実機で存在を確認済み。2026-08-03)

`recovery-probe.service` / `recovery-probe-sandbox.service` / `recovery-io.service` /
`homelab-incident-capture.service` / `homelab-incident-capture.timer` /
`homelab-incident-investigate.service` / `homelab-incident-investigate.timer` /
`semaphore.service` /
`ansible-cert-renew-quory.service` / `.timer` /
`ansible-authy-healthcheck.timer` / `ansible-monitoring-healthcheck.timer` /
`ansible-proxmox-healthcheck.timer` / `ansible-proxmox-hw-check.timer` / `ansible-proxmox-patch-dryrun.timer`

`status` が一括表示するのは先頭8つ(復旧パイプライン + Semaphore)に絞る。

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
