# T1(証拠捕捉)quory本番実行の観測 — test_result

- 対象Watch項目: `docs/ai/status.md` 「T1(証拠捕捉)のquoryでの初回実行」および「`_spool/`のグループ所有がroot」
- 実施者: Tester(subagent)
- 実施日: 2026-07-28(平日、pve1夏季平日シャットダウン運用により停止中 — 発火条件を満たす)
- 実施範囲: **読み取り専用のみ**。`ansible quory -m command -a "..."`(必要に応じ`-b`)によるread-only参照。非冪等操作、設定変更、`git`操作は一切行っていない。

## 実行コマンドと実測結果(Q1〜Q6)

### Q1: `_spool/`の現況

```
ansible quory -m command -a "sh -c 'ls -la .../reports/incidents/_spool/'"
```
結果: `1785185420-30cddc4d.json` 1件のみ存在(mtime 2026-07-28 05:50)。中身:
```json
{
  "controller": "quory", "id": "1785185420-30cddc4d",
  "play_host": "quory", "play_name": "Time sync check (per-host NTP self-report)",
  "slack_status": "warning", "slack_title": "[time_sync_check] WARNING",
  "tester_mode": false, "written_at": "2026-07-28T05:50:20+09:00"
}
```
`controller: "quory"` かつ `tester_mode: false` — **本番identityでの実行の直接証拠**。

### Q2: バンドルディレクトリ

`reports/incidents/` 配下に `semaphore-*`(38件、既存)、`spool-*`(11件、今回新規)が存在。**収集器がspoolを処理した証拠として成立**。ただし後述(新規発見)のとおり、この11件はすべて同一spoolレコード(id `1785185420-30cddc4d`)の重複バンドルだった。

### Q3: 収集器の稼働状況

- `systemctl list-timers homelab-incident-capture.timer`: 5分間隔で稼働中、`enabled`。
- `systemctl status homelab-incident-capture.service`: **`Active: failed (Result: exit-code)`**。05:45以降のすべてのサイクルで`status=2/INVALIDARGUMENT`(collector側`EXIT_COLLECTION_ERRORS`)。05:45より前は正常終了(`Deactivated successfully`)。
- `journalctl -u homelab-incident-capture --since '24 hours ago'`(`-b`必要、ann単独では権限不足で空)。05:45から06:45まで5分毎に一貫して失敗。
- `_runs/run-*.json`(14件)の`collection_errors`を確認:
  - `run-1785148955.json`(07-27 19:42、初回backfill): R5b発火「Semaphore recorded 38 new failed job(s)...but spool contained zero spool records」→38件全てSemaphore単独バンドル化。
  - `run-1785185108.json`(05:45、task 466起因): 同様のR5b「1 new failed job(s) since 461, spool zero」。
  - `run-1785185407.json`(05:50、task 467起因): 同様のR5b「1 new failed job(s) since 466, spool zero」。
  - `run-1785185708.json`(05:55)以降11件: **すべて同一内容**「`failed to remove consumed spool record .../1785185420-30cddc4d.json`」「`[Errno 13] Permission denied`」。

### Q4: `/var/lib/homelab-recovery/incident-capture/state.json`

`ann`単独では権限不足(`Permission denied`)、`-b`(become)で読めた:
```json
{"last_failed_task_id": 467}
```
最後に処理したSemaphore task idは467(Proxmox hardware check、05:45エラー)。

### Q5: owner:group:mode

```
ansible quory -b -m command -a "getfacl .../reports/incidents/_spool"
```
- `reports/incidents/` 本体: `yoshi:homelab-ansible`(既知)。
- `_spool/`: **`owner=yoshi group=homelab-ansible mode=0755`**。W6で追加された`group: homelab-ansible`の明示は**現物に反映済み**。
- ただしACL詳細: `user:recovery-exec:rwx #effective:r-x`(**`mask::r-x`が名前付きACEを実効的に切り詰めている**)。→ 後述の新規発見の直接原因。

**判定: グループ所有のWatch項目は解消済み。** group=rootだった旧状態は現在再現せず、roleの修正が実環境へ反映されている。

### Q6: 通知の裏取り(`homelab-semaphore-query`、`-b`必要)

```
ansible quory -b -m command -a "/usr/local/bin/homelab-semaphore-query recent-failed 30"
```
直近24時間以内に該当:
```
467|SAFE: Proxmox hardware check|playbooks/proxmox_hw_check.yml|error|2026-07-27 20:45:01
466|SAFE: Proxmox healthcheck|playbooks/proxmox_healthcheck.yml|error|2026-07-27 20:40:01
```
(UTC表記。JSTでは05:45/05:40)。**Semaphoreジョブは実際にerrorで終了しており、発火条件は満たされていた。**

`playbooks/proxmox_hw_check.yml`のtester-gateコメント(1-2行目)を確認: 「**通知経路はない**」と明記。→ task 467についてはそもそもT1の対象外(設計上notify.ymlを呼ばない)。
`playbooks/proxmox_healthcheck.yml`は通知経路を持つ(`roles/proxmox_healthcheck/tasks/main.yml:226-231`、WARNING/CRITICAL時に`common_slack/tasks/notify.yml`をinclude)。task 466がこの経路を実際に通ったか(pve1到達不能がnotifyへ到達する前の致命的失敗を起こした可能性)までは、コード読解の深追いが観測の範囲を超えるため**未確認・未実施**として残す。

## 判定

### Watch項目1: T1のquoryでの初回実行

**本番実行が確認できた。** Q1の`_spool/`レコード(`controller: "quory"`, `tester_mode: false`, `play_name: "Time sync check..."`)が直接証拠。これはansy実測やコード構造からの推論ではなく、**quory上で生成された実物**。時刻(05:50:20 JST)は`homelab-semaphore-query`が示す実ジョブ稼働時間帯と整合する。

したがって「本番identityでの実行は未確認」という従来の限界は解消し、Watch項目はクローズしてよい。

### Watch項目2: `_spool/`のグループ所有

**解消済み。** `group: homelab-ansible`が現物に反映されている。roleを再実行した形跡(Q3のjournalの初回発火が2026-07-27 19:42のW6完了直後付近から始まっている)と整合的。

## 未実施・観測できなかった項目

- **Proxmox healthcheck(task 466)がnotify.ymlへ実際に到達したかどうか**: コード上の分岐(pve1到達不能時に途中でfatalし notify タスクへ到達しない経路があるか)を最後まで追い切れていない。読み取り専用の範囲では`_runs/`にplay_name「Proxmox healthcheck」を含むレコードが一件もないことしか確認できず、「T1が沈黙した」のか「そもそもnotifyへ到達しなかった」のかを本タスクの範囲では切り分けられなかった。
- `journalctl`は`ann`単独権限では空("No entries")。`-b`(become、root委任)で読めた。これはCoordinator提示の安全境界内(read-only)だが、報告の透明性のため明記する。
- `git status`によるquory作業ツリーの直接確認は行っていない(別Watch項目により原理的に不可、既知)。

## 新規発見(依頼範囲外だが観測中に判明した現況、残存リスクとして明示)

**spoolファイルの消費(削除)が構造的に失敗し続けている。**

- 事実: `1785185420-30cddc4d.json`は05:50に書かれて以降、**11回連続(05:55〜06:45、5分毎)** 同一内容のまま再バンドル化されている(`spool-1785185420-*`が11個、すべて同じ`id`/`written_at`の同一レコードを含む)。
- 直接原因(`_runs/run-*.json`のcollection_errorsに実測): `os.remove()`が`[Errno 13] Permission denied`で失敗し続けている。
- 根本原因(`getfacl`で実測): `_spool/`のACLは`user:recovery-exec:rwx`という名前付きエントリを持つが、`mask::r-x`が実効権限を`r-x`へ切り詰めている(`#effective:r-x`とgetfaclが明示)。ディレクトリからのunlinkにはディレクトリ自体へのwrite権限が要るため、recovery-execは`_spool/`内のファイルを削除できない。
- 影響: (1) systemdサービスが5分毎に`failed`状態を報告し続ける(現在進行中)。(2) 同一通知のバンドルが際限なく重複生成される(ディスク消費、`_runs/`の肥大)。(3) 実害としての情報欠落は無い(重複バンドルの中身自体は正しい)が、**運用上のノイズと将来のディスク圧迫リスク**。
- これはコード側の設計コメント(`incident-capture-collector.py` 51-70行)が想定していた「ディレクトリへの書込権があれば所有者に関係なくunlinkできる」という前提が、**maskによって実際には成立していない**ことを示す。W6の`incident_capture` roleが`_spool/`のACLをどう設定しているか(default ACLのみでmaskを明示していないなど)の確認と修正はTech Lead/Implementerの領分であり、Testerはここで停止し報告する。

**この発見はWatch項目の判定そのものには影響しない**(T1自体は正しく動作し、spoolレコードは正しく書かれている。壊れているのは収集器側の後始末)が、放置すると収集器が恒常的に`failed`のまま運用されることになるため、次のアクションとしてTech Leadへのエスカレーションを推奨する。
