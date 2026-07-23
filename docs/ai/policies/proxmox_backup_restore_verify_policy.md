# Proxmox Backup Restore Verify Policy v1.0

作成日: 2026-06-14
版: v1.0
対象: コアVM（Sophos / authy / monnie 等、`verify` タグ付きVM）の月次リストア検証

参照:

- docs/ai/prompts/core.md
- docs/ai/prompts/proxmox_patch_policy.md（prefer* / hacritical タグ、cluster resources、group_vars/proxmox.yml の接続情報）

---

## 1. 目的

コアVMの vzdump バックアップが、実際にリストアして起動できることを月次で検証する。
「バックアップが取れているつもりで壊れていた」（サイレント破損）を、本番に影響を与えずに
検出することが目的。

検証は使い捨ての VMID 999 へリストアして行い、本番VMには config 読み取り以外で触れない。

---

## 2. 対象と実行

| 項目 | 内容 |
|---|---|
| 検証対象VM | `verify` タグを持つVMのうち、月次ローテーションで当たった1台 |
| リストア先VMID | **999 固定**（検証専用・使い捨て） |
| 実行ノード | 対象VMの `prefer<node>` タグで決まるノード（例: authy/Sophos → pve1、monnie → pve2） |
| 実行元 | quory（本番・月次スケジュール）/ ansy（開発・手動 CLI） |
| バックアップ元 | vzdump NFS ストレージ（Synology、PVE の dump フォルダ）。未指定時は NFS かつ content に backup を含むストレージを自動検出 |
| リストア先ストレージ | `local-zfs`（本 homelab の全VM） |
| 安全度 | controlled apply（999 の作成・起動・削除を伴う。本番VMは reboot/migrate しない） |

実装ファイル:

- playbooks/proxmox_backup_restore_verify.yml（2プレイ: 決定 → 検証）
- roles/proxmox_backup_restore_verify/（tasks/main.yml, defaults/main.yml）

inventory / group_vars / host_vars は変更しない（対象はタグで動的決定）。

## 対応するPlaybook

| Playbook | 役割 |
|---|---|
| `proxmox_backup_restore_verify.yml` | コアVMのvzdumpバックアップを月次でVMID 999へリストアし、実際に起動できることを検証する（2プレイ: 対象VM決定 → 検証）。 |

---

## 3. 対象VMの決定（Play 1, run_once on proxmox）

cluster resources（`pvesh get /cluster/resources`）から決定する。Ansible 側に対象VMリストを
持たず、Proxmox 側のタグ付けだけで増減に対応する。

### 3.1 月次ローテーション

1. `verify` タグを持つ QEMU VM を列挙する。
2. vmid 昇順でソートし、決定的な順序リストを得る。
3. `(現在の月 - 1) % リスト長` でインデックスを決め、今月の対象VMを確定する。

VMの増減は Proxmox のタグ付けのみで対応でき、インデックスは自動で振り直される。
検証履歴の永続化は不要（月番号固定方式のため）。

### 3.2 手動バイパス

`-e target_vmid=<id>` が渡された場合はローテーションを無視し、その VMID を直接対象にする
（開発・手動用）。存在しなければ fail。

### 3.3 リストア先ノードと agent 期待レベル

- リストア先ノードは対象VMの `prefer<node>` タグから決定する（無ければ fail）。
- 対象VMの config（`pvesh .../config`、read-only）の `agent` 設定で期待レベルを決める。
  `agent == '1'` または `enabled=1` を含むなら agent 期待、それ以外は agent 無し。
- 決定結果は `add_host` で動的グループ `brv_restore_targets` に渡し、Play 2 がその
  ノード上で role を実行する（`hosts:` を hostvars で動的指定すると syntax-check が
  パース時に失敗するため、動的グループを使う）。

---

## 4. ライフサイクル（Play 2 / role, block・rescue・always）

become: true（root）で実行する（NFS のアクセス権が root に絞られているため）。

```text
Phase -1 最小ロック取得（§6）
Phase 0  999 残骸ガード（既存なら触れず critical 通知して中断）
Phase 1  最新 vzdump バックアップ特定（ctime 最新※）
Phase 2  qmrestore で 999 へリストア → 999 description に owner トークン刻印
Phase 3  NIC 切断（net デバイス削除、IP は指定しない）
Phase 4  qm start で 999 起動
Phase 5  正常性判定（§5）
rescue   失敗を捕捉
always   999 cleanup（§7）→ ロック解放 → レポート保存 → Slack 通知 → 結果に応じ再 fail
```
※バックアップ作成時刻（storage content API の ctime フィールド）が最新

shell / Ansible の責務分離: qmrestore / qm set / start / stop / destroy / guest cmd は
Ansible tasks 側で実行条件を明示制御する。OK/NG 判定と fail 制御も Ansible tasks 側に置く。
専用 shell スクリプトは持たない（core.md §7 / §9）。

---

## 5. 正常性判定

期待レベル（どこまで要求するか）は本番VMの agent 設定で決まる。実測は 999 を起動して測る。
判定は実測が期待レベルに届いているか。

| VM種別 | 合格基準 | 手段 |
|---|---|---|
| agent 対応（agent:1） | osinfo 取得成功 | `qm agent 999 get-osinfo` をポーリング |
| agent 無し（未設定/0） | 起動後 N 秒経過してもなお running | `qm status` |

- agent 無しVMは running 継続のみで合格扱い（Sophos を特別扱いしない）。
- agent 無しの判定 block は分離してあり、次フェーズで serial0 コンソール文字列マッチへ
  差し替えられる。

---

## 6. ロック方針（3者合意・最小ガード）

### 6.1 位置づけ

同時実行は **運用で禁止** する。ロックはその補助の最小ガードであり、完全な分散排他では
ない。

- 月次は quory から固定時刻の単一スケジュール。
- 手動（ansy）は、人が月次と重複しないことを確認して実行する。

### 6.2 実装

- 公式の pmxcfs ロック（`/etc/pve/priv/lock/brv-restore-verify` への atomic `mkdir`）で
  取得する。既存なら即 fail・通知・非ゼロ終了（待機しない）。
- ロックディレクトリは **空** に保つ。これにより pmxcfs 標準の 120秒陳腐化回収が効き、
  クラッシュした実行のロックは手動削除なしで自動回収される。
- refresher / 期限更新 / 生存監視 / 孤児管理は **持たない**（最小化）。
- 解放は空ディレクトリの `rmdir`（取得した場合のみ）。

### 6.3 本番への危害防止（ロックに依存しない）

破壊的操作の安全は、ロックではなく以下で担保する。

- destroy 対象を 999 に固定する hard assert（999 以外は絶対に destroy しない）。
- 開始前 999 残骸ガード（既存 999 には触れない。残骸検出時は critical 通知して中断）。
- 999 description への一意 owner トークン刻印。cleanup では、トークンが自分のもの、または
  未刻印（＝同時実行禁止前提下で自分の途中失敗）の場合のみ destroy し、別実行のトークンが
  あれば触れない（cheap defence in depth）。

### 6.4 受容した残余リスク

ロック保持が 120秒を超える窓で、低頻度の同時実行が万一重なった場合、最悪で使い捨て 999 の
検証が1サイクル無駄になる。**本番影響はない。** これを運用判断として受容する
（docs/ai/reviews/proxmox_backup_restore_verify/2026-06-14_012_final.md）。

---

## 7. cleanup と終了判定（always）

- cleanup は「リストアを試行した」かつ「開始前残骸でない」場合のみ実行する。
- live state を再取得し、999 が現存し所有判定が真なら `qm stop`（best-effort）→ `qm destroy
  999 --purge 1`。
- destroy に失敗して 999 が残った場合は `cleanup_ok=false`。
- 終了コードは、検証失敗（rescue 捕捉）または cleanup 失敗のいずれかで非ゼロにする。

---

## 8. 通知

roles/common_slack/tasks/notify.yml を include_tasks で呼ぶ（best-effort）。優先順位は
critical > error > ok。

| 状況 | チャンネル | status |
|---|---|---|
| 検証 OK（期待レベル達成） | info | ok |
| 検証 NG（リストア失敗 / 正常性未達） | alerts | error |
| 999 残骸検出 or destroy 失敗 | alerts | critical |

レポートは `{{ reports_base_dir }}/proxmox-backup-verify/` に JSON 保存する。

---

## 9. 制約

- 本番VM（既存 VMID）には config 読み取り以外で触らない。
- 秘密情報を扱わない。
- IP リテラルをファイルに書かない（core.md §3）。NIC 切断は net デバイス削除で行い、IP を
  指定しない。
- read-only / 変更系の区別: 変更系。999 の作成・起動・停止・削除を行う。本番VMは config
  読み取りのみ。

---

## 10. スコープ

### 初回実装（実装済み）

ローテーション選定 / 最新バックアップ特定 + qmrestore / NIC 切断起動 / 正常性判定 /
999 の destroy + 安全装置 / 最小ロック / Slack 通知。

### 次フェーズ（除外）

- agent 無しVM（Sophos）の serial0 コンソール文字列マッチ（判定 block は分離済み）。
- バックアップ鮮度チェック（別 playbook、取得側整備後）。
- 検証履歴の永続化（月番号固定方式のため不要）。

---

## 11. 今後のレビュー観点（合意）

ロック所有権の深掘りより、本質に重心を置く。

- 最新かつ正しい対象VMのバックアップを選べるか
- NIC 切断後に起動して有効な正常性判定ができるか
- destroy 対象が構造的に 999 に固定されているか
- 失敗時に 999 を安全に処理できるか
- Slack 通知 / レポート / 終了コードが実結果と一致するか
- 本番VMへ変更操作が及ばないか
