# implement: Batch 2(7 Policy)から経緯・根拠を落とす

正本: `docs/ai/reviews/norm_docs_rationale_removal_round3/2026-08-02_001_requirement.md`
先行: `2026-08-02_002_implement_batch1.md`(Batch 1。判断は参考にしたが、独立に本文を突合して判定した)

## 変更したファイル

| ファイル | 種別 |
|---|---|
| `docs/ai/policies/incident_capture_policy.md` | 変更(未staged) |
| `docs/ai/policies/ansible_test_safety_policy.md` | 変更(未staged) |
| `docs/ai/policies/time_sync_check_policy.md` | 変更(未staged) |
| `docs/ai/policies/unifi_backup_fetch_policy.md` | 変更(未staged) |
| `docs/ai/policies/proxmox_backup_restore_verify_policy.md` | 変更(未staged) |
| `docs/ai/policies/cert_renew_policy.md` | **変更なし**(下記参照) |
| `docs/ai/policies/autonomous_recovery_policy.md` | 変更(未staged) |

`cert_renew_policy.md`は本文の日付が1件のみで、その1件(`docs/ai/reviews/cert_renew_unreachable_node/2026-08-01_001_requirement.md`への「正本とする」ポインタ)が§5「残す」列(行き先・保存先・正本の指定)かつAC1の「経緯でない日付(実在ファイル名)」の両方に該当したため、編集不要と判断し触れていない。

指定の7本以外は変更していない。着手前から変更があった`docs/ai/context-classification.md`・`docs/ai/memory-classification.md`・`docs/ai/role-context-matrix.md`・`docs/ai/status.md`・`docs/ai/reviews/norm_docs_rationale_removal_round2/`配下・Batch 1が変更した`proxmox_operations_policy.md`/`log_observability_policy.md`は、着手前後で`git status --short`を突合し変化がないことを確認した(いずれも他者の変更であり触れていない)。

## 要件充足状況

| ID | 状態 | 備考 |
|---|---|---|
| R1 | 充足 | §5「落とす」列に該当する記述を本文から除去した。詳細はAC2節の突合 |
| R2 | 該当なし(受け皿確認は実施済み) | 落とした断片はすべて、(a)本文の他の場所に既に現在の規則として存在している、(b)各Policy自身の「変更履歴」節に既に記録されている、(c)`## 9. 参照`等の既存参照リストに同一ファイルが残る、のいずれかで受け皿を確認した。新設を要した箇所はない |
| R3 | 該当なし | Batch 2の7本の本文に、新たに退番すべきPolicy IDは無かった(既存の退番記録にも触れていない) |
| R4 | 充足 | 見出しに埋め込まれた日付・版注記は本文中に無かった(全見出しをgrep確認、ヒット0件)。変更履歴節に構造的に含まれる見出し(例: `unifi_backup_fetch_policy.md`の`### 12. 実機検証状況（2026-06-15, pve1）`)は非ゴール「変更履歴節を書き換えない」により対象外とした |
| R5 | 充足(下記) | `ubuntu_vm_patch_policy.md` / `cert_renew_cloudkey_policy.md`は根拠への参照の有無だけ確認。本文は変更していない |
| R6 | 充足 | `scripts/check-doc-consistency.py`(check3、内部リンク切れ検査、90件比較)がOK。`incident_capture_policy.md`の`## 9. 参照`リストは未編集のまま残り、そこが指す実ファイルは全て実在確認済み(Batch1のR2確認結果を踏襲) |

## R5の確認結果

```
grep -n "docs/ai/memory/lessons\|docs/ai/memory/incidents\|docs/ai/reviews\|docs/ai/adr" \
  docs/ai/policies/ubuntu_vm_patch_policy.md docs/ai/policies/cert_renew_cloudkey_policy.md
```
ヒット0件。両ファイルとも`lessons/` `reviews/` `incidents/` `adr/`への参照を一切持たない(requirement §1の表と一致、本文の日付も0件)。本文は変更していない。

## ファイルごとの判定根拠

### incident_capture_policy.md(本文の日付6件 → 5件除去・1件維持)

- 冒頭「状態:」行の`(2026-07-28作成・...)`から作成日を除去(状態・承認・改訂権限の記述は維持)。受け皿は「変更履歴」2026-07-28行(新規作成)。
- 「このPolicyが存在する理由」段落(2026-07-27〜28の経緯説明)を全文除去。同段落は「変更履歴」2026-07-28行に要旨がほぼそのまま既存。
- IC-004: `docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md` D4への根拠引用を除去。同ファイルは`## 9. 参照`(未編集のまま残置)に既に列挙されており、規則文自体(quoryで捕捉・ansyに担わせない、とその理由)は独立して残っている。
- IC-007: `(2026-07-31 Yoshinobu決定。2026-07-28の「事象ごとにLLMを起動しない」を改める)`を除去。受け皿は「変更履歴」2026-07-31行(一次調査の段を新設、IC-007の改訂を明記)。
- IC-033: `(2026-07-28 Yoshinobu決定)`を除去。受け皿は「変更履歴」2026-07-28行(IC-033を追加)。
- **維持**: `## 9. 参照`内の`docs/ai/reviews/incident_auto_capture/2026-07-27_001_design_agreement.md`(D1〜D7)。AC1の「経緯でない日付(実在ファイル名)」の例外に該当する書誌情報であり、書き換えていない。ファイル実在を確認済み。

### ansible_test_safety_policy.md(本文の日付5件 → 5件除去)

- 冒頭リード文から`旧docs/ai/prompts/core.md §18から移設した(2026-07-26)。`を除去(受け皿: 「変更履歴」2026-07-06〜07行・2026-07-26行)。
- TS-030: `(2026-07-31 Incident: subagentが--check付きで実配備した)`を除去(受け皿: `docs/ai/memory/incidents/2026-07-31_subagent-unintended-deploy-risk-accepted-check.md` — 実在確認済み。「変更履歴」2026-07-31行にもTS-030新設の記録あり)。
- TS-033: `(2026-07-31、同一案件のバッチ間で実際に発生した)`を除去(受け皿: 「変更履歴」2026-07-31行、TS-033新設の記録)。
- TS-029: `この決定は2026-07-06の分類設計時に確認され、`を除去し、後続の事実文「現在もリポジトリ内に該当実装は存在しない」は維持(§5「実測の日付注記は落とす/事実と規則は残す」に対応)。
- TS-036: `(2026-07-31、roles/cloudkey_cert_deploy/tasks/main.ymlが...実例)`を除去(受け皿: 「変更履歴」2026-07-31行、TS-036新設の記録に同一実例が既存)。

### time_sync_check_policy.md(本文の日付3件 → 3件除去)

- TIME-001: SSH方式検討からself-report方式へ転換した経緯段落(`docs/ai/reviews/time_sync_check/2026-06-23_006_implement.md`への「経緯:」引用付き)を全文除去。現行方式のルールは直前の段落に既に独立して存在し、受け皿は引用先ファイル自身(実在確認済み)。
- TIME-007: `（2026-06-25実施: ntp.nict.jp/ntp.jst.mfeed.ad.jp/quory.internal）`を除去。この値スナップショットは後続段落(ntp_server_3をIPへ変更)によって既に一部陳腐化しており、現在値の表現としては後続段落が正となるため、日付だけでなく値ごと落とした。
- TIME-007: 続く段落から`2026-07-16、`と「〜事象が判明した」の経緯枠組みを除去し、「busybox ntpdはNXDOMAIN応答をhard failureとして扱い失敗する」「ntp_server_3はIPアドレスをGUI経由で登録する」という現在も有効な事実・規則へ言い換えた。**この言い換えは文の時制・接続を変えたが、規則そのもの(IPアドレスで登録する/quory.internalにしない)は変えていない** — 独立レビューでの確認を推奨する(下記「未解決事項」参照)。

### unifi_backup_fetch_policy.md(本文の日付1件 → 1件除去)

- 「実機（CloudKey Gen2 Plus, 2026-06-15）ではログイン応答に両ヘッダーが返り」から日付のみ除去。CSRF優先順位の規則自体(直前の箇条書き)、実機確認の事実は維持。

### proxmox_backup_restore_verify_policy.md(本文の日付1件 → 1件除去)

- 「この分類自体はYoshinobuが判断済み(2026-07-06)であり」から日付のみ除去。規則(monthly実行のたびに個別の実行判断を必要としない)は維持。
- **観察(編集対象外)**: `## 8. 変更履歴`見出し直下、テーブルより前にBRV-075(`<!-- BRV-075 -->`付きの実質的な規則文)が置かれている。日付を含まずrequirement対象外のため触れていないが、構造上「変更履歴」節に規則が混在している。参考情報として記載する。

### cert_renew_policy.md(本文の日付1件 → 変更なし)

- 唯一のヒットは「技術的背景(...)は`docs/ai/reviews/cert_renew_unreachable_node/2026-08-01_001_requirement.md` §1を正本とする。」。§5「残す」列(行き先・保存先・正本の指定)に直接該当し、AC1の実在ファイル名例外にも該当するため、無編集とした。

### autonomous_recovery_policy.md(本文の日付1件 → 1件除去)

- 「根拠は`docs/ai/memory/incidents/2026-07-29_global-monitoring-pause-left-on-8-days.md`(8日間の未検出)、」を除去。「実装は`playbooks/recovery_monitoring_check.yml`」「案件記録は`docs/ai/reviews/recovery_pause_daily_check/`」(いずれも§5「残す」列=行き先の指定)は維持。受け皿は「変更履歴」2026-08-01行(AR-103新設の記録に同一の`docs/ai/memory/incidents/...`引用が既存)。

## 判断を求めて報告する事項

**無い。** 規則の意味が変わる編集が必要と判断した箇所、受け皿が存在せず新設が要ると判断した箇所は発生しなかった。

ただし1点、境界線上だったため明記する。`time_sync_check_policy.md` TIME-007の言い換え(上記参照)は、他ファイルの「日付だけを機械的に外す」編集より踏み込んで、経緯的な文(「〜事象が判明した」)を現在形の事実文へ書き直した。規則(IPアドレスで登録する)自体は変更していないと判断したが、**文体の書き換えを伴う点で他の6箇所より判断の幅が大きい**。実施はしたが、Reviewerの確認を推奨する。

## AC別の自己検証

### AC1(変更履歴を除いた本文の日付が0件、経緯でない日付は書き換えず報告)— 確認済み

```
incident_capture_policy.md:              2件 (## 9. 参照内の実在ファイル名、書き換えず維持)
ansible_test_safety_policy.md:           0件
time_sync_check_policy.md:               0件
unifi_backup_fetch_policy.md:            0件
proxmox_backup_restore_verify_policy.md: 0件
cert_renew_policy.md:                    1件 (正本ポインタ内の実在ファイル名、書き換えず維持)
autonomous_recovery_policy.md:           0件
```
(`awk`で各ファイルの最初の`## N. 変更履歴`見出し行の手前までを本文とみなし、`2026-`をgrepして測定。`unifi_backup_fetch_policy.md`は`## 8. 変更履歴`見出し配下に構造的にネストする`### 12. 実機検証状況`等のサブ見出しも本文から除外している — この扱いはrequirement §1の実測件数(1件)と一致することで裏付けた)

### AC2(改訂前後の逐行突合、許可・禁止・停止条件が1つも変わっていない、Policy IDも失われていない)— 確認済み

`git diff`を6ファイル分すべて全文読み、削除・変更した全断片を上記「ファイルごとの判定根拠」節で分類した。

- 削除したのはすべて「作成日・改訂注記・実測日付・経緯段落・判断日付の引用」であり、いずれの箇所も**直前・直後に規則本文が独立して存在する**か、**規則本文自体は変更せず日付だけを除去した**かのいずれかである。
- Policy ID(IC- / TS- / TIME- / UNIFI- / BRV- / AR-)はすべて残存している。新規の退番・新設は無い。
- 唯一「規則の表現」に手を入れたのは`time_sync_check_policy.md` TIME-007の言い換えで、上記「判断を求めて報告する事項」に明記した。規則の中身(quory.internalでなくIPアドレスをGUI経由で登録する)は変えていない。

**結論**: 7ファイルとも、削除・変更したのは経緯・根拠・日付・引用のみであり、許可・禁止・停止条件は改訂前と同一である。Policy IDも1件も失われていない。

### AC3(退番の記録が「変更履歴」節にすべて含まれている)— 該当なし

Batch 2の7本の本文に、新たに退番すべきPolicy IDは無かった。既存の退番記録(他ファイルのもの)にも触れていない。

### AC4(§5「残す」列の行き先・保存先・正本の指定がすべて残っている)— 確認済み

```
grep -n "正本\|案件記録\|受け皿" 7ファイル
```
- `incident_capture_policy.md`: `## 9. 参照`(D1〜D7を含む全リスト)は無編集。IC-032の「対応の記録の正本は`docs/ai/memory/incidents/`」等は無編集。
- `ansible_test_safety_policy.md`: AR-069相当の正本記述(該当なし、TS側にはこの型の記述元々少ない)。
- `cert_renew_policy.md`: 「`docs/ai/reviews/cert_renew_unreachable_node/2026-08-01_001_requirement.md` §1を正本とする」は無編集(そもそも本ファイル自体を変更していない)。
- `autonomous_recovery_policy.md`: 「実装は`playbooks/recovery_monitoring_check.yml`」「案件記録は`docs/ai/reviews/recovery_pause_daily_check/`」は維持。
- 他ファイルも同様に、行き先・保存先の指定は全て無編集で残存している(上記「ファイルごとの判定根拠」参照)。

### AC5(`check-doc-consistency.py`・`git-pre-commit-check.sh`がOK、宙ぶらりん参照が無い)— 確認済み(隔離コピー経由)

Implementerは`git add`を行えないため、`/tmp/claude-1000/.../scratchpad/repo_check_copy_batch2`へリポジトリ全体を`cp -r`し、そのコピー内でのみ`git add -A`して検証した(実リポジトリのstaging状態には触れていない。検証後にコピーは削除済み)。

```
[check-doc-consistency.py]
[check1] OK (98 compared)
[check2] OK (8 compared)
[check3] OK (90 compared)
exit=0

[git-pre-commit-check.sh]
gitleaks: no leaks found
[tester-gate-lint] OK (49 playbooks)
[check1] OK / [check2] OK / [check3] OK
[pre-commit] OK
exit=0
```

## 非ゴールの遵守

- 許可・禁止・停止条件は変更していない(AC2の突合で確認。TIME-007の言い換え1件のみ文体変更を伴うが規則の中身は不変)。
- Policy ID(IC- / TS- / TIME- / UNIFI- / BRV- / AR-)は1件も落としていない。
- 「変更履歴」節は書き換えず、各ファイルへ追記(1行)のみ行った。
- `docs/ai/reviews/` ・`docs/ai/memory/`の既存記録は書き換えていない(参照・grepのみ)。
- `skills/`には触れていない。
- Batch 1の2本(`proxmox_operations_policy.md` / `log_observability_policy.md`)、対象外2本(`ubuntu_vm_patch_policy.md` / `cert_renew_cloudkey_policy.md`、R5の確認のみで本文は無編集)には触れていない。

## 未解決事項

1. **`time_sync_check_policy.md` TIME-007の言い換え**(上記「判断を求めて報告する事項」参照)。日付除去にとどまらず経緯的な文を事実文へ言い換えたため、他の6箇所より独立レビューでの確認優先度が高い。
2. **`proxmox_backup_restore_verify_policy.md`のBRV-075の構造的な位置**(`## 8. 変更履歴`見出し配下、テーブルより前に規則本文が置かれている)。今回のrequirement対象(日付・経緯除去)には該当しないため触れていないが、既存の文書構造上の課題として記録しておく。
3. AC5は隔離コピーでの検証。実リポジトリでの最終確認は、Yoshinobuまたは次工程が`git add`した時点で改めて`scripts/git-pre-commit-check.sh`を走らせることを推奨する。
