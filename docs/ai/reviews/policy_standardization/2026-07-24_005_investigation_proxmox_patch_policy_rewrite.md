# Proxmox Patch Policy 標準構造書換 Phase 1 調査

## 1. 調査範囲と正本

- requirement: `2026-07-24_004_requirement_proxmox_patch_policy_rewrite.md`
- 旧Policy正本: Git HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79` の `docs/ai/policies/proxmox_patch_policy.md`
- 旧Policy blob: `61a38e445d6d8af4113b0f33e43213c205d2986d`
- 旧Policy規模: 2007行、主section 22件
- Phase 1で編集したファイル: 本調査記録のみ
- 未実施: Policy、Context、playbook、roleの編集、意味的な安全境界変更、実機実行

行番号はすべて上記HEAD snapshotの1始まりである。作業ツリーのPolicy差分はないことを確認した。内部IP、VLAN ID、VM ID、認証情報、秘密情報の実値は本記録へ転載しない。

## 2. A: 標準8節への旧section全量配置計画

### 2.1 新Policyの標準8節

| 新節 | 収容するPolicy核 | 主な旧範囲 |
|---|---|---|
| 1. 目的 | 安全な判断・適用・停止、先行検証、主系保護、復旧原則 | §1 L9-22 |
| 2. 対象と実行範囲 | 対象ノード、Status別の自動・手動範囲、control node別の許可範囲 | §2 L26-67、§4 L153-159、§5 L162-320、§11.1 L1129-1191 |
| 3. 対応するPlaybook | 入口、4安全度、各入口の許可条件・停止条件・非対応範囲 | §6 L324-850 |
| 4. 判断軸 | Status、Urgency、重要コンポーネント、remove、公式情報の優先順位 | §3 L71-141、§7-§10 L852-1123、§14.1/§14.4-§14.7 L1418-1422/L1484-1543 |
| 5. ライフサイクル・処理フロー | preflight、dry-run、退避、apply、reboot、post-check、復帰、保留・復旧への遷移 | §5.3-§5.6 L263-320、§11 L1127-1336、§13 L1356-1412、§17 L1805-1884、§18.1 L1888-1893 |
| 6. 通知方針 | Status別の通知強度、成功・停止・保留・BLOCKED時の必須内容 | §15 L1545-1614、§11.6 L1319 |
| 7. 制約・禁止事項 | 自動適用禁止、部分適用禁止、停止条件、AI権限制限、control node制約、Sophos条件 | §2 L26-67、§6の停止条件、§8-§13、§16のPolicy核、§18.1、§19の安全前提、§20のPolicy核 |
| 8. 変更履歴 | 旧版メタデータと今回の標準化・分離を初回エントリとして記録 | L1-7、新規記録 |

§22 L1989-2007は標準8節外の「出典付録」としてPolicy末尾に維持する。これは9節目ではなく、判断軸から参照される非規範appendixとする。

### 2.2 旧主section 22件の全量配置

| 旧section・行 | 新Policy配置 | 移動先 | 分割方針 |
|---|---|---|---|
| 表題・メタデータ L1-7 | 1、8 | なし | 文書目的と旧版情報を分ける |
| §1 L9-22 | 1 | §22参照以外なし | 目的と安全原則を保持 |
| §2 L26-67 | 2、7 | なし | 許可、禁止、例外を保持 |
| §3 L71-141 | 4 | なし | Status/Urgency定義を保持 |
| §4 L145-159 | 2、5、7 | `context/system/proxmox.md` | L145-151の現状役割を移し、L153-159の順序・続行条件を保持 |
| §5 L162-320 | 2、5、7 | `context/ansible/proxmox-patch.md` | §5.2の接続定義、CLI/Jinja例、role現状、未実装表示を移し、タグ規範、退避・復帰条件、自動migration許可を保持 |
| §6 L324-850 | 3、5、7 | `context/ansible/proxmox-patch.md`、`context/operations/proxmox-patch.md` | 入口・安全度・許可条件・停止条件を保持。処理詳細はRepository Context、§6.5 retry手順はOperations Contextへ移す |
| §7 L852-887 | 4 | なし | 重要コンポーネント判定を保持 |
| §8 L891-1017 | 4、5、7 | なし | 各Statusの条件・行動を保持 |
| §9 L1019-1047 | 4、7 | なし | remove分類と禁止を保持 |
| §10 L1049-1125 | 4、7 | `context/ansible/proxmox-patch.md` | 判断材料と規範を保持し、単一コマンド例はRepository Contextへ移す |
| §11 L1127-1338 | 2、5、7 | `context/operations/proxmox-patch.md` | Mode許可範囲・停止条件・reboot gateを保持。仮時刻と逐次手順はOperations Contextへ移す |
| §12 L1340-1354 | 5、7 | なし | 保留、再評価、手動確認を保持 |
| §13 L1356-1414 | 5、7 | なし | BLOCKEDの禁止、route、復帰条件を保持 |
| §14 L1416-1544 | 4、付録 | `context/ansible/proxmox-patch.md` | 情報源の優先順位と最終判定責務を保持。CLI契約・例はRepository Contextへ移す |
| §15 L1545-1614 | 6 | なし | 通知契約を保持 |
| §16 L1617-1803 | 4、7 | `context/ansible/proxmox-patch.md`、`context/system/proxmox.md`、本005 | AIを最終判断者にしない規範と禁止、control node停止条件を保持。CLI契約はRepository Context、配置現状はSystem Context、初期テスト計画は本005へ移す |
| §17 L1805-1884 | 5、7 | `context/operations/proxmox-patch.md` | 開始・続行・停止・人間確認gateを保持し、重複する逐次runbookを移す |
| §18 L1886-1930 | 5、7 | `context/operations/proxmox-patch.md` | §18.1を保持。§18.2-§18.4の復旧・再構築手順を移す |
| §19 L1933-1947 | 7 | 本005 | Sophos稼働時の安全前提をPolicyに保持し、移行時点の達成確認・計画履歴を本005へ移す |
| §20 L1950-1962 | 5、7 | `context/operations/proxmox-patch.md`、`context/system/proxmox.md` | patch禁止・時間帯・慎重判断を保持。配置事実と通信確認手順を分離する |
| §21 L1964-1988 | 8の移行根拠のみ | 本005 | 時点依存project planをPolicyから除く |
| §22 L1989-2007 | 出典付録 | なし | Policyに維持する |

## 3. B: migration-map実測19行の追跡表

requirementの「18項目」は移動対象数を表す。migration-mapの表は§22を含む19行であり、本表は18移動候補と1維持項目の全19行を追跡する。

| # | migration-map項目 | Phase 2受け皿 | Policyに残す核 | 状態 |
|---|---|---|---|---|
| 1 | §4 L145-151 | 既存 `docs/ai/context/system/proxmox.md` | L153-159のpve2先行、pve1続行条件 | 移動+核保持 |
| 2 | §5.2 L190-228 | 新規 `docs/ai/context/ansible/proxmox-patch.md` | L203-205/L207-213/L228のタグ正本・命名・意味 | 移動+核保持 |
| 3 | §5.2 L246-261 | 新規 `docs/ai/context/ansible/proxmox-patch.md`、roadmap部分は本005 | L246-250のHA/non-HA分類と許可された退避・復帰原則 | 移動+核保持 |
| 4 | §6.2-§6.7 L360-827 | 新規 `docs/ai/context/ansible/proxmox-patch.md` | 4安全度、入口、実行条件、停止条件、禁止範囲 | 移動+核保持 |
| 5 | §6.5 L610-688 | 新規 `docs/ai/context/operations/proxmox-patch.md` | L625-631のreboot後だけretry可、L662-663の最終結果 | 移動+核保持 |
| 6 | §11.2 L1193-1234 | 新規 `docs/ai/context/operations/proxmox-patch.md` | Mode A/Bの許可範囲 | 移動+核保持 |
| 7 | §11.3-§11.4 L1236-1284 | 新規 `docs/ai/context/operations/proxmox-patch.md` | control node条件、health/Status gate、次node禁止 | 移動+核保持 |
| 8 | §14.2-§14.3 L1424-1482 | 新規 `docs/ai/context/ansible/proxmox-patch.md` | changelog優先、単純grep禁止、Ansible最終判定、AI非実行 | 移動+核保持 |
| 9 | §16.1-§16.3 L1619-1669 | 新規 `docs/ai/context/ansible/proxmox-patch.md` | AIは最終適用判断者でなくAnsibleが確定 | 移動+核保持 |
| 10 | §16.5 L1686-1704 | 新規 `docs/ai/context/ansible/proxmox-patch.md` | apply可否をAnsibleの決定論的gateが支配 | 移動+核保持 |
| 11 | §16.6-§16.7 L1706-1732 | 既存 `docs/ai/context/system/proxmox.md` | Proxmox hostで分類CLIを直接動かさず、apply中に導入・更新しない | 移動+核保持 |
| 12 | §16.8.0-§16.8.2 L1744-1783 | 既存 `docs/ai/context/system/proxmox.md`、時点履歴は本005 | L1734-1743/L1785-1789のcontrol node禁止・停止 | 移動+核保持 |
| 13 | §16.9 L1791-1803 | 本005 | なし | 移動 |
| 14 | §17 L1805-1884 | 新規 `docs/ai/context/operations/proxmox-patch.md` | 開始・続行・停止・人間確認条件 | 移動+核保持 |
| 15 | §18 L1886-1930 | 新規 `docs/ai/context/operations/proxmox-patch.md` | §18.1 L1888-1893 | 移動+核保持 |
| 16 | §19 L1933-1947 | 移行計画部分は本005 | Sophos稼働前に安全前提を満たす要求への参照 | 移動+核保持 |
| 17 | §20 L1950-1960 | 手順は新規 `docs/ai/context/operations/proxmox-patch.md`、配置事実は既存 `docs/ai/context/system/proxmox.md` | 直接patch禁止、許容時間帯、慎重判断、urgency判断 | 移動+核保持 |
| 18 | §21 L1964-1986 | 本005 | なし | 移動 |
| 19 | §22 L1989-2007 | Policy出典付録 | 全参照リンク | Policy維持 |

## 4. C: 安全境界ledger

### 4.1 記録規則

- 1行は1つの意味単位とし、別の許可・禁止・停止・必須・例外を同じ行へ混ぜない。
- `旧行`はHEAD snapshotとの突合キー、`新Policy先`はPhase 2での1:1受け皿である。
- Contextへ移す実装説明に規範が混在する場合も、規範は必ず新Policy先を持つ。
- `P1`から`P8`は2.1の新標準節、`PA`は出典付録を表す。

### 4.2 許可・禁止・停止・必須・例外の全量ledger

| ID | 種別 | 旧行 | 原文の安全境界 | 新Policy先 |
|---|---|---:|---|---|
| SB-001 | 必須 | L15-22 | 自動化、重要更新非自動、pve2先行、pve1保護、再インストール前提、guest/replication/backup保護、Sophos移行前のpatch運用確立を目的とする | P1 |
| SB-002 | 必須 | L30-42 | Proxmox patchを通常Linux更新より慎重に扱い、列挙された基盤領域への影響を考慮する | P7 |
| SB-003 | 許可 | L44-48 | 重要コンポーネントでない更新だけならPATCH_READYとして土曜朝に自動適用する | P2/P4 |
| SB-004 | 禁止 | L50-54 | 重要コンポーネント、remove、major疑いを自動適用せず、人間判断または別計画へ移す | P7 |
| SB-005 | 禁止 | L56-65 | MAINTENANCE_REQUIREDで軽微更新を含んでも通常運用では部分適用しない | P7 |
| SB-006 | 例外 | L67 | 部分適用は通常patchでなく明示的な例外maintenanceとしてだけ検討する | P2/P7 |
| SB-007 | 判断 | L82-90 | Statusごとの自動適用可・不可・禁止を維持する | P4 |
| SB-008 | 禁止 | L94-103 | Urgencyは人間対応速度であり、自動適用許可に使わない | P4/P7 |
| SB-009 | 必須 | L105-118 | 列挙された重大脆弱性条件はURGENTとして即対応する | P4 |
| SB-010 | 必須 | L120-131 | HIGH候補は前提条件・利用有無・可用性・露出を確認して判断する | P4 |
| SB-011 | 必須 | L153-158 | pve2先行、pve1正常時のみpve2更新、pve2障害時はpve1を守って再構築、pve2成功後だけpve1へ進む | P5/P7 |
| SB-012 | 必須 | L166-168 | apply前にguest所在を確認し、PATCH_READY自動flowに退避と復帰を含める | P5 |
| SB-013 | 必須 | L203-213/L228 | home nodeは外部YAMLでなくProxmox tagを正本とし、規定命名と一致する対象だけを復帰対象にする | P2/P7 |
| SB-014 | 必須 | L232-250 | HA/non-HA/対象外をtagで分類し、許可された方式で退避・復帰し、残存running guestは最終確認で停止する | P5/P7 |
| SB-015 | 停止 | L265-274 | pve2 apply前に両node health、分類・退避完了、reboot可能状態を満たす | P5/P7 |
| SB-016 | 停止 | L278-283 | pve1 apply前にguest退避とpve2の退避先健全性を満たす | P5/P7 |
| SB-017 | 必須 | L287-295 | patch/reboot/post-check後に復帰し、home配置・running・health OKを確認する | P5 |
| SB-018 | 許可 | L297-300 | guest migrationはPATCH_READY自動適用flow内で許可する | P2/P5 |
| SB-019 | 例外/停止 | L301-320 | local disk migrationは明示変数に従い、無効時は除外せず失敗停止する。HA対象はこのflag外 | P3/P7 |
| SB-020 | 必須 | L324-356 | 入口をsafe/semi-safe/controlled apply/unsafeの4分類に固定し、自動実行範囲を分類どおり制限する | P3 |
| SB-021 | 禁止 | L370/L398 | healthcheckは単一node limit可だが、WARNING/CRITICALならapplyを禁止する | P3/P7 |
| SB-022 | 停止 | L406-414 | quorum、ZFS、apt/dpkg、重要service、systemd、filesystem、report生成の異常をhealthcheck失敗とする | P3/P4 |
| SB-023 | 必須/禁止 | L428-440/L459 | dry-runは固定pair対象で単一node非対応。実行対象の両node healthcheck OKの場合だけ開始し、metadata更新とsimulationだけで実patchしない | P3/P7 |
| SB-024 | 禁止 | L461-470 | AI分類は補助であり最終Statusを直接決めない | P4/P7 |
| SB-025 | 判断 | L480-487 | 更新なし、simulation失敗、major疑い、重要更新、remove、通常更新を所定Statusへ分類する | P4 |
| SB-026 | 停止 | L518-522/L546-551 | evacuateは両node healthと対象妥当性を要求し、migration失敗またはmaintenance有効化timeoutで停止する | P3/P7 |
| SB-027 | 許可 | L566-588 | apply_nodeはPATCH_READY自動またはMAINTENANCE_REQUIRED手動だけを単一nodeへ適用でき、後者は明示確認を要求する | P3/P7 |
| SB-028 | 停止 | L582-600 | 対象/反対node health、Status、control node分離、guest退避を満たさず、またはBLOCKED/MAJORなら停止する | P3/P7 |
| SB-029 | 例外 | L610-631 | post-healthcheck retryはreboot済みかつCRITICAL/UNKNOWNの場合だけ許可し、rebootなしでは許可しない | P5/P7 |
| SB-030 | 判断 | L662-663 | retryでOKならSUCCESS、全試行CRITICALならCRITICALとして扱う | P4/P5 |
| SB-031 | 禁止 | L690-696 | apply_node単体は退避、次node自動続行、最終復帰、BLOCKED解除をせず、MAJORを対象にしない | P3/P7 |
| SB-032 | 必須 | L712-735 | weekly fullは外部control node、両node health、PATCH_READY、退避復帰可能、明示許可controllerを要求しpve2から始める | P2/P3/P5 |
| SB-033 | 停止 | L745-775 | control node、health、Status、evacuate、apply、復帰、post-checkの各gateで失敗時に停止し、pve2 NGでpve1へ進まない | P5/P7 |
| SB-034 | 停止 | L789-825 | restoreはtag対象だけを戻し、migration、maintenance解除、HA復帰、post-restore check失敗で停止する | P3/P5/P7 |
| SB-035 | 禁止 | L829-847 | MAINTENANCE_REQUIREDは人間のmaintenance判断、MAJORは別project、BLOCKEDはcontingencyとし自動化しない | P2/P7 |
| SB-036 | 判断 | L852-887 | 重要コンポーネント更新、remove+置換不明、remove+置換ありを所定Statusへ分類する | P4 |
| SB-037 | 禁止 | L893-903 | NO_UPDATESは通知・reportのみでapplyしない | P4/P6/P7 |
| SB-038 | 許可/停止 | L907-930 | PATCH_READY条件をすべて満たす場合だけ自動適用し、pve2 post-check NGなら停止・通知する | P4/P5/P7 |
| SB-039 | 禁止 | L934-960 | MAINTENANCE_REQUIREDは自動・部分適用せず、固定期限なしで再評価し、人間がpve2からの手動実施を判断する | P4/P5/P7 |
| SB-040 | 禁止 | L964-987 | BLOCKEDは両node適用・部分適用を禁止し、timer停止、復旧route移行、復帰条件までapply禁止とする | P4/P5/P7 |
| SB-041 | 判断/禁止 | L991-1015 | Proxmox major変化疑い、Debian suite変化疑い、repository suite変更直後、base package大量更新、install/remove大量、pve-manager major変化疑いのいずれかをMAJOR_UPGRADE_DETECTEDとし、通常patchから除外、自動適用せず別project化、pve2検証・pve1最後とする | P4/P7 |
| SB-042 | 判断 | L1023-1035 | removeを即BLOCKEDにせず、simulation成功・置換あり・major疑いなし等ならMAINTENANCE_REQUIREDとして手動判断する | P4/P7 |
| SB-043 | 判断/停止 | L1037-1045 | simulation/apt check失敗、置換不明の重要remove、中核消失、依存破綻はBLOCKEDとする | P4/P7 |
| SB-044 | 禁止 | L1049-1061 | UrgencyをStatusと分離し、simulationだけで決めず、複数の公式・機械・分類材料を使う | P4 |
| SB-045 | 判断 | L1063-1118 | LOW/NORMAL/HIGH/URGENTの条件を維持する | P4 |
| SB-046 | 例外/禁止 | L1120-1123 | URGENTは過剰自動昇格せず公式情報・人間判断で昇格し、Urgencyが高くても非許可Statusを自動適用しない | P4/P7 |
| SB-047 | 許可 | L1131-1165 | full flowはreboot影響を受けないクラスタ外control nodeの場合だけ自動実行できる | P2/P5 |
| SB-048 | 禁止 | L1167-1191 | クラスタ内control nodeでは連続自動patchをせず、control nodeのない側だけを単一実行し、同一playbook中の自己migrationをしない | P2/P7 |
| SB-049 | 例外 | L1286-1302 | 事前手動適用後にNO_UPDATESならapplyせず、片nodeだけ済みの場合もModeごとのcontrol node条件を満たす範囲に限る | P5/P7 |
| SB-050 | 停止 | L1306-1308 | apply失敗なら次nodeへ進まない | P7 |
| SB-051 | 停止 | L1309 | reboot後にSSH/API/GUIが戻らなければ次nodeへ進まない | P7 |
| SB-052 | 停止 | L1310 | post-healthcheckがWARNING/CRITICALなら次nodeへ進まない | P7 |
| SB-053 | 停止 | L1311-1313 | apt/dpkg、systemd、cluster/ZFS/replication異常なら次nodeへ進まない | P7 |
| SB-054 | 停止 | L1314-1316 | guest退避・復帰・稼働へ影響があれば次nodeへ進まない | P7 |
| SB-055 | 停止 | L1317 | control nodeがtarget上で継続不能なら次nodeへ進まない | P7 |
| SB-056 | 必須 | L1319 | 停止理由をsummary通知し、週末中に対応する | P6 |
| SB-057 | 許可/停止 | L1323-1336 | PATCH_READY適用後にreboot-requiredなら自動rebootし、復帰・post-check OK後だけ続行する | P5/P7 |
| SB-058 | 禁止 | L1342-1350 | MAINTENANCE_REQUIRED週は自動・部分適用せず、毎週再評価し、高Urgencyでも人間が手動枠を判断する | P5/P7 |
| SB-059 | 必須/停止 | L1352 | MAINTENANCE_REQUIREDのplaybook手動applyは規定形式の明示確認を必須とし、なければ停止する | P7 |
| SB-060 | 禁止 | L1358-1370 | BLOCKEDでは両node・部分適用・apply playbookを禁止しtimerを止め、Sophos状況別の保護とpve1安定を優先する | P5/P7 |
| SB-061 | 停止 | L1374-1381 | simulation失敗は修正後のdry-runで許可Statusへ戻るまでapplyしない | P5/P7 |
| SB-062 | 停止 | L1383-1387 | 置換なし重要removeは更新setを適用せず、remove予定消滅までapplyしない | P5/P7 |
| SB-063 | 停止 | L1389-1393 | apt check失敗は修復して成功するまでapplyしない | P5/P7 |
| SB-064 | 停止 | L1395-1401 | major疑いは通常flowを止め、MAJOR扱い・別計画・pve2検証としpve1を対象外にする | P5/P7 |
| SB-065 | 必須 | L1403-1412 | six return conditionsをすべて満たすまで通常patchへ戻さない | P5/P7 |
| SB-066 | 必須/禁止 | L1418-1443 | 週次はchangelog優先、major/minor疑い等でRoadmap参照、全文保存・要約通知、単純grepを最終判断にせずAnsibleが最終Statusを決める | P4/P6/P7 |
| SB-067 | 禁止 | L1480-1482 | AI分類結果は入力に限り、upgrade実行、BLOCKED解除、apply判断をさせない | P7 |
| SB-068 | 必須 | L1484-1543 | major/minor疑い、中核更新、changelogだけでは変更全体像が見えない場合にRoadmap / Release Notesを参照し、公式更新手順、Security Advisory、Debian Trackerを条件と用途に応じて参照する | P4/PA |
| SB-069 | 必須 | L1547-1556 | 全StatusとPATCH_READY成功/停止を所定強度で通知する | P6 |
| SB-070 | 必須 | L1568-1613 | 成功、pve2停止、MAINTENANCE_REQUIRED、BLOCKEDごとの必須通知項目を含める | P6 |
| SB-071 | 禁止 | L1632-1640 | AIは分類・説明生成であり実行・最終適用判断を担わない | P4/P7 |
| SB-072 | 必須 | L1667-1669 | AIのUrgencyは候補に限り、AnsibleがPolicy表と照合して最終Status/Urgencyを確定する | P4/P7 |
| SB-073 | 禁止 | L1671-1684 | AIにupgrade、reboot、host直接実行、設定変更、Status解除・上書き、apply判断、timer有効化をさせない | P7 |
| SB-074 | 必須 | L1686-1704 | 収集・分類・最終判定・applyの責務を分離し、apply可否をAnsibleが制御する | P4/P7 |
| SB-075 | 必須/禁止 | L1706-1732 | 分類CLIはansy/quory/macOSだけで実行し、pve1/pve2/authy/Sophos Firewall VMでは実行・導入せず、patch apply中に導入・更新しない | P7 |
| SB-076 | 禁止 | L1734-1743 | PATCH_READY自動適用でcontrol nodeをtarget node上に置かない | P2/P7 |
| SB-077 | 禁止 | L1744-1769 | 管理対象host自身からAnsibleを実行せず、クラスタ内control nodeではfull flow・同一playbook自己migrationをしない | P2/P7 |
| SB-078 | 許可 | L1771-1783 | reboot影響を受けないクラスタ外control nodeからだけfull flowを自動実行できる | P2/P5 |
| SB-079 | 停止 | L1785-1789 | control nodeがtarget上ならapply停止、sequence中に停止し得る配置ならfull flowを実行しない | P7 |
| SB-080 | 必須 | L1807-1882 | Mode A/B/手動Modeの開始・health・Status・退避・明示確認・post-check・pve2先行gateを満たす | P5/P7 |
| SB-081 | 禁止/必須 | L1888-1893 | host OS rollbackは原則せず、破損時は再インストールする | P5/P7 |
| SB-082 | 必須 | L1895-1930 | node別復旧・再構築情報を準備し、file rollbackでなく再構築する | P5からOperations Contextを参照 |
| SB-083 | 必須 | L1935-1946 | Sophos移行前にpatch実績、health、再構築、backup/restore、配置・退避、停止時手順の安全前提をすべて満たす | P7から本005の達成記録を参照 |
| SB-084 | 禁止 | L1952-1955 | Sophos Firewall VMがProxmox上で稼働している場合に限り、target node上なら直接patchせず、先に移動可否を確認する | P7 |
| SB-085 | 必須 | L1952/L1956-1958 | Sophos Firewall VMがProxmox上で稼働している場合に限り、network影響を許容できる時間帯だけ実施し、割当確認と移動後通信確認を行う | P5/P7からOperations Contextを参照 |
| SB-086 | 必須 | L1952/L1959-1960 | Sophos Firewall VMがProxmox上で稼働している場合に限り、稼働nodeのMAINTENANCE_REQUIREDをより慎重に扱い、外部露出を踏まえて高Urgencyを早めに判断する | P4/P7 |
| SB-087 | 禁止 | L503/L522 | evacuateの`target_node`はpve1/pve2のいずれかに限定し、`destination_node`は反対側として自動決定して外部指定させない | P3/P7 |
| SB-088 | 必須 | L570/L601 | apply対象はpve1/pve2の指定した1nodeに限定し、対象nodeにrunning guestが残っていないことをapply前に確認する | P3/P7 |
| SB-089 | 必須 | L612-619/L1325-1328 | reboot要否はdry-run時の推定とapply後の事実を区別し、reboot-requiredファイルだけでなく実行中kernelと導入済みkernelの差も使う | P4/P5 |
| SB-090 | 必須/禁止 | L1746-1755 | Ansible実行端末をansyまたはquoryに限定し、管理対象host自身から実行せず、weekly fullはProxmox nodeからの実行をpreflightで拒否する | P2/P3/P7 |

### 4.3 原文行単位での照合規則

SB行の`旧行`が範囲または複数行を示す場合、Reviewerは範囲全体を一つの要約として合否判定してはならない。範囲内の各箇条書き・表行・規範文を旧HEADと新Policyで1行ずつ照合し、同じ新Policy節に複数の旧行を統合した場合も、各旧行について次を個別に記録する。

- 新Policyの到達行
- `保持`、`欠落`、`緩和`、`厳格化`、`条件・例外・順序変更`のいずれか
- 差異がある場合の原文と新文

特に複数の独立条件を含むSB-001、SB-009、SB-010、SB-014-SB-017、SB-020、SB-022、SB-025-SB-028、SB-031-SB-045、SB-047-SB-049、SB-057-SB-065、SB-068-SB-070、SB-073-SB-085、SB-087-SB-090は、`すべて`、`のみ`、`明示`、`次へ進まない`、列挙条件の論理積・論理和を落とさず原文行単位に展開する。ledgerの要約文は移行先索引であり、原文の代替正本ではない。

## 5. D: 移動先の選定理由

| 受け皿 | 選定理由 | 書かないもの |
|---|---|---|
| `docs/ai/context/system/proxmox.md` | node役割、control node配置、CLI実行場所はコードだけでは決まらない実環境の事実。既存文書に同じcluster・可用性・control node説明がある | 時点依存の導入履歴、逐次コマンド、Policyの許可・禁止 |
| `docs/ai/context/ansible/proxmox-patch.md` | 複数playbook/roleを横断するpatch固有の入口、role連携、report、CLI入出力・責務契約を一度に追えるRepository Contextが必要。ホームラボ固有契約なので汎用Skillは作らない | 単一taskの逐語複製、安全可否の最終規範、roadmap |
| `docs/ai/context/operations/proxmox-patch.md` | Mode別の逐次flow、retry、復旧、Sophos退避・通信確認は複数roleを横断するrunbookで、運用時に順序として読む情報 | Statusの定義、禁止・停止条件の正本、実値 |
| 本005 | quory到着前後、初期品質確認、Sophos移行達成確認、実装順序は「その時」の監査・project planであり、生きたContextではない | 現行Policyとして継続する安全境界 |
| Policy出典付録 | §22は判断根拠へ到達する一次情報indexであり、非規範appendixとして同居可能 | 手順本文、時点依存の評価結果 |

## 6. E: Phase 2で想定する編集対象

Phase 1では未編集。Phase 2はTech Leadの明示承認後に限る。

| path | 種別 | 予定操作 |
|---|---|---|
| `docs/ai/policies/proxmox_patch_policy.md` | Policy | 標準8節へ全面再編し§22出典付録を維持 |
| `docs/ai/context/system/proxmox.md` | 既存System Context | node役割、CLI/control node配置の現状事実を重複なく追記・整理 |
| `docs/ai/context/ansible/proxmox-patch.md` | 新規Repository Context | patch入口、role連携、report、CLI契約を収容 |
| `docs/ai/context/operations/proxmox-patch.md` | 新規Operations Context | Mode、retry、復旧、Sophos関連の非Policy手順を収容 |
| `docs/ai/reviews/policy_standardization/2026-07-24_005_investigation_proxmox_patch_policy_rewrite.md` | 調査記録 | Phase 2実績・移行済み追跡を必要最小限追記 |

playbooks、roles、他Policy、既存map、requirement、他者の既存変更は編集対象外である。

## 7. 重複・矛盾リスク

| リスク | 実測 | Phase 2対策 |
|---|---|---|
| `system/proxmox.md`との重複 | 既にpve2先行、pve1続行gate、quory外部control node、healthcheck依存が記載済み | 同義文を追加せず、旧Policyの現状事実で不足するCLI配置だけを補う。Policyは規範へ参照する |
| §5、§6、§11、§17のflow重複 | 退避→apply→post-check→復帰が複数回記載 | Policyは一つの抽象lifecycleとgate、Operations Contextは一つのMode別runbookへ統合する |
| §3と§8-§10の判断重複 | Status/Urgencyの概要と詳細が分散 | P4で定義表を一つに統合し、同じ条件を複製しない |
| §6.5と§11.7のreboot/retry境界 | reboot判定とpost-check retryが別節 | Policyに許可条件・最終停止だけ、Operations Contextに変数・時系列を置く |
| AI判断の表現揺れ | AIが候補を出す記述とAnsibleが最終決定する記述が分散 | P4/P7で「AIは候補、決定論的Ansible gateが最終」を一度だけ規定する |
| §19のlive Policyと移行履歴 | 移行前チェックは時点依存だが安全前提でもある | P7に全条件を満たす義務を残し、個別達成証跡だけ本005へ置く |
| §20のPolicyとrunbook混在 | 直接patch禁止、時間帯、通信確認、Urgencyが同居 | 禁止・判断はP4/P7、操作順はOperations Context、配置事実はSystem Contextへ分ける |
| 旧リンクpath | L1649、L1966に旧 `docs/ops/...` pathがある | 新Policy/Repository Contextで現行pathへ訂正するが、安全条件の意味は変えない |
| 安全境界の強弱変化 | 要約時に「のみ」「すべて」「明示」「次へ進まない」が落ちる危険 | SB-001〜SB-090を4.3に従ってReviewerが旧原文行と1:1照合し、削除・緩和・追加を差異として記録する |

## 8. 未解決点とPhase 2確認事項

Phase 2を止める未解決点はない。次は受け皿を変える論点ではなく、Phase 2でReviewerが確認する表現・重複リスクである。

1. §19 L1935-1946は、全条件をPolicy義務として維持し、時点依存の達成証跡・移行計画だけを本005へ移す。この分割はTech Lead指定の受け皿決定と安全境界不変を同時に満たす確定方針である。
2. §20 L1957の割当確認は実値を転載せず「必要なnetwork interface / segment割当」と一般化する。意味が狭まらないかReviewerの逐語比較対象とする。
3. §6.2-§6.7の単一role実装詳細はコードを正本とすべきだが、Tech Lead指定に従い横断契約だけRepository Contextへ収容する。task列挙の複製は避ける。
4. 新Policyの§22を番号付き9節と誤認させないため「付録A 出典」とする案をPhase 2で採用する。

## 9. 検査計画

### 9.1 Phase 1成果物

- HEAD commit/blob、旧2007行、旧主section 22件を記録したか。
- 旧section配置表が23行（表題・メタデータ1行 + 主section 22行）あり、L1-2007を覆うか。
- migration追跡表が19行あり、18件は移動または移動+核保持、§22はPolicy維持か。
- safety ledger IDが連番で重複せず、全行に旧行・種別・新Policy先があるか。
- 編集対象一覧、選定理由、重複/矛盾、未解決点、Phase 2検査を含むか。
- Markdown表空欄、IPv4 literal、VLAN ID/VM ID/秘密の実値、末尾空白を検査する。
- `git diff --check`と未追跡ファイルへの`git diff --no-index --check`を実施する。

Phase 1実測結果:

| 検査 | 結果 |
|---|---|
| HEAD snapshot | commit `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `61a38e445d6d8af4113b0f33e43213c205d2986d`、2007行で一致 |
| 全量配置 | 表題・メタデータ1行 + 主section 22行 = 23行、§1-§22の欠番なし |
| migration-map追跡 | 19行（移動候補18 + §22維持1） |
| safety ledger | SB-001-SB-090の90件、連番・重複なし |
| Markdown表 | 空セル0 |
| 禁止実値 | IPv4 literal 0。VLAN ID / VM ID / 認証情報 / 秘密の実値0 |
| scope | 本005以外のPhase 1対象ファイルに変更なし。Policyの作業ツリー差分なし |
| whitespace | `git diff --check` PASS、`git diff --no-index --check /dev/null <本005>` PASS |

### 9.1.1 007 reviewによるledger補正（2026-07-24）

上記「Phase 1実測結果」は当時の実績として変更していない。007の旧HEAD逐行レビューでledger要約自体の対象漏れが判明したため、SB番号を増減せず、4.2の該当ledger行だけを次のとおり補正した。

| review | ledger補正 |
|---|---|
| must-fix #1 | SB-023へ旧L440の両node healthcheck開始gateを追加 |
| must-fix #2 | SB-041へ旧L995-1000のmajor upgrade判断6条件を追加 |
| must-fix #3 | SB-068へ旧L1500のRoadmap / Release Notes参照条件を追加 |
| must-fix #4 | SB-075へ旧L1708-1719の分類CLI allowlist / denylistを追加 |
| must-fix #5 | SB-084〜SB-086へ旧L1952の共通条件を追加し、SB-085の無条件化を解消 |

これはPhase 1検査の遡及改竄ではなく、Reviewerが検出した安全境界索引の欠落をPhase 2修正契約へ反映する追記である。

### 9.2 Phase 2実装後

- 新Policyの標準見出しが8件各1回で、§22が出典付録として残るか。
- migration 19行の各行に実移動先またはPolicy核の到達先があるか。
- SB-001〜SB-090を旧HEAD行と新Policy行でReviewerが1:1比較し、範囲指定は4.3に従って原文行単位へ展開したうえで、許可範囲の拡大、禁止・停止の緩和、要件追加がないか。
- `のみ`、`すべて`、`明示的確認`、`進まない`、`自動適用しない`、`禁止`、`停止`の保持を機械検索と目視で確認する。
- 3 Contextの重複見出し・相互矛盾・旧path参照を検索する。
- 対象5ファイル以外、特に`playbooks/`、`roles/`、他Policyにdiffがないか pathspec付きで確認する。
- IPv4 literalと禁止実値、秘密らしい文字列、Markdown表空欄、リンク切れ、`git diff --check`を確認する。
- 実機・Ansible実行は文書再構成の受入に不要であり実施しない。

## 10. Phase 1結論

Phase 2の受け皿はTech Lead指定どおり4分類できる。最大リスクは移動そのものではなく、混合sectionを要約した際の安全境界の脱落または強弱変化である。90件のSB-001〜SB-090と4.3の原文行単位照合規則を移行契約として使用する。§19の分割方針を含む受け皿は確定しており、Phase 2を止める未解決点はない。
