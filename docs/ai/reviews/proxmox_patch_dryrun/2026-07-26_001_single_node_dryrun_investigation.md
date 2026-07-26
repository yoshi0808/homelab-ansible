# Proxmox Patch Dry-run 単一ノード対応 調査記録(正式版)

**日付**: 2026-07-26
**Role**: Tech Lead(`techlead`)
**性質**: Coordinator配下の調査サブエージェントが作成した先行ドラフト(`proxmox_patch_dryrun_single_node_draft.md`、スクラッチ領域に保存・リポジトリ外)を基に、2026-07-26時点で対象ファイルを`Read`ツールにより本人が再取得し、行番号・内容を独立に検証したうえで正式化したもの。コード変更・Policy変更は本書に含まない。Tier判定・requirement・ADRは別ファイル(`2026-07-26_002_requirement.md`、`docs/ai/adr/002-proxmox-patch-dryrun-single-node.md`)を参照する。

## 0. 前提の訂正: 依頼文中の「Mode B」「§11.4」は現行Policyに存在しない

先行ドラフトが指摘したとおり、当初の依頼前提(「Policyが既に§11.4で『Mode B』に言及している」)は現行ファイルでは成立しない。現行`docs/ai/policies/proxmox_patch_policy.md`は全8節+付録Aの構成で、§11自体が存在せず、`Mode A`/`Mode B`という語は本文中どこにも現れない(2026-07-26、全417行を`Read`で再確認)。

変更履歴(`docs/ai/policies/proxmox_patch_policy.md:405`)にあるとおり、2026-07-25のコミット`a0262a4`で「定義が存在しない`Mode A`/`Mode B`参照」が意図的に削除され、条件記述へ統一されている。現行の§3.2 SB-023(`docs/ai/policies/proxmox_patch_policy.md:99`)は次のとおり明記しており、これは「Policyが実装より一歩先」ではなく「Policyが実装(固定ペア前提)と完全に一致し、かつ単一ノードdry-runを明示的に禁止している」状態である。

> dry-runはpve1 / pve2固定pairを対象とし、単一node実行を許可しない。

「単一node」に触れているのは`docs/ai/context/operations/proxmox-patch.md:30`の「-> dry-runまたはre-dry-run」という一文(apply側の単一ノードflow手順内)だけであり、2026-07-25のPolicy改訂(単一ノードdry-run明示禁止)と整合していない。Context側の書き換えが追いついていない孤立記述である可能性が高い。

したがって本調査が扱う「単一ノードdry-run」は、旧Policy用語の復元ではなく、SB-023を含む複数節を新規に改訂して導入する新機能として扱う。

## 1. 検証方法

2026-07-26に以下のファイルを`Read`ツールで再取得し、本書の行番号はすべてこの再取得結果に基づく(先行ドラフトの行番号を無検証で転記していない)。

- `docs/ai/policies/proxmox_patch_policy.md`(全417行)
- `playbooks/proxmox_patch_dryrun.yml`(全26行)
- `roles/proxmox_patch_dryrun/tasks/main.yml`(全357行)
- `roles/proxmox_patch_dryrun/defaults/main.yml`(全26行)
- `roles/proxmox_patch_dryrun/files/proxmox-dryrun-merge.py`(全103行)
- `playbooks/proxmox_healthcheck.yml`(全10行)
- `roles/proxmox_healthcheck/tasks/main.yml`(全256行)
- `docs/ai/context/operations/proxmox-patch.md`(全98行)
- `docs/ai/context/system/proxmox.md`(全57行)
- `docs/ai/context-classification.md`(全120行)
- `docs/ai/reviews/proxmox_patch_dryrun/2026-07-24_003_final.md`(全99行、先行レビュー)
- `roles/proxmox_patch_apply_node/tasks/main.yml`(該当箇所)、`roles/proxmox_patch_apply_node/defaults/main.yml`(全4行)
- `scripts/codex-classify.sh`(grep確認)
- `inventories/homelab/hosts.yml`(該当箇所、hostname表記のみ確認しIPは転記しない)

先行ドラフトが引用した行番号(§2, §4, §5に相当する箇所)は、以下の照合の結果**すべて現行ファイルと一致した**(2026-07-26時点で追加改変が入っていないことを確認)。ただし本書は独立に再取得した結果として記載し、ドラフトを根拠として引用しない。

## 2. `roles/proxmox_patch_dryrun/tasks/main.yml` の固定ペア依存箇所(2026-07-26再検証)

### 2-1. `hostvars['pve1']` / `hostvars['pve2']` の直接参照(3箇所)

| 箇所 | 行 | 内容 | 単一ノード時の挙動 |
|---|---|---|---|
| Phase 2冒頭、merge入力生成(タスク名`Save node dryrun data to temp file for merging`) | `:58-64`(値は`:60`) | `content: "{{ [hostvars['pve1'].node_dryrun, hostvars['pve2'].node_dryrun] \| to_json }}"` | `--limit pve2`実行時、`hostvars['pve1']`に`node_dryrun`が存在せず即失敗(Phase 1がpve1で走っていないため) |
| pre-status判定(タスク名`Determine pre-Codex cluster status`) | `:89-107`(ハードコード列挙は`:92-97`、6回) | `unified_dryrun.node_summaries['pve1'].apt_update_ok`等をpve1/pve2×apt_update_ok/apt_check_ok/sim_okの組み合わせで6回列挙 | 同上。2-1が回避できても、この`set_fact`が`pve1`キー欠如で失敗 |
| 最終レポートJSON生成(タスク名`Build final report JSON`) | `:216-230`(該当行`:226-227`) | `reboot_required_pve1: "{{ hostvars['pve1'].node_dryrun.reboot_required }}"` / `reboot_required_pve2: "{{ hostvars['pve2'].node_dryrun.reboot_required }}"` | 同上。レポートschema自体が`pve1`/`pve2`固定キー設計 |

### 2-2. 通知文面の`groups['proxmox']`使用(実行対象に関わらず両ノード名を表示するバグ)

| 箇所 | 行 | 内容 |
|---|---|---|
| NO_UPDATES通知件名(タスク名`Set notification content for NO_UPDATES`) | `:291` | `"[Proxmox Patch Dry-run] NO_UPDATES - {{ groups['proxmox'] \| join(', ') }} 更新候補なし"` |
| NO_UPDATES通知本文の対象ノード | `:296` | `対象ノード: {{ groups['proxmox'] \| join(', ') }}` |
| NO_UPDATES通知本文の固定文言 | `:298` | `pve1/pve2 ともに更新候補がありません。`(両ノード決め打ちの日本語文) |
| BLOCKED通知本文の対象ノード(タスク名`Set notification content for BLOCKED`) | `:311` | `対象ノード: {{ groups['proxmox'] \| join(', ') }}` |

`groups['proxmox']`はinventory groupの静的定義を返すため、`--limit pve2`を付けてもこの値は`['pve1', 'pve2']`のまま変わらない。ハードコード参照(2-1)だけを修正しても、通知文面は「pve1, pve2」「両ノードとも」と表示し続け、実際にはpve2しか検査していないという誤情報を人間に送る。

### 2-3. `playbooks/proxmox_patch_dryrun.yml`のplayレベル設定

`:9-13`は次のとおり(全26行のうち先頭部)。

```yaml
- name: Proxmox patch dry-run
  hosts: proxmox
  gather_facts: true
  become: true
  any_errors_fatal: true
```

`any_errors_fatal: true`(`:13`)が、pve1停止時にpve2側も即中断する直接原因である(先行レビュー`2026-07-24_003_final.md`が`linear.py`のstrategy実装まで確認済み。本調査では該当箇所の再実行検証はしていない)。

### 2-4. 相対的に修正不要と推定される箇所

- `roles/proxmox_patch_dryrun/files/proxmox-dryrun-merge.py`(全103行): `node_names = [n["node"] for n in nodes]`(`:57`)を筆頭に、ノード数を可変長で処理する設計であることを2026-07-26に再読して確認した。`node_summaries`辞書(`:71-81`)は既にnode名をkeyとする可変長dictであり、各nodeの`reboot_required`は`node_summaries[node].reboot_required`として既に含まれている(`:77`)。**Ansible側(2-1)の固定参照を直せば、このPythonスクリプト自体は無改修で単一ノード入力にもそのまま対応する。**
- `scripts/codex-classify.sh`(全297行): 2026-07-26に`クラスタ|両方|両ノード|pve1|pve2|cluster`でgrepを再実行し、0件を確認(先行ドラフトの簡易確認と同結果)。ただしプロンプト文言内の暗黙のクラスタ前提(パラフレーズ)はgrepでは検出できないため、実装フェーズでの全文精読は引き続き必要。

## 3. `proxmox_healthcheck` が「お手本」である理由(再確認)

`roles/proxmox_healthcheck/tasks/main.yml`(全256行)を2026-07-26に再読した結果、単一ノード対応の核心は次の2点である。

1. **ホスト間の相互参照をしない**。収集・判定・レポート保存はすべて`inventory_hostname`単位で完結し、`hostvars['pve1']`のような固定ホスト名参照が一切ない。
2. **集約が必要な箇所(Semaphoreサマリ生成、`Build Semaphore health summary`タスク、`:138-219`)では固定名ではなく`ansible_play_hosts`(そのplay実行で実際に対象になり、かつ失敗・到達不能で除外されていないホストの動的リスト)をループする**(`:142`、`:165`)。`--limit pve2`を付けた瞬間に`ansible_play_hosts == ['pve2']`となり、サマリも通知も自動的に単一ノード表示に縮退する。

さらに`playbooks/proxmox_healthcheck.yml`(全10行)は`hosts: proxmox`のみで`any_errors_fatal`を**持たない**(2026-07-26に全文再確認)。到達不能ノードがあっても他ノードの処理は続行され、Ansible標準の「失敗したホストはそのホストの残タスクだけスキップする」挙動に委ねている。この「`any_errors_fatal`なし」と「`ansible_play_hosts`による動的集約」の**組み合わせ**が単一ノード対応の実体であり、後者だけを移植しても`proxmox_patch_dryrun.yml`側の`any_errors_fatal: true`(`:13`)が残っていれば効果がない。

## 4. SB-023の経緯とYoshinobuの回答(2026-07-26)

現行SB-023(`docs/ai/policies/proxmox_patch_policy.md:99`)は「dry-runはpve1 / pve2固定pairを対象とし、単一node実行を許可しない」と明記しており、これは意図的な制約だった。しかし2026-07-26、Yoshinobuから次の回答があり、方針が確定した。

- **制約をかける対象が誤っていた**。本来の目的は「pve1/pve2間でパッチ版数の差分(drift)を作らないこと」であり、これは**apply(実パッチ適用、SB-027/SB-028)側の懸念**である。
- dry-run自体は「package metadata更新+simulationのみ」であり実際のpackage状態を変更しない情報収集であって、drift発生源ではない(現行Policy本文もSB-023の後段で同じ性質を明記している: 「package metadata更新とsimulationは行うがpackage本体を変更せず、実patchを適用しない」)。
- Yoshinobuの意図は「パッチ情報は可能な限り入手したい」。
- **結論**: SB-023はdry-runを片方のnodeでも実行可とする条件分岐へ改訂する。実apply側は従来通りpve1/pve2両ノード揃った状態(drift回避)を要求し続ける。この分離が設計の核。

## 5. 追加調査: 下流消費者の棚卸し(未決事項の一部解消)

先行ドラフトが「実装着手前に依存箇所の棚卸しが必要」としていた点について、repo全文grepで確認した。

- `reboot_required_pve1`/`reboot_required_pve2`という文字列を参照するのは、`roles/proxmox_patch_dryrun/tasks/main.yml:226-227`(書き込み元そのもの)のみ。他のrole/playbookからの読み取りはrepo全体で0件。
- `roles/proxmox_patch_apply_node/tasks/main.yml:293`(`Find latest unified dry-run JSON`タスク)は`query('fileglob', proxmox_patch_dryrun_report_dir + '/*_unified_dryrun.json')`で最新の`unified_dryrun.json`をglobし、その`.updates`配列(パッケージ名のリスト)だけを使う。`node_summaries`のキーや`_final_report`(`*_final.json`)の`reboot_required_pve1`/`_pve2`は参照していない。
- つまり`_final_report`(`*_final.json`)の`reboot_required_pve1`/`_pve2`固定キーは、**repo内では書き込まれるだけで読み取り側が存在しない**。schema変更のrepo内リグレッションリスクは低い。ただしrepo外(Semaphore dashboard等でのJSON直接参照)の消費者有無は本調査の範囲外であり未確認(requirement.mdのオープンクエスチョンに計上)。

## 6. 未決事項の整理(解決状況とADR/requirementへの割当)

| # | 論点 | 状態 |
|---|---|---|
| 1 | 単一ノードdry-run機能を新設する方向性そのものへの合意 | **解決済み**(本書§4、2026-07-26 Yoshinobu回答) |
| 2 | 意図しないUNREACHABLEと`--limit`による意図的単一ノード実行の区別 | `docs/ai/adr/002-proxmox-patch-dryrun-single-node.md`の(d)で技術方式を決定 |
| 3 | レポートJSON schemaの後方互換性 | 本書§5でrepo内消費者0件を確認(部分解消)。repo外消費者の有無はrequirement.mdのオープンクエスチョンとして残す |
| 4 | 既存playbookを直接改修するか専用playbookを新設するか | ADR-002の(c)で決定 |
| 5 | Slack通知の「クラスターStatus」表現の扱い | requirement.mdの要件(P1)・ADR-002のConsequencesで扱う |
| 6 | `scripts/codex-classify.sh`のプロンプトテンプレート全文精読 | 本書§2-4で簡易確認(0件)を再確認。全文精読はImplementerが実装フェーズで行う(requirement.mdのP2) |
| 7 | Policy改訂の粒度(条件付き許可への書き換えか新規SB番号追加か) | ADR-002のDecisionで新規SB番号採番(廃止番号非再利用の慣行に倣う)と決定 |
| 8 | 調査自体の古さへの注意 | 本書自体が2026-07-26時点の再検証であり、§1のとおり全件現行ファイルと一致を確認済み |

## 7. 本書が扱わないこと

- 実装(role/playbookの編集)、Policy本文の書き換え。
- 実ホストへのansible実行、健康状態の実測。
- apply/evacuate/weekly full側のロジック変更(既存のまま両ノード要求を維持する前提で、変更提案を含まない)。
