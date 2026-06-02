# Proxmox Patch Policy v2.0

作成日: 2026-05-09  
版: v2.0  
対象: pve1 / pve2 / 将来の Sophos Firewall VM 移行前提

---

## 1. 目的

この文書は、Proxmox VE ホストに対するパッチ適用を安全に判断・実施・停止するための運用ポリシーを定義する。

特に、過去に Proxmox の upgrade 中にホストが停止・復旧不能になった経験を踏まえ、以下を重視する。

- パッチ適用を人間の気分や記憶に依存させない
- 軽微な通常パッチは自動化し、対応忘れを防ぐ
- 重要コンポーネント更新は自動適用しない
- pve2 を先行検証ノードとして使う
- pve1 を保護する
- Proxmox ホスト OS は rollback ではなく再インストール前提で考える
- VM / CT / replication / backup を守る
- Sophos Firewall VM を Proxmox に移行する前に、Proxmox パッチ運用を確立する

---

## 2. 基本方針

### 2.1 パッチ適用はメンテナンス作業である

Proxmox ホストへのパッチ適用は、通常の Linux サーバー更新より慎重に扱う。

特に以下の領域に影響する更新は、家庭内ネットワーク・VM 稼働・クラスタ安定性に直結する。

- kernel
- ZFS
- NIC / firmware / driver
- pve-cluster
- corosync
- pve-manager
- qemu-server
- Proxmox storage / replication 周り
- network stack / bridge / VLAN 周り

### 2.2 軽微パッチは自動適用する

重要コンポーネントに該当しない更新のみで構成される場合、`PATCH_READY` として扱い、土曜朝に自動適用する。

軽微な通常パッチについては、手動対応忘れの方が運用リスクになりやすいため、自動化する。

### 2.3 重要コンポーネント更新は自動適用しない

重要コンポーネントに該当する更新、remove を伴う更新、major upgrade 疑いがある更新は自動適用しない。

これらは `MAINTENANCE_REQUIRED` / `BLOCKED` / `MAJOR_UPGRADE_DETECTED` として扱い、人間判断または別計画に移す。

### 2.4 部分適用は通常運用では行わない

`MAINTENANCE_REQUIRED` が検出された場合、重要コンポーネント以外の軽微なパッケージが同時に含まれていても、通常運用では部分適用しない。

理由:

- Proxmox 更新は `apt-get dist-upgrade` による一括更新を基本とする
- 部分適用は依存関係やパッケージ組み合わせの判断を人間が背負う
- 自動化対象としては安全ではない
- 軽微パッケージだけ先に当てる運用は、パッケージ状態を分岐させる

例外的に部分適用を検討する場合は、通常パッチ運用ではなく、明示的な例外メンテナンスとして扱う。

---

## 3. 判断軸

本ポリシーでは、判断軸を以下の2つに絞る。

```text
Status  = 適用安全度
Urgency = 対応緊急度
```

### 3.1 Status

Status は、「自動適用してよいか」「手動判断が必要か」「通常フローを止めるか」を表す。

| Status | 意味 | 自動適用 |
|---|---|---|
| `NO_UPDATES` | 更新候補なし | 不要 |
| `PATCH_READY` | 重要コンポーネントに該当しない通常更新のみ | 可 |
| `MAINTENANCE_REQUIRED` | 重要コンポーネント更新、または remove を含む | 不可 |
| `BLOCKED` | 通常更新計画として信用できない | 禁止 |
| `MAJOR_UPGRADE_DETECTED` | 通常パッチではなくメジャーアップグレード疑い | 禁止 |

### 3.2 Urgency

Urgency は、「どれくらい急いで人間が判断すべきか」を表す。

Urgency は自動適用の許可条件ではない。

| Urgency | 意味 |
|---|---|
| `LOW` | 軽微な通常更新 |
| `NORMAL` | 一般的な更新 |
| `HIGH` | セキュリティ関連、または早めの対応が望ましい更新 |
| `URGENT` | 前提条件なしに重大な被害が起きるリスク。即対応。 |

### URGENT 判断基準

以下の条件に該当する場合は `URGENT` とし、即対応とする。

| 条件 | 判断 |
|---|---|
| 認証なし RCE | 即対応 |
| 管理画面 RCE | 即対応 |
| exploit 公開済み | 即対応 |
| ransomware 利用中 | 即対応 |
| VM escape | 即対応 |
| 認証バイパス | 即対応 |
| root 権限取得可能（LPE） | 即対応 |
| backup / token / secret 漏えい | 即対応 |

### HIGH 判断基準

以下の条件に該当する場合は `HIGH` とし、早めの対応が望ましい。

| 条件 | 判断 |
|---|---|
| ローカルユーザー必須 | 中〜高（LPE なら URGENT を検討） |
| 特定機能を有効化している場合のみ | 使用有無を確認 |
| DoS のみ | 可用性次第 |
| XSS のみ | 管理画面なら中〜高 |
| 物理アクセス必須 | 家庭環境なら低め |
| 特定 CPU / デバイスのみ | 該当性確認 |

例:

| 状況 | Status | Urgency |
|---|---|---|
| tzdata / vim 等の通常更新 | `PATCH_READY` | `LOW` |
| OpenSSL / OpenSSH のセキュリティ更新 | `PATCH_READY` | `HIGH` |
| kernel LPE 修正 | `MAINTENANCE_REQUIRED` | `URGENT` |
| 重要コンポーネント remove かつ置換先不明 | `BLOCKED` | `HIGH` |
| Proxmox major upgrade 疑い | `MAJOR_UPGRADE_DETECTED` | `NORMAL` |

---

## 4. ノードの役割

| ノード | 役割 | パッチ順序 |
|---|---|---|
| `pve2` | 先行検証・縮退運用・再構築許容ノード | 最初 |
| `pve1` | 主系・安定運用ノード | pve2 成功後 |
| Sophos Firewall VM 稼働ノード | 家庭内ネットワーク中核 | 最後・慎重 |

基本方針:

- pve2 で先に試す
- pve1 が正常な状態でのみ pve2 を更新する
- pve2 が壊れた場合は、pve1 が生きているうちに pve2 を再インストールする
- pve1 への適用は、pve2 更新後の healthcheck が OK の場合のみ行う

---

## 5. VM 配置・退避・復帰方針

### 5.1 基本方針

パッチ対象ノードを reboot する可能性があるため、patch apply 前に VM / CT の所在を確認する。

PATCH_READY の自動適用では、VM / CT の退避と復帰も自動フローに含める。

用語:

```text
current node:
  現在 VM / CT が稼働しているノード

home node:
  通常時に VM / CT を置きたい規定ノード

evacuation:
  パッチ対象ノードから一時的に VM / CT を退避すること

restore placement:
  パッチ完了後に VM / CT を home node へ戻すこと
```

### 5.2 home node の考え方

VM / CT ごとに home node を定義する。

現在の Ansible 構成では、以下のファイルに Proxmox グループの接続情報が定義されている。

```text
inventories/homelab/group_vars/proxmox.yml
```

例:

```yaml
ansible_user: ann
ansible_ssh_private_key_file: ~/.ssh/id_ann
```

`group_vars/proxmox.yml` は接続情報を中心に維持し、VM / CT 配置ポリシーは混在させない。

VM / CT の home node は、Proxmox 上のタグで管理する。YAMLファイルによる外部定義は使用しない。

タグ命名規則:

```text
prefer<node名>
```

例: `pve1` が home node であれば `preferpve1` タグを付与する。

Proxmox の Web UI または CLI でVM/CTに付与する:

```bash
# VM 101 に preferpve1 タグを付与する例
pvesh set /nodes/pve2/qemu/101/config --tags preferpve1
```

Ansible での判定:

```yaml
selectattr('tags', 'search', '(^|;)prefer' ~ inventory_hostname ~ '(;|$)')
```

`inventory_hostname`（例: `pve1`）と一致する `prefer<node名>` タグを持つVM/CTが、そのノードへ復帰すべき対象として扱われる。

report / mail では、VM ID だけでなく以下のように表示する。

```text
VM 101 example-vm-101:
  current node: pve2
  home node:    pve1  (tag: preferpve1)
  action:       migrate back to pve1
```

### 5.3 pve2 apply 前

pve2 に PATCH_READY を適用する前に、以下を行う。

1. pve2 上の running VM / CT を一覧化する
2. 自動退避対象か確認する
3. 必要な VM / CT を pve1 へ migrate / shutdown / skip のいずれかで処理する
4. pve2 が patch apply / reboot 可能な状態であることを確認する

pve2 上に退避できない重要 VM / CT が残っている場合、pve2 apply は行わない。

### 5.4 pve1 apply 前

pve1 に PATCH_READY を適用する前に、以下を行う。

1. pve1 上の running VM / CT を一覧化する
2. pve1 を reboot できるよう、必要な VM / CT を pve2 へ一時退避する
3. pve2 が健康であり、退避先として使えることを確認する
4. pve1 が patch apply / reboot 可能な状態であることを確認する

### 5.5 patch 完了後の VM 復帰

pve1 の patch / reboot / post-healthcheck が完了した後、VM / CT を home node へ戻す。

特に、通常時に pve1 へ置く VM / CT は、pve1 の post-healthcheck OK 後に pve1 へ戻す。

最終状態では、以下を確認する。

- VM / CT が期待する home node にいる
- VM / CT が running である
- Proxmox healthcheck が OK
- 必要な疎通確認が通る

### 5.6 自動 migration の扱い

VM / CT の migrate は、PATCH_READY 自動適用フロー内で許可する。

ただし、以下の場合は自動 migration を行わず停止する。

- migration dry-run / precheck が失敗
- 対象 VM / CT が migration 非対応
- 対象 VM / CT が local-only storage を使っている
- 対象 VM / CT が Sophos Firewall などネットワーク中核で、手動判断が必要
- pve2 / pve1 のどちらかの healthcheck が OK ではない

---

## 6. Playbook 分離方針

safe / semi-safe / controlled apply / unsafe を明確に分離する。

種別は増やしすぎない。  
本ポリシーでは以下の4分類に固定する。

| 種別 | 意味 |
|---|---|
| safe | read-only。状態収集のみ |
| semi-safe | 状態更新はあるが、実パッチ適用はしない |
| controlled apply | VM/CT migration など、制御された変更を行う |
| unsafe | OSパッチ適用、major upgrade、重要コンポーネント手動適用など |

また、Ansible control node が Proxmox クラスタ内 VM の場合と、quory のようなクラスタ外物理ノードの場合で、実行できる単位を分ける。

### 6.1 Playbook 一覧

| 種別 | Playbook | 内容 | 自動実行 |
|---|---|---|---|
| safe | `proxmox_healthcheck.yml` | read-only healthcheck | 可 |
| semi-safe | `proxmox_patch_dryrun.yml` | `apt update` + simulation + changelog収集 + Codex分類 | 可 |
| controlled apply | `proxmox_evacuate_node.yml` | patch対象ノード上のVM/CTを反対側ノードへ退避 | 条件付き可 |
| unsafe | `proxmox_patch_apply_node.yml` | 1ノード単位の `PATCH_READY` 実パッチ適用 | 条件付き可 |
| unsafe | `proxmox_patch_weekly_full.yml` | pve2 → pve1 → VM復帰の全体制御 | quory / 外部control nodeのみ可 |
| controlled apply | `proxmox_restore_vm_placement.yml` | VM / CT を home node へ戻す | 条件付き可 |
| unsafe | major upgrade / maintenance apply | 重要コンポーネント更新の手動適用 | 自動禁止 |

補足:

- `proxmox_patch_apply_node.yml` は `PATCH_READY` のみを扱う場合でも、実際にOSパッチを適用するため `unsafe` とする。
- `proxmox_patch_weekly_full.yml` は内部で実パッチ適用を含むため `unsafe` とする。
- `proxmox_evacuate_node.yml` と `proxmox_restore_vm_placement.yml` は VM/CT の配置を変更するが、OSパッチは適用しないため `controlled apply` とする。

---

### 6.2 `proxmox_healthcheck.yml`

#### 目的

Proxmox ノードが現在パッチ適用可能な健康状態かを確認する。

#### 対象

- pve1
- pve2
- `--limit` による単一ノード実行も可

#### 安全度

```text
safe
read-only
```

#### 処理概要

1. 対象ノードに疎通できることを確認する
2. Proxmox / Debian 基本情報を収集する
3. `pveversion` を収集する
4. `pvecm status` を収集する
5. quorum 状態を判定する
6. `zpool status` を収集する
7. ZFS pool が ONLINE であることを確認する
8. `pvesr status` を収集する
9. replication の異常有無を確認する
10. `systemctl --failed` を収集する
11. `pve-cluster` / `corosync` / `pvedaemon` / `pveproxy` などの service 状態を確認する
12. root filesystem 使用率を確認する
13. `apt-get check` を実行し、apt / dpkg の破綻がないことを確認する
14. `/var/run/reboot-required` の有無を確認する
15. VM / CT の所在と稼働状態を収集する
16. JSON report を control node 側に保存する
17. `OK` / `WARNING` / `CRITICAL` を判定する
18. `WARNING` / `CRITICAL` の場合は patch apply を禁止する

#### 出力

- healthcheck JSON report
- 標準出力サマリー
- `OK` / `WARNING` / `CRITICAL`

#### 失敗条件

- quorum なし
- ZFS 異常
- apt / dpkg 異常
- 重要 service 停止
- systemd failed units あり
- root filesystem 危険域
- report 生成失敗

---

### 6.3 `proxmox_patch_dryrun.yml`

#### 目的

更新候補を取得し、今回の更新セットを `NO_UPDATES` / `PATCH_READY` / `MAINTENANCE_REQUIRED` / `BLOCKED` / `MAJOR_UPGRADE_DETECTED` に分類する。

#### 対象

- pve1
- pve2
- pve1 / pve2 の固定ペアで実行する（単一ノード実行は非対応）

#### 安全度

```text
semi-safe
apt-get update あり（パッケージリストの更新のみ、パッケージ本体は変更しない）
実パッチ適用なし
```

#### 処理概要

1. 対象ノードの healthcheck が OK であることを確認する
2. `apt-get update` を実行し、パッケージリストを最新化する
3. `apt-get check` を実行し、apt / dpkg の整合性を確認する
4. `apt-get -s dist-upgrade` を実行する
5. simulation の成功/失敗を収集する
6. `Inst` / `Remv` / `Conf` / kept back などを抽出する
7. 更新対象パッケージ一覧を作成する
8. remove 予定パッケージ一覧を作成する
9. newly installed package 一覧を作成する
10. 重要コンポーネント該当候補を抽出する
11. Debian security repository 由来候補を抽出する
12. 対象パッケージの `apt changelog` を取得する
13. changelog 全文を report ディレクトリに保存する
14. dry-run report JSON を生成する
15. Codex CLI に dry-run report / changelog / policy を渡す
16. Codex CLI から構造化分類 JSON を受け取る
17. Ansible tasks が最終 Status / Urgency を判定する
18. メール本文を生成する
19. 必要に応じて通知する
20. apply は行わない

#### Codex CLI の役割

- changelog を読む
- 重要コンポーネント該当性を分類する
- remove が置換に見えるか分類する
- security-sensitive か分類する
- urgency 候補を出す
- メール本文向けの要約を作る

Codex CLI は最終 Status を直接決定しない。

#### 出力

- dry-run JSON report（unified JSON。changelog diff を含む）
- Codex classification JSON
- final report JSON
- 日本語 MD report（changelog 差分の全文と分析結果を含む）
- final Status / Urgency

#### Status 判定

- 更新なし → `NO_UPDATES`
- apt simulation 失敗 → `BLOCKED`
- major upgrade 疑い → `MAJOR_UPGRADE_DETECTED`
- 重要コンポーネント更新あり → `MAINTENANCE_REQUIRED`
- remove あり、置換判断が必要 → `MAINTENANCE_REQUIRED` または `BLOCKED`
- 重要コンポーネント更新なし、removeなし → `PATCH_READY`

---

### 6.4 `proxmox_evacuate_node.yml`

#### 目的

patch対象ノード上の VM / CT をすべて反対側ノードへ退避する。

この playbook は、patch apply の前提処理として使う。

#### 対象

```text
--limit pve2
--limit pve1
```

または変数で対象ノード を指定する。
(例)
```yaml
target_node: pve2
destination_node: pve1
```

#### 安全度

```text
controlled apply
VM/CT migration を伴う
OSパッチ適用なし
```

#### 実行条件

- target node / destination node の healthcheck が OK
- destination node に退避先として十分なリソースがある
- 対象 VM / CT が migration 可能である
- 対象 VM / CT が local-only storage に依存していない
- 対象 VM / CT が手動判断対象ではない
- Sophos Firewall VM などネットワーク中核VMが含まれる場合は停止する

#### 処理概要

1. target node を確認する
2. destination node を確認する
3. target / destination 両方の healthcheck が OK であることを確認する
4. target node 上の running VM / CT を一覧化する
5. VM / CT ごとに migration 可否を判定する
6. local-only storage 使用有無を確認する
7. 手動判断対象 VM / CT が含まれていないことを確認する
8. destination node の CPU / memory / storage 余力を確認する
9. migration plan を作成する
10. migration plan を report に保存する
11. VM / CT を destination node へ migrate する
12. migration 結果を確認する
13. target node 上に running VM / CT が残っていないことを確認する
14. evacuation report を保存する

#### 停止条件

- target / destination の healthcheck が OK ではない
- migration 不可 VM / CT がある
- local-only storage 使用 VM / CT がある
- Sophos Firewall VM など手動判断対象が含まれる
- destination node のリソース不足
- migration 失敗
- target node 上に VM / CT が残る

#### 出力

- evacuation plan
- evacuation report
- migrated VM / CT 一覧
- skipped VM / CT 一覧
- failed VM / CT 一覧

---

### 6.5 `proxmox_patch_apply_node.yml`

#### 目的

`PATCH_READY` の自動適用、または `MAINTENANCE_REQUIRED` の手動適用を、指定した1ノードに対して行う。

#### 対象

apply 対象ノードを実行時に指定する（`pve1` または `pve2` のいずれか）。

#### 安全度

```text
unsafe
単一ノード限定
OSパッチ適用あり
```

#### 実行条件

- 対象ノードの healthcheck が OK
- 退避先または反対側ノードを利用する場合は、実行前段・上位 playbook・手動手順のいずれかで反対側ノードの healthcheck が OK であることを確認済み
- 事前 dry-run または apply 直前の re-dry-run により、対象ノードの Status を確認済み
- control node が対象ノード上にいない
- 対象ノード上の VM / CT が退避済み
- `BLOCKED` / `MAJOR_UPGRADE_DETECTED` は適用禁止
- `MAINTENANCE_REQUIRED` の場合は手動 apply モードかつ明示的確認が必要

#### 処理概要

1. 対象ノードを確認する
2. control node が対象ノード上にいないことを確認する
3. 対象ノードの healthcheck が OK であることを確認する
4. 退避先または反対側ノードを利用する場合は、実行前段・上位 playbook・手動手順で反対側ノードの healthcheck が OK であることを確認する
5. 事前 dry-run または apply 直前の re-dry-run により、対象ノードの Status を確認する
6. Status に応じた apply モードを判定する
   - `PATCH_READY`: 自動 apply モードで続行する
   - `MAINTENANCE_REQUIRED`: 手動 apply モードかつ明示的確認文字列が正しい場合のみ続行する
   - `BLOCKED` / `MAJOR_UPGRADE_DETECTED`: 停止する
7. 対象ノード上に running VM / CT が残っていないことを確認する
8. 対象ノードにパッケージを適用する
9. apply 結果を保存する
10. reboot-required があれば対象ノードを reboot する
11. SSH / Proxmox API / GUI の復帰を待つ
12. 対象ノードの post-healthcheck を実行する
13. 結果を report に保存する
14. summary mail を生成する

#### reboot 要否の判定原則

/var/run/reboot-required の有無だけでは
kernel 更新後の reboot 要否を正確に検出できない場合がある。

reboot 要否は以下を組み合わせて判定する:
- /var/run/reboot-required の有無
- 現在動作中の kernel バージョン（uname -r）と
  インストール済み kernel パッケージのバージョンの比較

#### post-healthcheck リトライ設定

reboot 直後の post-healthcheck が CRITICAL または UNKNOWN になる場合がある。
サービスが起動しきる前にチェックが走ること、またはスクリプト自体が一時的に失敗することが原因であることが多い。

この問題に対応するため、**「reboot実施済み かつ CRITICAL または UNKNOWN」の場合に**、
一定時間待機してから post-healthcheck をリトライする仕組みがある。

- CRITICAL: JSON は取得できたが health 判定が NG
- UNKNOWN: healthcheck スクリプト自体が失敗した（コマンドエラー・不正JSON など）

reboot を伴わない CRITICAL / UNKNOWN はリトライしない（本物の障害として扱う）。

設定変数（`roles/proxmox_patch_apply_node/defaults/main.yml`）:

| 変数 | デフォルト | 意味 |
|---|---|---|
| `proxmox_patch_apply_hc_retry_count` | `2` | リトライの最大試行回数。内部で `range(N+1)` 回ループし、各試行の冒頭に待機する |
| `proxmox_patch_apply_hc_retry_delay` | `60` | 各リトライ試行の冒頭で待機する秒数 |

計算式:

```text
リトライ最大試行回数 = retry_count + 1
最大待機時間        = (retry_count + 1) × retry_delay 秒
  （各試行の先頭で delay 秒待機するため、試行回数分の待機が発生する）
```

デフォルト設定（retry_count=2、retry_delay=60）での動作例:

```text
reboot完了
→ post-healthcheck 1回目: CRITICAL   （初回）
→ 60秒待機                            （リトライ試行1の冒頭 pause）
→ post-healthcheck 2回目: CRITICAL   （リトライ試行1）
→ 60秒待機                            （リトライ試行2の冒頭 pause）
→ post-healthcheck 3回目: OK         （リトライ試行2）
→ SUCCESS として扱う
```

最大待機時間 = (2+1) × 60 = 180秒

リトライ後に OK になった場合はSUCCESSとして扱い、summary mail の件名も `[SUCCESS]` になる。
すべての試行でCRITICALのままだった場合は CRITICALとして報告する。

チューニング例:

```text
サービスの起動が遅い環境:
  proxmox_patch_apply_hc_retry_count: 3
  proxmox_patch_apply_hc_retry_delay: 90
  → リトライタスク最大4回試行、最大待機 (3+1)×90 = 360秒

素早く判断したい場合:
  proxmox_patch_apply_hc_retry_count: 1
  proxmox_patch_apply_hc_retry_delay: 30
  → リトライタスク最大2回試行、最大待機 (1+1)×30 = 60秒
```

変更方法:

```bash
# 実行時に一時的に変更
ansible-playbook proxmox_patch_apply_node.yml \
  -e proxmox_patch_apply_hc_retry_count=3 \
  -e proxmox_patch_apply_hc_retry_delay=90

# または defaults/main.yml を直接編集して恒久変更
```

#### やらないこと

- VM / CT の退避は行わない
- もう一方のノードへ自動で進まない
- VM / CT を home node へ最終復帰しない
- `BLOCKED` を解除しない
- `MAJOR_UPGRADE_DETECTED` は適用対象外

#### 出力

- apply report
- post-healthcheck report
- summary mail

---

### 6.6 `proxmox_patch_weekly_full.yml`

#### 目的

土曜朝の全体自動パッチを制御する。

pve2 から開始し、pve2 が正常に完了した場合のみ pve1 へ進み、最後に VM / CT を home node へ戻す。

#### 対象

- pve2
- pve1
- VM / CT home node 定義

#### 安全度

```text
unsafe
quory / 外部 control node のみ
OSパッチ適用あり
```

#### 実行条件

- control node が Proxmox クラスタ外にある
- pve1 / pve2 の reboot 影響を受けない
- pve1 / pve2 healthcheck が OK
- dry-run Status が `PATCH_READY`
- VM / CT の退避と復帰が可能
- quory など外部 control node から実行している

#### 処理概要

1. control node が Proxmox クラスタ外にあることを確認する
2. pve1 healthcheck を実行する
3. pve2 healthcheck を実行する
4. どちらか WARNING / CRITICAL なら停止する
5. pve2 dry-run を実行する
6. Status が `PATCH_READY` であることを確認する
7. `proxmox_evacuate_node.yml` 相当の処理で pve2 上の VM / CT を pve1 へ退避する
8. pve2 に patch apply する
9. pve2 reboot if required
10. pve2 post-healthcheck を実行する
11. pve2 post-healthcheck OK の場合のみ pve1 へ進む
12. `proxmox_evacuate_node.yml` 相当の処理で pve1 上の VM / CT を pve2 へ退避する
13. pve1 に patch apply する
14. pve1 reboot if required
15. pve1 post-healthcheck を実行する
16. `proxmox_restore_vm_placement.yml` 相当の処理で VM / CT を home node へ戻す
17. final healthcheck を実行する
18. summary mail を送信する

#### 停止条件

- control node が Proxmox クラスタ内にいる
- healthcheck が WARNING / CRITICAL
- dry-run Status が `PATCH_READY` ではない
- VM / CT の退避失敗
- apply 失敗
- reboot 後に対象ノードが戻らない
- post-healthcheck NG
- pve2 NG の状態で pve1 へ進もうとした場合

#### 出力

- full flow report
- evacuation reports
- per-node apply reports
- final healthcheck report
- summary mail

---

### 6.7 `proxmox_restore_vm_placement.yml`

#### 目的

VM / CT を定義済み home node へ戻す。

#### 対象

- VM / CT home node 定義
- pve1
- pve2

#### 安全度

```text
controlled apply
VM migration を伴う
OSパッチ適用なし
```

#### 処理概要

1. VM / CT home node 定義を読む
2. 現在の VM / CT 所在を取得する
3. home node と current node を比較する
4. 差分を一覧化する
5. migration 可能性を確認する
6. 必要な VM / CT を home node へ migrate する
7. migration 後の所在を確認する
8. running 状態を確認する
9. final report を保存する

#### 停止条件

- home node 定義がない
- VM / CT が migration 非対応
- local-only storage を使っている
- 退避先ノードの healthcheck が OK ではない
- Sophos Firewall VM など手動判断対象が含まれる

---

### 6.8 major upgrade / maintenance apply

#### 目的

`MAINTENANCE_REQUIRED` または `MAJOR_UPGRADE_DETECTED` の場合に、人間がメンテナンス枠で実施する。

#### 方針

この文書では自動化しない。

```text
MAINTENANCE_REQUIRED:
  手動メンテナンス判断

MAJOR_UPGRADE_DETECTED:
  別プロジェクト化

BLOCKED:
  Contingency Plan
```

---

## 7. 重要コンポーネント

以下に該当するパッケージが更新対象に含まれる場合、通常パッチ扱いしない。

```text
proxmox-ve
proxmox-kernel-*
pve-manager
pve-cluster
pve-ha-manager
qemu-server
pve-container
libpve-*
corosync
zfsutils-linux
zfs-zed
ifupdown2
firmware-*
intel-microcode
amd64-microcode
systemd
udev
```

重要コンポーネントの扱い:

```text
重要コンポーネント更新あり
  → MAINTENANCE_REQUIRED

重要コンポーネント remove あり、かつ置換先不明
  → BLOCKED

重要コンポーネント remove あり、ただし後継・置換パッケージが同時に見える
  → MAINTENANCE_REQUIRED
```

---

## 8. Status 判定ルール

### 8.1 NO_UPDATES

条件:

- 更新候補なし

行動:

- メールで通知する（件名に `NO_UPDATES` を明示する）
- パッチ適用しない
- report を保存する

---

### 8.2 PATCH_READY

条件:

- healthcheck が OK
- `apt-get check` 成功
- `apt-get -s dist-upgrade` 成功
- remove なし
- major upgrade 疑いなし
- 重要コンポーネント更新なし

意味:

```text
重要コンポーネントに該当しない通常更新のみ。
自動適用してよい。
```

行動:

- 土曜朝に pve2 へ自動適用
- pve2 post-healthcheck OK なら pve1 へ自動適用
- pve2 post-healthcheck NG なら pve1 へ進まない
- pve2 で止めて通知する

---

### 8.3 MAINTENANCE_REQUIRED

条件:

- 重要コンポーネント更新あり
- remove あり
- 重要コンポーネント remove ありだが、後継・置換パッケージが同時に見える
- apt simulation は成功している
- major upgrade 疑いではない

意味:

```text
危険確定ではないが、通常パッチとして扱わない。
自動適用しない。
人間がメンテナンス枠で pve2 から実施するか判断する。
```

行動:

- 自動適用しない
- 軽微パッケージも含めて通常パッチは保留する
- 部分適用しない
- 毎週 dry-run で再評価する
- 保留期間に固定上限は設けない
- urgency が HIGH / URGENT に上がった場合でも自動適用しない
- ユーザーがメンテナンス枠を確保して手動実施するか判断する

---

### 8.4 BLOCKED

条件:

- `apt-get check` 失敗
- `apt-get -s dist-upgrade` 失敗
- 重要コンポーネント remove あり、かつ後継・置換パッケージが確認できない
- `proxmox-ve` / `pve-cluster` / `zfsutils-linux` などが消えるだけに見える
- repository / dependency の破綻が疑われる

意味:

```text
通常の更新計画として信用できない。
通常パッチ運用を停止する。
```

行動:

- pve1 / pve2 のどちらにも適用しない
- PATCH_READY 相当の軽微な更新が含まれていても部分適用しない
- 自動 apply timer を停止する
- 復旧・回避・再構成ルートへ移行する
- apply は再開条件を満たすまで禁止する

---

### 8.5 MAJOR_UPGRADE_DETECTED

条件:

- Proxmox major version が変わる疑い
- Debian suite が変わる疑い
- repository suite を変更した直後
- base package が大量に更新される
- install / remove が大量
- `pve-manager` の major version が変わる疑い

意味:

```text
通常パッチではなく、メジャーアップグレード案件。
```

行動:

- 通常パッチ運用から除外
- 自動適用しない
- 別プロジェクト化
- Roadmap / Release Notes を参照
- pve2 検証計画を作る
- pve1 は最後

---

## 9. remove の扱い

`apt-get dist-upgrade` では、依存関係解決のために package remove が計画されることがある。

remove が検出された場合、単純に即 BLOCKED とはしない。  
removed / newly installed / upgraded の組み合わせを見て、後継パッケージへの置換である可能性を区別する。

### 9.1 MAINTENANCE_REQUIRED とする remove

以下の場合は `BLOCKED` ではなく `MAINTENANCE_REQUIRED` とする。

- apt simulation が成功している
- remove と同時に後継・置換と思われる package install がある
- Proxmox major upgrade 疑いではない
- `proxmox-ve` などの中核メタパッケージが失われるだけの状態ではない

この場合、自動適用は行わず、メールで remove / install / upgrade の対応関係を提示し、ユーザーがメンテナンス枠で判断する。

### 9.2 BLOCKED とする remove

以下の場合は `BLOCKED` とする。

- apt simulation が失敗している
- `apt-get check` が失敗している
- 重要コンポーネントが remove される一方で、後継・置換パッケージが確認できない
- `proxmox-ve` / `pve-cluster` / `zfsutils-linux` などが消えるだけに見える
- repository / dependency の破綻が疑われる

---

## 10. Urgency 判定

Urgency は、対応をどれくらい急ぐべきかを表す。  
Status とは別軸であり、自動適用の許可条件ではない。

`apt-get -s dist-upgrade` の出力だけでは urgency は判定できない。  
初期実装では、以下を材料として urgency を決める。

- candidate version が Debian security repository 由来か
- `apt changelog` / NEWS に security / CVE / vulnerability が明記されているか
- Codex CLI による changelog 分類
- Proxmox Security Advisories の有無
- package が SSH / TLS / auth / qemu / kernel / firewall / network exposure に関係するか

### 10.1 LOW

軽微な通常更新。

例:

- timezone
- editor
- documentation
- small utility

### 10.2 NORMAL

一般的な更新。

例:

- bug fix
- minor package update
- routine maintenance update
- 重要コンポーネント更新だが security 要素が明確でないもの

### 10.3 HIGH

セキュリティ関連、または早めの対応が望ましい更新。

HIGH とする条件:

- candidate version が Debian security repository 由来
- `apt changelog` / NEWS に CVE / security / vulnerability が明記されている
- Proxmox Security Advisories に関連がある
- openssl / openssh / curl / libc / apt / dpkg / qemu / kernel など security-sensitive な package が含まれる
- firewall / network service / authentication / TLS に関係する更新

Debian security repository 由来の判定は、初期実装では `apt-get -s dist-upgrade` の `Inst` 行、または `apt-cache policy <package>` を補助的に使う。

例:

```bash
LC_ALL=C apt-get -s dist-upgrade \
  | awk '/^Inst / && /security\.debian\.org|-security|Debian-Security/i { print "HIGH:", $2 }'
```

ただし、単純な grep だけで最終判定せず、Codex CLI による changelog 分類と併せて扱う。

### 10.4 URGENT

重大脆弱性、または既知悪用が疑われる更新。

例:

- known exploited vulnerability
- remote code execution
- authentication bypass
- VM escape / hypervisor escape
- firewall / internet exposure に関わる重大問題

`URGENT` は初期実装では自動昇格しすぎない。  
公式 advisory、changelog、ユーザー判断により昇格する。

Urgency が HIGH / URGENT でも、Status が `MAINTENANCE_REQUIRED` / `BLOCKED` / `MAJOR_UPGRADE_DETECTED` の場合は自動適用しない。

---

## 11. 土曜朝の自動パッチ運用

### 11.1 実行モード

土曜朝の自動パッチには、control node の配置に応じて2つの実行モードを定義する。

#### Mode A: quory / 外部 control node

条件:

- control node が Proxmox クラスタ外にある
- pve1 / pve2 の reboot 影響を受けない
- quory のような物理ノードから実行する

この場合のみ、以下の全体フローを自動実行してよい。

```text
pve2 patch
↓
pve2 reboot if required
↓
pve2 post-healthcheck
↓
pve1 patch
↓
pve1 reboot if required
↓
pve1 post-healthcheck
↓
VM / CT を home node へ戻す
```

#### Mode B: ansy / Proxmox 上の control node

条件:

- control node が ansy である
- ansy が pve1 または pve2 上の VM として動いている

この場合、pve1 / pve2 の連続自動パッチは行わない。

実行可能なのは、control node が存在しない側の単一ノード patch のみ。

例:

```text
ansy が pve1 上にいる:
  pve2 の単一ノード patch は可
  pve1 の patch は不可

ansy が pve2 上にいる:
  pve1 の単一ノード patch は可
  pve2 の patch は不可
```

ansy 自身を playbook 内で自動 migrate して、同一playbookで続行する運用はしない。  
control node の所在変更は、別作業としてユーザーが明示的に行う。

### 11.2 スケジュール

```text
毎週土曜朝
```

Mode A 推奨例:

```text
05:00 healthcheck
05:05 patch dry-run
05:10 PATCH_READY の場合のみ pve2 VM/CT所在確認・退避
05:20 pve2 apply
05:30 pve2 reboot if required
05:40 pve2 post-healthcheck
05:50 pve1 VM/CT所在確認・退避
06:00 pve1 apply
06:10 pve1 reboot if required
06:20 pve1 post-healthcheck
06:30 VM/CT を home node へ戻す
06:40 final healthcheck
06:45 summary mail
```

Mode B では単一ノードのみを対象にする。

例:

```text
05:00 healthcheck
05:05 patch dry-run
05:10 control node placement check
05:15 target node VM/CT所在確認・退避
05:25 target node apply
05:35 target node reboot if required
05:45 target node post-healthcheck
05:50 summary mail
```

時刻は仮置きであり、実装時に調整する。

### 11.3 Mode A 実行フロー

Mode A は、quory / 外部 control node からのみ実行する。

```text
1. control node が Proxmox クラスタ外にあることを確認
2. pve1 healthcheck
3. pve2 healthcheck
4. どちらか WARNING / CRITICAL なら停止
5. pve2 patch dry-run
6. Status 判定
7. PATCH_READY 以外なら apply しない
8. pve2 上の VM / CT 所在確認
9. pve2 上の VM / CT を必要に応じて pve1 へ退避
10. pve2 に自動適用
11. pve2 で reboot-required があれば自動 reboot
12. pve2 post-healthcheck
13. pve2 OK の場合のみ pve1 へ進む
14. pve1 上の VM / CT 所在確認
15. pve1 上の VM / CT を必要に応じて pve2 へ退避
16. pve1 に自動適用
17. pve1 で reboot-required があれば自動 reboot
18. pve1 post-healthcheck
19. VM / CT を定義済み home node へ戻す
20. final healthcheck
21. summary mail
```

### 11.4 Mode B 実行フロー

Mode B は、ansy が Proxmox 上の VM として動いている場合の暫定運用である。

```text
1. control node の所在確認
2. target node が control node の稼働ノードではないことを確認
3. target node healthcheck
4. 退避先または反対側ノードを利用する場合は、実行前段・上位 playbook・手動手順で反対側ノードの healthcheck を確認
5. healthcheck が WARNING / CRITICAL なら停止
6. target node patch dry-run または apply 直前の re-dry-run
7. Status 判定
8. PATCH_READY 相当ではない場合は自動 apply しない
9. target node 上の VM / CT 所在確認
10. target node 上の VM / CT を必要に応じて反対側ノードへ退避
11. target node に自動適用
12. target node で reboot-required があれば自動 reboot
13. target node post-healthcheck
14. summary mail
```

Mode B では、反対側ノードへ自動で続行しない。  
もう一方のノードを patch する場合は、control node を patch 対象外の場所へ移した後、別の実行として行う。

### 11.5 金曜に手動適用した場合

金曜夕方の通知を受けてユーザーが手動でパッチ適用した場合、土曜朝の自動パッチは空振りになってよい。

土曜朝の dry-run で更新候補がなくなっている場合は、以下として扱う。

```text
Status:
  NO_UPDATES

Action:
  apply しない
  必要なら report のみ保存
```

金曜に pve2 のみ手動適用済みで pve1 が未適用の場合、Mode A では土曜朝に pve1 へ進む余地がある。  
Mode B では control node の所在条件を満たす場合のみ、pve1 の単一ノード patch を実行する。

### 11.6 停止する条件

以下の場合、次のノードには進まない。

- apply が失敗
- reboot 後に SSH / Proxmox API / GUI が戻らない
- post-healthcheck が WARNING / CRITICAL
- apt / dpkg が失敗
- systemd failed units が出た
- pve-cluster / corosync / ZFS / replication に異常
- VM / CT の退避に失敗
- VM / CT の復帰に影響がある
- VM / CT の稼働に影響がある
- control node が target node 上にあり、継続実行できない

summary mail で停止理由を通知し、週末中に対応する。

### 11.7 reboot-required の扱い

`PATCH_READY` の自動適用後に reboot-required が検出された場合、対象ノードを自動 reboot する。

dry-run 時点では reboot-required は確定しない。  
dry-run では `reboot_expected` を推定し、apply 後に `reboot_required` を事実として扱う。

reboot-required の検出は `/var/run/reboot-required` の存在確認を基本とする。ただし、カーネルパッケージの更新を伴う場合は、実行中のカーネルバージョンとインストール済みカーネルバージョンの差分によっても reboot 要否を判定する。

対象ノードで reboot-required が検出された場合:

1. 対象ノードを自動 reboot する
2. SSH / Proxmox API / GUI の復帰を待つ
3. post-healthcheck を実行する
4. post-healthcheck が OK の場合のみ次の処理へ進む
5. post-healthcheck が WARNING / CRITICAL の場合、次のノードには進まない

---

## 12. MAINTENANCE_REQUIRED 時の保留方針

`MAINTENANCE_REQUIRED` が検出された場合、その週の自動パッチ適用は行わない。

重要コンポーネント以外の軽微な更新が同時に含まれていても、通常運用では部分適用しない。

保留期間に固定上限は設けない。

毎週の dry-run により状態を再評価し、urgency や対象パッケージの変化を確認する。

urgency が `HIGH` または `URGENT` になった場合でも自動適用は行わず、ユーザーがメンテナンス枠を確保して pve2 から手動実施するか判断する。

playbook を使って手動 apply を行う場合、明示的確認文字列を実行時変数として指定しなければならない。この確認がない場合、playbook は自動的に停止する。確認文字列は playbook が規定した形式に沿う。

---

## 13. BLOCKED 時の Contingency Plan

`BLOCKED` は、通常パッチ運用を停止する状態である。

`BLOCKED` が検出された場合、pve1 / pve2 のどちらにもパッチを適用しない。  
PATCH_READY 相当の軽微な更新が含まれていても、部分適用は行わない。

### 13.1 Immediate actions

- patch apply timer を停止する
- apply 系 playbook の実行を禁止する
- pve1 / pve2 の両方に適用しない
- Sophos 移行前であれば移行を延期する
- Sophos 移行後であれば Sophos 稼働ノードを固定し、不要な移動を行わない
- pve1 の安定稼働を最優先する

### 13.2 Route selection

`BLOCKED` の原因に応じて、以下のいずれかのルートに移行する。

#### apt simulation failed

- 通常パッチ運用を停止する
- repository / apt source 修正ルートへ移行する
- 修正後に dry-run を再実行する
- `PATCH_READY` または `MAINTENANCE_REQUIRED` に戻るまで apply しない

#### important component remove without replacement

- その更新セットは適用しない
- repository / dependency 修正ルートへ移行する
- 重要コンポーネントの remove 予定が消えるまで apply しない

#### apt-get check failed

- 通常パッチ運用を停止する
- apt / dpkg 修復ルートへ移行する
- `apt-get check` が成功するまで apply しない

#### major upgrade suspected

- 通常パッチ運用を停止する
- `MAJOR_UPGRADE_DETECTED` として扱う
- major upgrade 計画へ移行する
- pve2 検証計画を作る
- pve1 は対象外にする

### 13.3 Return condition

以下をすべて満たすまで通常パッチ運用に戻さない。

- `apt-get check` が成功する
- `apt-get -s dist-upgrade` が成功する
- 重要コンポーネントの remove 予定がない、または置換関係として `MAINTENANCE_REQUIRED` に分類できる
- major upgrade 疑いがない
- `proxmox_healthcheck` が OK
- dry-run status が `PATCH_READY` または `MAINTENANCE_REQUIRED` に戻る

---

## 14. 公式情報と changelog の扱い

### 14.1 基本方針

通常の週次 patch dry-run では、対象パッケージの changelog を最優先する。

Roadmap / Release Notes は、メジャー / マイナーリリース疑いがある場合、または Proxmox 中核パッケージが広範囲に動く場合に参照する。

### 14.2 changelog

コマンド例:

```bash
apt changelog pve-manager
apt changelog pve-cluster
apt changelog qemu-server
apt changelog zfsutils-linux
apt changelog corosync
```

運用:

- changelog 全文は report に保存する
- メール本文には要約だけ載せる
- 人間が changelog 全文を毎回読む運用にはしない
- 単純な grep だけで重要コンポーネント該当性や urgency を判定しない
- Codex CLI が changelog を読み、構造化分類 JSON を生成する
- 最終 status は、dry-run の機械的結果と Codex CLI の構造化分類をもとに Ansible tasks が判定する

### 14.3 changelog 分類の考え方

`apt changelog` は長く、人間がすべて読む運用は現実的ではない。

そのため、対象パッケージの changelog は Codex CLI に渡し、以下を構造化して出力させる。

- 重要コンポーネントに該当するか
- 該当する場合、その理由
- remove が置換に見えるか
- major / minor upgrade 疑いがあるか
- security-sensitive な変更があるか
- urgency の候補
- 判断に使った changelog の根拠
- confidence

Codex CLI は自然文の説明だけでなく、JSON で分類結果を返す。

例:

```json
{
  "package": "qemu-server",
  "important_component": true,
  "important_reason": "VM lifecycle and QEMU integration component",
  "security_sensitive": false,
  "urgency": "NORMAL",
  "major_upgrade_suspected": false,
  "replacement_suspected": false,
  "evidence": [
    "changelog mentions VM start/stop behavior"
  ],
  "confidence": "medium"
}
```

この分類結果は、最終 status 判定の入力として使う。

ただし Codex CLI は、`apt-get dist-upgrade` を実行したり、`BLOCKED` を解除したり、パッチ適用を判断したりしない。

### 14.4 Roadmap / Release Notes

Proxmox では、Roadmap ページ内の各バージョン節が Release Notes として案内される。

用途:

- Proxmox VE 全体の大きな変更点確認
- major / minor release の確認
- pve-manager / QEMU / LXC / HA など、大きめの変更概要確認

Roadmap を参照する条件:

- `MAJOR_UPGRADE_DETECTED`
- Proxmox major version が変わる疑い
- Proxmox minor version が変わる疑い
- pve-manager / qemu / lxc / ha / sdn など広範囲の中核更新
- changelog だけでは変更の全体像が見えない場合

URL:

```text
https://pve.proxmox.com/wiki/Roadmap
```

### 14.5 Proxmox VE System Software Updates

用途:

- Proxmox 公式の更新手順確認
- `apt-get update` / `apt-get dist-upgrade` を使う根拠

URL:

```text
https://pve.proxmox.com/wiki/System_Software_Updates
```

### 14.6 Proxmox Security Advisories

用途:

- Proxmox project または core dependencies に関する security advisory 確認

URL:

```text
https://forum.proxmox.com/threads/official-proxmox-security-advisories-forum-available.149771/
```

### 14.7 Debian Security Tracker

用途:

- Debian 由来パッケージの CVE / DSA / security 状態確認

URL:

```text
https://security-tracker.debian.org/
```

## 15. メール通知ルール

### 15.1 通知対象

| Status | メール |
|---|---|
| `NO_UPDATES` | 送る（件名に明示） |
| `PATCH_READY` 自動適用成功 | 送る |
| `PATCH_READY` pve2 で停止 | 強めに送る |
| `MAINTENANCE_REQUIRED` | 送る |
| `BLOCKED` | 強めに送る |
| `MAJOR_UPGRADE_DETECTED` | 強めに送る |

### 15.2 件名案

```text
[Proxmox Patch] PATCH_READY applied successfully
[Proxmox Patch][STOPPED] pve2 post-healthcheck failed
[Proxmox Patch Dry-run] MAINTENANCE_REQUIRED
[Proxmox Patch Dry-run][BLOCKED] automatic patch stopped
[Proxmox Patch Dry-run][MAJOR] major upgrade suspected
```

### 15.3 PATCH_READY 成功メール

含める内容:

- pve2 apply result
- pve2 post-healthcheck result
- pve1 apply result
- pve1 post-healthcheck result
- reboot-required: yes/no
- 更新パッケージ一覧
- changelog summary は必要最小限

### 15.4 pve2 で停止した場合

含める内容:

- pve2 で停止した理由
- pve1 には進んでいないこと
- 対応が必要であること
- failed task / healthcheck NG の内容
- report path

### 15.5 MAINTENANCE_REQUIRED メール

含める内容:

- Status
- Urgency
- 判定理由
- 重要コンポーネント一覧
- remove / install / upgrade の関係
- changelog summary
- Roadmap 参照が必要か
- 推奨アクション
- Codex CLI による分類・要約結果

### 15.6 BLOCKED メール

含める内容:

- Status
- 適用禁止であること
- 自動 apply timer を止めたこと
- pve1 / pve2 どちらにも適用していないこと
- どの contingency route に入ったか
- return condition

---

## 16. Codex CLI 利用方針

### 16.1 Codex CLI の役割

Codex CLI は、patch dry-run report と changelog を読み、構造化された分類結果と説明メールを生成するために使う。

Codex CLI は単なる説明文生成だけでなく、以下の分類を補助する。

- 重要コンポーネントに該当するか
- remove が置換に見えるか
- major / minor upgrade 疑いがあるか
- security-sensitive な変更があるか
- urgency を LOW / NORMAL / HIGH / URGENT のどれに置くべきか
- メールに載せるべき changelog 要約

ただし、Codex CLI は最終的なパッチ適用判断者ではない。

重要ルール:

```text
Codex は changelog 分類エンジン。
Codex は説明生成エンジン。
Codex は実行エンジンではない。
```

### 16.2 Codex CLI の入力

Codex CLI に渡す入力:

- dry-run JSON（Ansible が生成。important_component / security_repo / is_new 等のフラグ含む）
- 更新対象パッケージの changelog 差分（現在インストール済みバージョン以降のエントリのみ）
- 新規インストールパッケージの場合は最新エントリ1件のみ
- `docs/ops/proxmox_patch_policy.md`（URGENT / HIGH 判断基準テーブルを含む）

Ansible 側で事前に判定した情報（重要コンポーネント該当性、セキュリティリポジトリ由来か、新規インストールか、remove を伴うかなど）も入力として付与する。

### 16.3 Codex CLI の出力

Codex CLI は、最低限以下の情報を構造化して出力する。

- 重要コンポーネント更新の一覧と理由
- 重要コンポーネント削除の一覧
- 置換が疑われるか
- major upgrade が疑われるか
- security-sensitive な更新の一覧
- urgency 候補（LOW / NORMAL / HIGH / URGENT）
- changelog から識別した脆弱性タイプ（LPE / RCE / DoS / XSS など）
- メール件名と本文
- レポート MD

urgency 候補は Codex の識別結果に基づく候補であり、最終判定は Ansible tasks が行う。

Ansible tasks はこの出力を読み、patch policy の URGENT / HIGH 判断基準テーブルと照合して最終 status / urgency を確定する。

### 16.4 Codex CLI にやらせないこと

Codex CLI に以下はさせない。

- `apt-get dist-upgrade` の実行
- `apt upgrade` / `apt full-upgrade` の実行
- reboot 実行
- Proxmox ホスト上での直接実行
- Proxmox 設定変更
- `BLOCKED` の解除
- `MAJOR_UPGRADE_DETECTED` の解除
- policy に反する status 上書き
- pve1 / pve2 への apply 判断
- apply timer の有効化

### 16.5 最終判定の責務分離

責務は以下のように分離する。

| 処理 | 担当 |
|---|---|
| apt simulation 実行 | Ansible / shell |
| package list 収集 | Ansible / shell |
| changelog 差分取得 | Ansible / shell |
| important_component 判定 | Ansible tasks（パッケージ名リストと照合） |
| security_repo 判定 | Ansible / shell（リポジトリ名判定） |
| changelog 内の CVE タイプ識別 | Codex CLI（LPE / RCE / DoS 等） |
| urgency 候補生成 | Codex CLI |
| URGENT / HIGH 条件への照合 | Ansible tasks（patch policy テーブルと照合） |
| 最終 status / urgency 判定 | Ansible tasks |
| 日本語メール本文生成 | Codex CLI |
| 日本語レポート MD 生成 | Codex CLI |
| patch apply | Ansible |
| apply 可否制御 | Ansible tasks |

### 16.6 実行場所

Codex CLI は以下で実行する。

- ansy
- quory
- macOS

実行しない場所:

- pve1
- pve2
- authy
- Sophos Firewall VM

### 16.7 Codex CLI セットアップ

Codex CLI のインストールと初期設定は、このポリシー文書の範囲外とする。

本ポリシーでは、以下を前提とする。

- ansy / quory / macOS のいずれかで Codex CLI が利用可能である
- Codex CLI は別チャット / 別手順書で導入する
- Proxmox ホストには Codex CLI をインストールしない
- Proxmox patch apply の実行中に Codex CLI の導入・更新は行わない

Codex CLI の導入確認は、patch dry-run 実装前の事前準備として扱う。

### 16.8 Ansible control node の配置ルール

PATCH_READY 自動適用では、Ansible control node が patch 対象ノード上に存在してはならない。

理由:

- patch 対象ノードを reboot した場合、control node 自体が停止する
- apply / reboot / post-healthcheck / 次ノードへの処理が継続できない
- pve1 / pve2 の連続適用フローが破綻する

### 16.8.1 quory 到着前

quory 到着前に ansy で運用する場合、ansy が Proxmox 上の VM なら full flow は実行しない。

```text
ansy が pve1 上にいる:
  pve2 の単一ノード patch のみ可

ansy が pve2 上にいる:
  pve1 の単一ノード patch のみ可
```

ansy 自身を同一playbook内で migrate して処理を継続する運用はしない。

### 16.8.2 quory 到着後

quory 到着後は、quory を Ansible control node とする。

```text
quory:
  Proxmox クラスタ外の物理 control node

許可:
  pve2 → pve1 → VM復帰 の full flow
```

quory が pve1 / pve2 の reboot 影響を受けない場合、土曜朝の full flow を自動実行してよい。

### 16.8.3 apply 停止条件

control node が patch 対象ノード上にいる場合、apply は停止する。

control node が pve1 / pve2 の両方の patch sequence 中に停止し得る場所にある場合、full flow は実行しない。

### 16.9 初期テスト方針

quory 到着前は ansy で手動実行する。

目的:

- Codex CLI の分類品質確認
- changelog 要約の品質確認
- 重要コンポーネント該当性の判定品質確認
- urgency 判定品質確認
- メール本文の読みやすさ確認
- PATCH_READY / MAINTENANCE_REQUIRED / BLOCKED の説明品質確認
- 誤った推奨が出ないか確認

## 17. 実適用時の標準手順

### 17.1 Mode A: PATCH_READY full flow

quory / 外部 control node から実行する。

```text
1. control node が Proxmox クラスタ外にあることを確認
2. pve1 healthcheck OK
3. pve2 healthcheck OK
4. pve2 dry-run status PATCH_READY
5. pve2 VM / CT 所在確認
6. pve2 VM / CT 退避
7. pve2 apply
8. pve2 reboot if required
9. pve2 post-healthcheck OK
10. pve1 VM / CT 所在確認
11. pve1 VM / CT 退避
12. pve1 apply
13. pve1 reboot if required
14. pve1 post-healthcheck OK
15. VM / CT を home node へ戻す
16. final healthcheck
17. summary mail
```

### 17.2 Mode B: PATCH_READY single-node flow

ansy が Proxmox 上の VM として動いている暫定運用で使う。

```text
1. control node の所在確認
2. target node が control node の稼働ノードではないことを確認
3. target node healthcheck OK
4. 退避先または反対側ノードを利用する場合は、実行前段・上位 playbook・手動手順で反対側ノードの healthcheck OK を確認
5. target node の事前 dry-run または apply 直前 re-dry-run で PATCH_READY 相当を確認
6. target node VM / CT 所在確認
7. target node VM / CT 退避
8. target node apply
9. target node reboot if required
10. target node post-healthcheck OK
11. summary mail
```

Mode B では、もう一方のノードへ自動で進まない。

### 17.3 MAINTENANCE_REQUIRED 手動適用

```text
1. メール内容確認
2. changelog summary 確認
3. 必要に応じて Roadmap / Security Advisory 確認
4. pve2 の重要 VM / CT 退避
5. メンテナンス枠を確保
6. pve2 healthcheck OK
7. pve2 手動 apply
8. reboot if needed
9. pve2 post-healthcheck
10. pve2 安定確認
11. pve1 は別途判断
```

### 17.4 Mode C: MAINTENANCE_REQUIRED 手動 apply（playbook 使用）

MAINTENANCE_REQUIRED が検出された場合に、手動 apply モードを使って playbook 経由で適用する。

```text
1. 通知メールで MAINTENANCE_REQUIRED の内容を確認する
2. changelog summary を確認する
3. 必要に応じて Roadmap / Security Advisory を確認する
4. メンテナンス枠を確保する
5. 対象ノードの healthcheck を確認する
6. 対象ノード上の VM / CT の退避を確認する
7. 手動 apply モードと明示的確認変数を指定して playbook を実行する
8. apply と reboot（必要な場合）が完了したことを確認する
9. post-healthcheck を実行し、OK であることを確認する
```

pve1 は pve2 成功後に別途判断する。

---

## 18. 復旧方針

### 18.1 基本方針

```text
Proxmox ホスト OS の rollback は原則しない。
壊れたら再インストールする。
```

### 18.2 pve2 が壊れた場合

- pve1 を守る
- pve1 が生きているうちに pve2 を再インストールする
- pve2 をクラスタに戻す
- replication / storage / network を再構成する

### 18.3 pve1 が壊れた場合

- pve2 に VM / CT が退避済みであることを前提に復旧する
- pve1 を再インストールする
- クラスタ復帰手順を別途整備する

### 18.4 バックアップ対象

Proxmox ホスト設定は「ファイルを戻して復元」ではなく、再構築メモとして保存する。

保存すべき情報:

- hostname
- management IP
- Server VLAN IP
- NIC 名
- NIC 割当
- bridge 設定
- VLAN 設定
- ZFS pool 名
- storage 設定
- apt repository
- SSH 公開鍵
- cluster join 方針
- replication 設定
- `/etc/network/interfaces`
- `/etc/hosts`
- `/etc/hostname`

---

## 19. Sophos 移行前の必須条件

Sophos Firewall VM を Proxmox に移行する前に、以下を満たす。

- pve2 で patch dry-run 運用を確認
- pve2 で `PATCH_READY` 自動適用を 1 回以上成功
- pve2 reboot 後に healthcheck OK を確認
- pve1 / pve2 両方で healthcheck OK
- pve2 再インストール手順がある
- Proxmox ネットワーク設定の再構築メモがある
- Sophos VM の backup / restore 手順がある
- Sophos VM の稼働ノード方針が決まっている
- Sophos VM の退避 / 停止 / 移動方針が決まっている
- 家庭内ネットワーク停止時の手順がある

---

## 20. Sophos 移行後の追加ルール

Sophos Firewall VM が Proxmox 上で稼働している場合、以下を追加する。

- Sophos VM が対象ノード上にいる場合、そのノードを直接パッチしない
- 先に Sophos VM を別ノードへ移動できるか確認する
- Sophos 停止時の家庭内ネットワーク影響を許容できる時間帯のみ実施する
- WAN / LAN / FAMILY / NAS / Guest などの NIC / VLAN 割当を確認してから実施する
- Sophos VM 移動後に通信確認を行う
- Sophos 稼働ノードへの `MAINTENANCE_REQUIRED` 適用は、通常より慎重に扱う
- Sophos が Internet に面していることを踏まえ、urgency HIGH / URGENT は早めに判断する

---

## 21. 今後の実装順序

1. `docs/ops/proxmox_patch_policy.md` を確定
2. Proxmox 上の VM/CT に `prefer<node名>` タグを付与
3. `proxmox_healthcheck` 実装
4. `proxmox_patch_dryrun` 実装
5. `proxmox_evacuate_node.yml` 実装
6. `proxmox_restore_vm_placement.yml` 実装
7. ansy で dry-run 手動実行
8. `apt changelog` 取得処理を実装
9. Codex CLI で changelog 分類 JSON 生成テスト
10. Ansible tasks で最終 status 判定テスト
11. Codex CLI でメール本文生成テスト
12. メール送信テスト
13. `proxmox_evacuate_node.yml` を pve2 対象で検証
14. `proxmox_patch_apply_node.yml` を pve2 単一ノードで検証
15. `proxmox_evacuate_node.yml` を pve1 対象で検証
16. `proxmox_patch_apply_node.yml` を pve1 単一ノードで検証
17. quory 到着後に `proxmox_patch_weekly_full.yml` を検証
18. `MAINTENANCE_REQUIRED` のメール品質確認
19. `BLOCKED` の Contingency Plan 通知品質確認
20. quory 到着後に systemd timer 化
21. Sophos 移行判断


## 22. 参考リンク

- Proxmox VE System Software Updates  
  https://pve.proxmox.com/wiki/System_Software_Updates

- Proxmox VE Roadmap / Release Notes  
  https://pve.proxmox.com/wiki/Roadmap

- Proxmox Security Advisories Forum  
  https://forum.proxmox.com/threads/official-proxmox-security-advisories-forum-available.149771/

- Debian Security Tracker  
  https://security-tracker.debian.org/

- Codex CLI  
  https://developers.openai.com/codex/cli

- Codex non-interactive mode  
  https://developers.openai.com/codex/noninteractive
