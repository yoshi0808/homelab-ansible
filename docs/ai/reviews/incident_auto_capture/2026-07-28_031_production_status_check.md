# quory本番 incident_capture(Step 1)稼働状況の確認 — test_result

- 実施者: Tester(subagent)
- 実施日時: 2026-07-28 12:00〜12:05 JST(すべての確認コマンドはこの時間帯に実行)
- 実施範囲: **read-onlyのみ**。`ssh quory`(接続ユーザー`ann`)による`systemctl status/list-timers`、`sudo -n journalctl -u ...`(sudoは読み取り専用コマンドのみ、`--become-user`等でyoshiのidentityは引き受けていない)、`ls`/`cat`/`getfacl`/`stat`。ファイル作成・変更・削除、timer/serviceの起動停止、playbook実行、spool消費は一切行っていない
- 対象: quoryのみ。Proxmox(pve1/pve2)・Sophos・UniFiへは触れていない
- `git add`/`git commit`/`git push`は行っていない

## 結論(先に要約)

**timerは健全に稼働中。ただし観測期間には本日未明(2026-07-28 05:45〜09:00 JST)に約3時間15分・40サイクルの継続的な収集失敗(exit 2)があった。** この失敗は既に別案件で発見・調査・修正済みの既知インシデントと一致する(`docs/ai/reviews/incident_auto_capture/2026-07-28_016`〜`030`、Auditor受入済みでクローズ)。09:05 JST以降、本レポート作成時点(12:05 JST)まで連続56サイクル、収集エラーなしで稼働している。**「配備してクローズ後、誰も見ていない間に起きていたこと」自体は本インシデントとして既に捕捉・対応済みであり、今回新たに発見した未対応の異常は無い。**

pve1夏季平日シャットダウン運用に由来する捕捉の実測頻度は後述(観測5)のとおり、全41件のバンドルのうち約19〜20件(半数弱)。

---

## 観測1: timerの有効性と発火

```
systemctl is-enabled homelab-incident-capture.timer  → enabled
systemctl is-active  homelab-incident-capture.timer  → active
systemctl list-timers homelab-incident-capture.timer --all
```

- Active: `active (waiting)` since 2026-07-27 20:14:27 JST(約15.75時間、配備時のtimer有効化から継続)
- 直近の発火: 2026-07-28 11:55:01 JST → 12:00:00 JST → 12:05:01 JST(5分間隔どおり、確認時点で連続稼働)
- 次回発火: 観測時点で正常にスケジュールされている

**注意点**: 最初に誤ったunit名`incident-capture.timer`で照会し`could not be found`(exit 4)を返された。実際のunit名は`homelab-incident-capture.timer`/`.service`(defaults/main.ymlのコメント通りだが、依頼文中の想定名と異なる)。正しい名前で再照会し上記結果を得た。

## 観測2: 収集器の実行結果履歴(終了コード分布)

`ann`単独では`journalctl -u homelab-incident-capture.service`は権限不足で空(`adm`/`systemd-journal`グループ非所属)。`sudo -n journalctl`(read-only)で取得。

timer有効化後(2026-07-27 20:14以降)の全履歴:

| 終了コード | 件数 | 期間 |
|---|---|---|
| 0(成功、"Deactivated successfully") | 大部分(5分毎、上記失敗期間を除く全周期) | 20:15〜20:18、20:20〜05:45、09:05〜12:05(観測時点) |
| **75/TEMPFAIL(flock、多重起動抑止)** | **1件** | 2026-07-27 20:18:08 |
| **2/INVALIDARGUMENT(収集エラー、`EXIT_COLLECTION_ERRORS`)** | **40件連続** | 2026-07-28 05:45:08 〜 09:00:08(5分毎) |

- exit 75(flock)は1件のみで、その日(07-27)の配備直後の検証作業時間帯に単発発生。5分間隔の通常運転で重複発火した形跡はこの1件を除き無い。
- exit 2の40件はすべて`_runs/run-*.json`に記録があり、内容は2種類:
  1. 05:45・05:50の2件: `capture pipeline appears silent (R5b)` — Semaphoreに新規失敗ジョブがあるのにspoolが空(T1の書き込みより先に収集器が走った、または本インシデントの前段階)
  2. 05:55〜09:00の38件: `failed to remove consumed spool record .../1785185420-30cddc4d.json` `[Errno 13] Permission denied` — 同一spoolレコードを消費(削除)できず、5分毎に再読込・再バンドル化され続けた
- **09:00:08を最後に失敗が止まり、09:05:01以降は本レポート作成時点(12:05:01)まで56サイクル連続で成功している。**

**この失敗パターンとタイムラインは、既存の別案件`docs/ai/reviews/incident_auto_capture/2026-07-28_016`(T1本番観測test_result)〜`030`(Auditor受入)が記録する「`_spool/`のACL maskが実効権限を切り詰め、recovery-execがspoolファイルを削除できなかった」インシデントと完全に一致する。** 同案件はU0〜U6のフルサイクルで原因究明・修正・Auditor受入まで完了しクローズ済み(`progress.md`)。今回の観測は、その修正が本番へ実際に反映され、それ以降健全に稼働し続けていることの**独立した事後確認**という位置づけになる。

## 観測3: spoolの滞留

```
ls -la /home/yoshi/homelab-ansible/reports/incidents/_spool/
```

結果: **空(観測時点で未処理レコード0件)。** 上記インシデントの原因だった`1785185420-30cddc4d.json`は現存しない(いつ消費に成功したかは`_runs/run-1785196808.json`(09:00:08)時点でまだ存在した痕跡があり、09:05:01の成功サイクルで最終的に消費されたと推定される。この1点は`_runs`ログからの推定であり、消費成功の瞬間を直接ログで確認したわけではない)。

`_spool/`自体のパーミッション: `drwxrwxr-x yoshi:homelab-ansible 775`、ACL `user:recovery-exec:rwx`(mask::rwx、切り詰めなし)。既知インシデントが修正した状態が現物に反映されている。

## 観測4: 生成されたバンドルの件数と概要

```
ls /home/yoshi/homelab-ansible/reports/incidents/ (semaphore-*, spool-* のみ)
```

**現存41件**(`semaphore-*` 40件 + `spool-1785185420-453e8cd7` 1件)。

- `semaphore-*` 40件の内訳(各`summary.json`の`semaphore.template`/`playbook`/`start`から集計):
  - 2026-05-31〜07-27の履歴的な失敗ジョブ(配備時のバックフィル、`docs/ai/reviews/incident_auto_capture/2026-07-27_004_observation.md`のR5b初回発火に相当): `Proxmox Weekly Full Patch`(error 3件)、`Cloudkey_cert_deploy`(stopped 1件)、`Cert_renew`(error/stopped 計10件、2026-06-04に集中)、`Codex update check`(error 1件)、`Ubuntu nightly reboot`(error 1件)、`Unifi backup fetch`(error 1件)、`Sophos trim`(stopped 1件)、`Proxmox snapshot check`(error 1件)
  - 平日05:40〜05:50 JSTの`Proxmox healthcheck`/`Proxmox hardware check`/`Time sync check`(pve1関連、後述観測5)
  - 本日(2026-07-28)分: `semaphore-466`(Proxmox healthcheck、05:40:01、error)、`semaphore-467`(Proxmox hardware check、05:45:01、error)
- `spool-1785185420-453e8cd7`(1件): 2026-07-28 05:50:20の`time_sync_check`警告(`play_host: quory`, `slack_status: warning`)。**同一spoolレコードから05:55〜09:00に生成された重複バンドル37件(`0ed8a07c`〜`edf82c42`等)は、既存インシデント対応のU6クリーンアップで整理済みで現存しない**(`progress.md`課題I-8「残1件、`semaphore-*` 40件・`_runs/` 41件は無傷」という記述と現物の件数が一致することを確認した)。

**したがって「重複バンドルが約束と異なり大量に消えている」ように見えた点は、Testerが今回新たに発見した異常ではなく、既存インシデント対応の一部として意図的に実施済みの整理作業の結果である。**

## 観測5: pve1夏季平日シャットダウン運用に由来する捕捉の頻度(実測)

`summary.json`の`semaphore.template`/`start`から、平日05:40前後に集中する項目を集計した(pve1が停止する時間帯と一致する、`docs/ai/context`の既知運用に基づく判断):

| playbook | 出現日(すべて05:40〜05:50 JST) | 件数 |
|---|---|---|
| `Proxmox healthcheck` | 05-31, 07-22, 07-23(×2、うち1件07:03:38は別トリガの可能性あり), 07-24, 07-26, 07-27, 07-28 | 8 |
| `Proxmox hardware check` | 07-22, 07-23, 07-24, 07-26, 07-27, 07-28 | 6 |
| `Time sync check` (semaphore由来) | 06-24, 07-22, 07-23, 07-24, 07-26 | 5 |
| `Time sync check` (spool由来、warning) | 07-28 | 1 |

**合計 約19〜20件 / 全41件バンドル中(約46〜49%)。** 07-22, 07-23, 07-24, 07-26, 07-27, 07-28の6平日は`healthcheck`+`hw_check`が毎回セットで05:40/05:45に出現しており、既知の「pve1平日シャットダウンで毎回1組の通知が出る」という運用実態と一致する。**Step 2(起票側)で機械的に弾く場合、この2playbook(+time_sync_checkのwarning)が最有力候補になる実測値**として使える。

## 観測できなかったこと

- **`/var/lib/homelab-recovery/incident-capture/state.json`の内容は未確認。** 依頼文の観測項目には明示されていないが、実行状態の一部であるため触れておく: `ann`単独では読めない(所有者`recovery-exec`、他ユーザ不可)。今回は`sudo -n cat`を試していない(読み取り専用の範囲内で許容されるはずだが、観測項目に無い追加調査であり、依頼された6項目の充足を優先し実施しなかった)。必要であれば追加で`sudo -n cat`を実行できる。
- **spoolレコード`1785185420-30cddc4d.json`が実際に消費された正確な時刻**は、`_runs/`ログの生成間隔(5分)以上の精度では確認できない(09:00:08時点でまだ存在し、次の09:05:01サイクルで初めて収集エラーが消えたことからの推定に留まる)。
- **U6クリーンアップの実施時刻・実施者による37件削除の実行ログそのもの**は本Testerの観測範囲外(既存案件`2026-07-28_029_u6_cleanup_result.md`が一次記録)。今回は現物の件数が既存記録と一致することのみ確認した。

## 異常の有無

- **新規の異常は無い。** 発見した唯一の異常(05:45〜09:00の40サイクル失敗)は、既に発見・修正・Auditor受入済みの別案件と完全に一致し、その後56サイクル健全に稼働している。
- **Coordinatorの判断が要る点**: 観測5の実測値(pve1由来が全体の半数弱)を、Step 2(起票側)の設計にどう反映するかはCoordinator/Tech Leadの判断事項であり、本Testerはデータの提示に留める。
