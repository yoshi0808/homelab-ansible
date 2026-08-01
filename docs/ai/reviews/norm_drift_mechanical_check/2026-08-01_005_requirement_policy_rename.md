# requirement — Proxmox Policyの改名とscope拡張(Step 3)

日付: 2026-08-01
状態: 確定(Yoshinobu承認済み)
前提: `2026-08-01_001_survey.md` §3.2(SB-020が②「存在しか検査できない」と判定された経緯)

## 1. 背景と目的

Step 1の棚卸しで、`playbooks/proxmox_*.yml` のうち3本が `proxmox_patch_policy.md` SB-020の安全度表に載っていないことが分かった。当初これは「掲載漏れ」と見えたが、Yoshinobuの判断は違った。

> ファイル名が proxmox patch policy というからややこしくなるのであって、proxmox operation policy なら何の問題もない

**scopeが曖昧だったのではなく、文書の名前が実態より狭かった。** 本Policyは既に patch 以外(healthcheck、退避・復帰、read-only点検)を規定しており、名前だけが patch に留まっていた。

したがって本作業は「表に3行足す」ことではなく、**文書のscopeを実態に合わせ、名前をそれに追随させる**ことである。

## 2. やること

### 2.1 改名

| 現在 | 変更後 |
|---|---|
| `docs/ai/policies/proxmox_patch_policy.md` | `docs/ai/policies/proxmox_operations_policy.md` |
| `docs/ai/context/operations/proxmox-patch.md` | `docs/ai/context/operations/proxmox-operations.md` |

`management` ではなく `operations` を選んだ理由: 本Policyの SB-002 が「**管理面**」をProxmoxの管理プレーンの意味で既に使っており、`management` だと文書内で語が衝突する。加えて `docs/ai/context/operations/` が既にこの語を使っている。

### 2.2 scope宣言の拡張

**改名だけでは目的を達しない。** 文書自身のscope宣言が3箇所とも patch 限定であり、そのままでは次に読む人が「backup検証は対象外」と再導出する。

| 箇所 | 現在の文言 |
|---|---|
| タイトル | `# Proxmox Patch Policy` |
| 冒頭リード | 「本書はProxmox VE hostの**patchに関する**許可、禁止、停止条件の正本である」 |
| SB-001 | 「本Policyは、Proxmox VE hostへの**patch**を安全に判断、適用、停止するため、次を必須目的とする」 |

これらを、**SB-020の安全度表に載る全playbookを包含するscope**へ広げる。具体的な文言は指定しない。

### 2.3 SB-020 安全度表への3本の追加

安全度は現物の記載から決めた。推測ではない。

| Playbook | 安全度 | 根拠 |
|---|---|---|
| `proxmox_hw_check.yml` | **safe** | ヘッダが `# tester-gate: safe-readonly`。SB-095 が `proxmox_healthcheck.yml` と並べて read-only点検と名指ししている |
| `proxmox_snapshot_check.yml` | **safe** | ヘッダが `# tester-gate: safe-readonly` |
| `proxmox_backup_restore_verify.yml` | **controlled apply** | playbookヘッダ自身が `Monthly VM backup restore-verify (controlled apply).` と記載。VMID 999へ復元→起動確認→破棄 |

### 2.4 live参照の張り替え

| 対象 | live層(張り替える) | `docs/ai/reviews/`(**張り替えない**) |
|---|---|---|
| `proxmox_patch_policy` | 13ファイル・18行 | 118ファイル・449行 |
| `proxmox-patch.md` | 3ファイル・6行 | 56行 |

live層にはコードが4件含まれる: `scripts/codex-classify.sh`、`roles/proxmox_evacuate_node/defaults/main.yml`、`roles/proxmox_restore_vm_placement/defaults/main.yml`、`roles/recovery_exec/templates/AGENTS.md.j2`。

> **`docs/ai/reviews/` 配下を書き換えてはならない。** 案件当時の記録であり、当時のパスを指しているのが正しい。旧 `core.md` 退役でも同じ扱いをした(live参照だけ張り替え、履歴は `git log` が持つ)。

`docs/ai/policy-migration-map.md` はPolicyの追跡表であり、live層として更新対象に含む。

## 3. やらないこと

- **`SB-` 接頭辞とID番号を変更しない。** patch由来の接頭辞ではなく、かつ変更履歴が「退番: SB-049(再利用しない)」と番号を資産として扱っているため、振り直しは破壊的である。
- **既存の規範文の意味を変えない。** 本作業はscopeの宣言と名前の変更であり、許可・禁止・停止条件そのものの改訂ではない。
- `ubuntu_vm_patch_policy.md` は対象外。同じ形の問題を持つ可能性があるが、本案件では扱わない。

## 4. 受入条件

| AC | 内容 |
|---|---|
| AC1 | 2つのファイルが改名され、live層の参照がすべて新しいパスを指す。`proxmox_patch_policy` / `context/operations/proxmox-patch.md` を指すlive層の参照が0件 |
| AC2 | `docs/ai/reviews/` 配下が1行も変更されていない |
| AC3 | タイトル・冒頭リード・SB-001のいずれにも、scopeを patch に限定する表現が残っていない |
| AC4 | SB-020の表に3本が§2.3の安全度で追加されている |
| AC5 | **`python3 scripts/check-doc-consistency.py` が exit 0**(改名で規範層に壊れたリンクが生じていないことの機械的な証拠) |
| AC6 | Policyの変更履歴に本変更の行が追加されている。既存の変更履歴の記法に合わせる |
| AC7 | **scope拡張によって、既存の許可・禁止・停止条件の適用範囲が意図せず広がっていないこと。** 特に「これまで対象外だったplaybookが、既存の禁止条項に抵触する状態になっていないか」を確認し、該当があれば実装せず報告する |

## 5. 実行identityと権限境界

**到達してはいけない状態**として示す。

- **実ホストに接続した状態で報告が返らないこと。** 本作業は ansy のリポジトリ作業ツリーと `/tmp` 配下で完結する
- **`docs/ai/reviews/` 配下(本案件フォルダの成果物を除く)が変更された状態で報告が返らないこと**
- **`scripts/check-doc-consistency.py`、`scripts/git-pre-commit-check.sh`、`.gitignore`、`scripts/tests/` が変更された状態で報告が返らないこと。** これらは別工程の成果物であり、本作業では検証に使うだけである
- **`git add` / `git commit` / `git push` が実行された状態で報告が返らないこと**
- 権限が昇格した状態に到達しないこと

harnessの安全機構にブロックされた場合、別の形で同じ結果へ到達せず、ブロックされた事実を報告に含めて返すこと。

## 6. 自己検証で確認できれば十分なこと

- AC1〜AC7の充足
- 変更したファイルの集合が§5の範囲に収まっていること
- 本ファイルが参照しているパスが実在すること

## 7. 成果物

- 上記の変更
- 実装記録 `docs/ai/reviews/norm_drift_mechanical_check/2026-08-01_006_implement_policy_rename.md`
