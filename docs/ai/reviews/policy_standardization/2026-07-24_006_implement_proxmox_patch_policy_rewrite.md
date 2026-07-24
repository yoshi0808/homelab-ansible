# Proxmox Patch Policy 標準構造書換 Phase 2 実装記録

## 1. 実装範囲

Phase 1の正本は `2026-07-24_005_investigation_proxmox_patch_policy_rewrite.md`、旧Policy比較元は同記録が固定したGit HEAD blobである。実機・Ansible実行は行わず、文書の再構成だけを実施した。

変更対象:

- `docs/ai/policies/proxmox_patch_policy.md`
- `docs/ai/context/system/proxmox.md`
- `docs/ai/context/ansible/proxmox-patch.md`
- `docs/ai/context/operations/proxmox-patch.md`
- 本006

## 2. 実装判断

- 新Policyは目的、対象と実行範囲、対応するPlaybook、判断軸、ライフサイクル・処理フロー、通知方針、制約・禁止事項、変更履歴の標準8節を順番どおり各1回置いた。
- 旧§22は規範節を増やさず「付録A 出典」としてPolicyに維持した。
- Policy本文中の `SB-001`〜`SB-090` HTML commentは監査用到達markerであり、表示本文の規範ではない。
- Contextは非規範であること、Policyが正本で競合時に優先することを各冒頭に明記した。
- Repository Contextは複数入口・role・report・分類CLIの横断契約だけを記録し、単一taskの逐語複製を避けた。
- Operations ContextはMode、retry、evacuation / restore、再構築、Sophos確認順を収容した。
- System Contextは既存記述を重複させず、分類CLIとcontrol nodeの配置事実だけを追記した。

## 3. migration-map 19行の移行実績

| # | 旧HEAD範囲 | 移動先 | 新Policyの核・到達行 |
|---|---|---|---|
| 1 | §4 L145-151 | `context/system/proxmox.md` L9-13 | node順序・続行条件 L39-44 |
| 2 | §5.2 L190-228 | `context/ansible/proxmox-patch.md` L18-24 | tag正本・命名・意味 L48-55 |
| 3 | §5.2 L246-261 | `context/ansible/proxmox-patch.md` L18-24。roadmapは005 | HA/non-HA退避・復帰 L281-282 |
| 4 | §6.2-§6.7 L360-827 | `context/ansible/proxmox-patch.md` L5-69 | 入口、安全度、条件、停止 L77-147 |
| 5 | §6.5 L610-688 | `context/operations/proxmox-patch.md` L42-49 | retry許可・最終判定 L246-247/L293-294 |
| 6 | §11.2 L1193-1234 | `context/operations/proxmox-patch.md` L5-40 | Mode許可範囲 L59-75 |
| 7 | §11.3-§11.4 L1236-1284 | `context/operations/proxmox-patch.md` L5-40 | control node・続行gate L59-75/L267-328 |
| 8 | §14.2-§14.3 L1424-1482 | `context/ansible/proxmox-patch.md` L42-69 | 情報源、Ansible最終判定、AI禁止 L249-262/L382-389 |
| 9 | §16.1-§16.3 L1619-1669 | `context/ansible/proxmox-patch.md` L42-62 | AI候補・Ansible最終判断 L255-262 |
| 10 | §16.5 L1686-1704 | `context/ansible/proxmox-patch.md` L42-62 | 決定論的apply gate L261-262 |
| 11 | §16.6-§16.7 L1706-1732 | `context/system/proxmox.md` L41-46 | 分類CLIのallowlist / denylist L388-389 |
| 12 | §16.8.0-§16.8.2 L1744-1783 | `context/system/proxmox.md` L41-46。履歴は005 | control node禁止・停止 L65-75/L391-392 |
| 13 | §16.9 L1791-1803 | 005のPhase 1検査・履歴 | Policy核なし |
| 14 | §17 L1805-1884 | `context/operations/proxmox-patch.md` L5-40 | 開始・続行・人間確認gate L267-328 |
| 15 | §18 L1886-1930 | `context/operations/proxmox-patch.md` L62-84 | rollback禁止・再構築原則 L330-334 |
| 16 | §19 L1933-1947 | 達成証跡は005 | 全安全前提 L396-409 |
| 17 | §20 L1950-1960 | `context/operations/proxmox-patch.md` L86-90、配置事実は`context/system/proxmox.md` | 共通条件、直接patch禁止、時間帯、Urgency L336-337/L410-414 |
| 18 | §21 L1964-1986 | 005のproject plan履歴 | Policy核なし |
| 19 | §22 L1989-2007 | Policyに維持 | 付録A L423-430 |

## 4. SB-001〜SB-090 新Policy到達行index

marker行は到達開始点である。005 §4.3に従い、Reviewerはmarker直後の各表行・箇条書き・規範文を旧HEADの各原文行と個別比較する。

| SB | 新Policy到達開始 | 実装状態 |
|---|---|---|
| `SB-001` | `docs/ai/policies/proxmox_patch_policy.md` L7 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-002` | `docs/ai/policies/proxmox_patch_policy.md` L22 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-003` | `docs/ai/policies/proxmox_patch_policy.md` L25 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-004` | `docs/ai/policies/proxmox_patch_policy.md` L28 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-005` | `docs/ai/policies/proxmox_patch_policy.md` L31 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-006` | `docs/ai/policies/proxmox_patch_policy.md` L34 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-007` | `docs/ai/policies/proxmox_patch_policy.md` L152 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-008` | `docs/ai/policies/proxmox_patch_policy.md` L161 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-009` | `docs/ai/policies/proxmox_patch_policy.md` L164 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-010` | `docs/ai/policies/proxmox_patch_policy.md` L167 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-011` | `docs/ai/policies/proxmox_patch_policy.md` L39 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-012` | `docs/ai/policies/proxmox_patch_policy.md` L45 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-013` | `docs/ai/policies/proxmox_patch_policy.md` L48 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-014` | `docs/ai/policies/proxmox_patch_policy.md` L281 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-015` | `docs/ai/policies/proxmox_patch_policy.md` L284 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-016` | `docs/ai/policies/proxmox_patch_policy.md` L287 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-017` | `docs/ai/policies/proxmox_patch_policy.md` L290 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-018` | `docs/ai/policies/proxmox_patch_policy.md` L51 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-019` | `docs/ai/policies/proxmox_patch_policy.md` L54 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-020` | `docs/ai/policies/proxmox_patch_policy.md` L81 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-021` | `docs/ai/policies/proxmox_patch_policy.md` L93 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-022` | `docs/ai/policies/proxmox_patch_policy.md` L96 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-023` | `docs/ai/policies/proxmox_patch_policy.md` L99 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-024` | `docs/ai/policies/proxmox_patch_policy.md` L243 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-025` | `docs/ai/policies/proxmox_patch_policy.md` L102 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-026` | `docs/ai/policies/proxmox_patch_policy.md` L114 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-027` | `docs/ai/policies/proxmox_patch_policy.md` L122 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-028` | `docs/ai/policies/proxmox_patch_policy.md` L125 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-029` | `docs/ai/policies/proxmox_patch_policy.md` L293 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-030` | `docs/ai/policies/proxmox_patch_policy.md` L246 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-031` | `docs/ai/policies/proxmox_patch_policy.md` L128 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-032` | `docs/ai/policies/proxmox_patch_policy.md` L136 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-033` | `docs/ai/policies/proxmox_patch_policy.md` L139 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-034` | `docs/ai/policies/proxmox_patch_policy.md` L142 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-035` | `docs/ai/policies/proxmox_patch_policy.md` L145 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-036` | `docs/ai/policies/proxmox_patch_policy.md` L172 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-037` | `docs/ai/policies/proxmox_patch_policy.md` L195 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-038` | `docs/ai/policies/proxmox_patch_policy.md` L198 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-039` | `docs/ai/policies/proxmox_patch_policy.md` L201 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-040` | `docs/ai/policies/proxmox_patch_policy.md` L204 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-041` | `docs/ai/policies/proxmox_patch_policy.md` L207 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-042` | `docs/ai/policies/proxmox_patch_policy.md` L221 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-043` | `docs/ai/policies/proxmox_patch_policy.md` L224 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-044` | `docs/ai/policies/proxmox_patch_policy.md` L229 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-045` | `docs/ai/policies/proxmox_patch_policy.md` L232 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-046` | `docs/ai/policies/proxmox_patch_policy.md` L238 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-047` | `docs/ai/policies/proxmox_patch_policy.md` L59 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-048` | `docs/ai/policies/proxmox_patch_policy.md` L62 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-049` | `docs/ai/policies/proxmox_patch_policy.md` L296 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-050` | `docs/ai/policies/proxmox_patch_policy.md` L359 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-051` | `docs/ai/policies/proxmox_patch_policy.md` L362 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-052` | `docs/ai/policies/proxmox_patch_policy.md` L365 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-053` | `docs/ai/policies/proxmox_patch_policy.md` L368 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-054` | `docs/ai/policies/proxmox_patch_policy.md` L371 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-055` | `docs/ai/policies/proxmox_patch_policy.md` L374 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-056` | `docs/ai/policies/proxmox_patch_policy.md` L341 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-057` | `docs/ai/policies/proxmox_patch_policy.md` L299 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-058` | `docs/ai/policies/proxmox_patch_policy.md` L302 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-059` | `docs/ai/policies/proxmox_patch_policy.md` L377 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-060` | `docs/ai/policies/proxmox_patch_policy.md` L307 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-061` | `docs/ai/policies/proxmox_patch_policy.md` L310 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-062` | `docs/ai/policies/proxmox_patch_policy.md` L313 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-063` | `docs/ai/policies/proxmox_patch_policy.md` L316 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-064` | `docs/ai/policies/proxmox_patch_policy.md` L319 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-065` | `docs/ai/policies/proxmox_patch_policy.md` L322 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-066` | `docs/ai/policies/proxmox_patch_policy.md` L249 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-067` | `docs/ai/policies/proxmox_patch_policy.md` L382 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-068` | `docs/ai/policies/proxmox_patch_policy.md` L252 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-069` | `docs/ai/policies/proxmox_patch_policy.md` L344 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-070` | `docs/ai/policies/proxmox_patch_policy.md` L347 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-071` | `docs/ai/policies/proxmox_patch_policy.md` L255 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-072` | `docs/ai/policies/proxmox_patch_policy.md` L258 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-073` | `docs/ai/policies/proxmox_patch_policy.md` L385 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-074` | `docs/ai/policies/proxmox_patch_policy.md` L261 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-075` | `docs/ai/policies/proxmox_patch_policy.md` L388 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-076` | `docs/ai/policies/proxmox_patch_policy.md` L65 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-077` | `docs/ai/policies/proxmox_patch_policy.md` L68 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-078` | `docs/ai/policies/proxmox_patch_policy.md` L71 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-079` | `docs/ai/policies/proxmox_patch_policy.md` L391 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-080` | `docs/ai/policies/proxmox_patch_policy.md` L327 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-081` | `docs/ai/policies/proxmox_patch_policy.md` L330 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-082` | `docs/ai/policies/proxmox_patch_policy.md` L333 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-083` | `docs/ai/policies/proxmox_patch_policy.md` L396 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-084` | `docs/ai/policies/proxmox_patch_policy.md` L410 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-085` | `docs/ai/policies/proxmox_patch_policy.md` L336 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-086` | `docs/ai/policies/proxmox_patch_policy.md` L413 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-087` | `docs/ai/policies/proxmox_patch_policy.md` L117 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-088` | `docs/ai/policies/proxmox_patch_policy.md` L131 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-089` | `docs/ai/policies/proxmox_patch_policy.md` L264 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |
| `SB-090` | `docs/ai/policies/proxmox_patch_policy.md` L74 | 保持。marker直後の規範文・表・箇条書きを旧HEAD行と逐行比較する |

## 5. 選択理由と重複処理

| 判断 | 理由 |
|---|---|
| System Contextは必要最小追記 | pve2先行、quory、health gateは既存記述済みで、再掲すると事実の二重管理になる |
| patch専用Repository Contextを新設 | 6入口と複数role、report、分類CLI契約は横断地図として価値がある |
| patch専用Operations Contextを新設 | Mode、retry、復旧は複数roleを跨ぐ順序で、単一role docsにもSystem Contextにも収まらない |
| 新Skillを作らない | 分類CLI契約はホームラボ固有であり、再利用可能な汎用手順ではない |
| §19条件をPolicyへ全保持 | 達成日は履歴だが、移行前に全条件を満たす義務は継続する安全境界である |
| §20を分割 | 直接patch禁止・時間帯・UrgencyはPolicy、確認順はOperations Context、配置はSystem Contextに属する |

## 6. 自己検査実績

### 6.1 007 review補正

| review | Policy補正 | 005 / 006補正 |
|---|---|---|
| must-fix #1 | SB-023 L99-100へ旧L440の両node healthcheck開始gateを復元 | 005 SB-023の旧行・要約を更新。006 indexを再生成 |
| must-fix #2 | SB-041 L207-219へ旧L995-1000の6判断条件を復元 | 005 SB-041の種別・要約を更新。006 indexを再生成 |
| must-fix #3 | SB-068 L252-253へ旧L1500のRoadmap参照条件を復元 | 005 SB-068要約を更新。006 indexを再生成 |
| must-fix #4 | SB-075 L388-389へ旧L1708-1719の実行場所allowlist / denylistを復元 | 005 SB-075の種別・要約を更新。006 indexを再生成 |
| must-fix #5 | SB-084〜086 L336-337/L410-414へ旧L1952の共通条件を復元 | 005の3 SBへ旧L1952を追加。006 indexを再生成 |

005のPhase 1実測結果は当時の記録として変更せず、007によるledger補正を005 §9.1.1へ追記した。Context 3本は本修正で編集していない。

### 6.2 最終機械検査

| 検査 | 実績 |
|---|---|
| 標準見出し | 8件、各1回、順序違反0。付録A 1件 |
| migration追跡 | 19行、列不正0 |
| safety boundary | SB marker 90件、一意。欠番0、重複0、006 index 90行、到達先欠落0 |
| 007補正 | must-fix 5件の旧HEAD規範を再照合。SB index 90件の行不一致0 |
| Context境界 | 3 Contextすべてに非規範宣言とPolicy linkあり |
| 重複・旧path | Policy標準見出し重複0、obsolete Policy path 0 |
| 禁止実値 | IPv4 literal 0、数値付きVLAN / VM / CT識別子0、認証情報・秘密の実値0 |
| Markdown | 表の空セル0 |
| scope | playbooks / roles diff 0、他Policy diff 0。005はledger補正と§9.1.1追記だけ。Context 3本と007は未編集 |
| whitespace | `git diff --check` PASS。未追跡の2 Contextと005 / 006の`git diff --no-index --check` PASS |
| 実行 | 実機・Ansible実行なし |

## 7. Reviewerへの引継ぎ

005 §4.3に従い、SB範囲を要約単位で合格させず、旧HEADの各箇条書き・表行・規範文を新Policyへ1行ずつ照合する。特に「のみ」「すべて」「明示的確認」「進まない」「自動適用しない」「禁止」「停止」と、条件のAND / OR、node順序、例外範囲を確認する。
