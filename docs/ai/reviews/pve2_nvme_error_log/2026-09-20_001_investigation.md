# pve2のNVMe error-log増加は実害か — 調査記録

状態: **クローズ**(2026-09-20)。**実害を示す観測は無い。**

## 1. 発端

2026-09の月次点検(Semaphoreジョブ #1111)が `[要確認] pve2: NVMe error-logの累積数が増加しました` を出した。表示は正しく、事象が問題かどうかが未判定だった。

## 2. この指標が何か

`roles/proxmox_storage_monthly/files/storage_collect.py:53` が `nvme smart-log <namespace> -o json` を実行し、そのJSONの **`num_err_log_entries`** を拾っている(`module_utils/storage_monthly.py:7` の `COUNTERS`)。判定は同ファイル131行で、**前月より増えていればWARNING**を出す。閾値ではなく増分そのものが条件である。

**この値はNVMeコントローラのError Information Logに積まれたエントリの累計であり、コマンドがエラーstatusで完了したときに増える。媒体の異常を数えるカウンタではない**(それは別フィールドの `media_errors`)。

## 3. 観測(OPREQ経由、2026-09-20)

開発側はpve2へ到達手段を持たず、`report-list proxmox-storage-monthly` もACLで拒否される。そのためquory側Operatorへread-onlyの情報収集を依頼した(OPREQ `req-20260920T184749+0900-...` / OPRES `req-20260920T194922+0900-...`)。

| 観測 | 値 |
|---|---|
| error-log のentry 0(唯一の非ゼロ) | `error_count=243`、`status_field=0x2002`、`lba=0`、`cmdid=0x14`、`nsid=0`、`opcode=0` |
| `0x2002` のデコード | **Invalid Field in Command**(予約値または未対応の値が定義済みフィールドに入っていた) |
| entry 1〜63 | すべてゼロ。**この個体は直近1件の中身しか保持していない** |
| smart-log | `num_err_log_entries=243`、`media_errors=0`、`critical_warning=0`、`avail_spare=100`、`percent_used=1` |

推移は 2026-09-11 17:17=239(baseline) → 09-12 01:12=239 → 09-15 08:00=241(+2、WARNINGが出た回) → 09-20=243(+2)。

## 4. 判断

**実害を示す観測は無い。** 記録されていたのはコマンドが拒否された記録であり、`media_errors` は生涯0である。これはerror-logとは独立のカウンタで、媒体の読み書きで実エラーが起きていないことの裏づけになる。

**増分は月次収集の実行と同期していない**(3日で+2、5日で+2)。**収集そのものが発生源という線は消えた。**

## 5. 確かめていないこと

- **直近1件の中身しか見えていないため、243件すべてが同じ種類とは言えない。**
- **発行元のコマンドは特定できない。** error-log上の `opcode` が0であり、特定するにはトレースを仕掛ける話になる。
- 09-15以降の+2が同じコマンドの再発か別物かは未確認。

## 6. 検査を変えなかった理由(Coordinator判断、Yoshinobu了承)

本検査は増分そのものを条件にしているため、この原因が続く限り毎月WARNINGが出る。条件を変える案(`media_errors` / `critical_warning` の変化と直近entryのstatus種別で分ける)は検討したが、**採らない。** `nvme error-log` の収集を本番の収集処理へ足すことになり、得るものが警告文の静穏化しかない。判定が要るのは年に数回で、そのとき本記録と同じ読み方をすれば済む。

増え続けるかどうかは月次点検が毎月見ている。
