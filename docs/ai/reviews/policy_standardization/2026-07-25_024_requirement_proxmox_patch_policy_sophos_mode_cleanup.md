# 要求仕様: proxmox_patch_policy.md の陳腐化記述・宙ぶらりん参照・冗長規範の整理

作成日: 2026-07-25
起票: claude(要件定義。文言はYoshinobuとの議論で確定済み)
種別: Policy文書の変更(実装コード変更なし)

## 目的

`docs/ai/policies/proxmox_patch_policy.md`(430行、SB-001〜SB-090)に含まれる次の3クラスの不具合を解消する。

1. **陳腐化**: Sophos FirewallのESXi→Proxmox移行はすでに完了し運用も確立しているが、Policyは「移行前」を前提とした条件節・達成条件リストを保持している。
2. **宙ぶらりん参照**: `Mode A` / `Mode B` というラベルを2箇所で参照しているが、定義がリポジトリ上のどこにも存在しない。旧Policy §11.2にあった定義は2026-07-24の再編でOperations Contextへ移動した際、見出しが説明的な名前へ改名されラベルが消えた。
3. **冗長・事実誤り**: SB-049は既存規範の言い換えに加え、実運用と食い違う曜日(dry-runは金曜だが「土曜dry-run」と記載)を含む。

## 背景 / 根拠(調査済みの事実)

### 実装の実挙動(SB-014関連)

`roles/proxmox_evacuate_node/tasks/main.yml`:

- L99-111 分類: `preferpve*`かつ`hacritical`なし → `_vms_to_migrate`(明示migration) / `hacritical`あり → `_vms_ha`(HA maintenance mode退避)。**tagなしguestはどちらのリストにも入らない**(=migrationしない)。
- L218-262 終端処理: nodeを再照会し`status == running`の全guestを`qm stop` / `pct stop`で強制停止する。

この強制停止は**tagなしguest専用の処理ではない**。migration失敗で残ったタグ付きguestやHA退避漏れも同じ網で捕捉する終端不変条件である。現行SB-014は分類規則と終端不変条件を1文に混在させており、「最終確認で停止する」が何を指すか読み取れない。

`qm stop`(電源断相当)であり`qm shutdown`(graceful)ではない点は、node rebootが後続するため現状維持とYoshinobuが判断済み(2026-07-25)。本件では変更しない。

### Statusはcluster集約(SB-049関連)

`roles/proxmox_patch_dryrun/tasks/main.yml` L89-104: `_pre_status`は`unified_dryrun.cluster_summary.total_unique_updates == 0 and total_unique_removes == 0`で`NO_UPDATES`を決める。per-nodeデータ(`node_summaries['pve1']` / `['pve2']`)は保持するが、Status判断はcluster全体。

`playbooks/proxmox_patch_weekly_full.yml`は単一の`_weekly_full_skip` flagで全stepをskipする(L244, L294, L327)。

したがって「pve2だけ手動適用済み」の場合、合算では候補が残るため通常flowが進み、pve2側のapt applyは適用対象ゼロで空振りし、pve1が適用される。両node候補なしなら`NO_UPDATES`で全skip。**SB-049が定める特別ルールは機構上不要**である。

### 実運用のschedule(SB-003 / SB-049関連)

dry-runは金曜、適用は土曜(旧systemd timerの`proxmox-patch-dryrun`は`Fri *-*-* 17:30:00`。現在はSemaphore schedule)。SB-049の「土曜dry-run」は事実誤り。曜日・時刻の実値はPolicyに書かず、scheduler設定とOperations Contextを正本とする方針は`docs/ai/policy-migration-map.md`の分類原則(「仮置き時刻と詳細タイムラインはrunbook/scheduler Contextへ」)と一致する。

### Sophosと自律復旧の関係(新SB-093の根拠)

- HA relocateはstop → migrate → startでVM再起動を伴い、weekly full patchで毎回発生する仕様として2026-07-04に確定済み。
- `docs/ai/policies/autonomous_recovery_policy.md` L76: `sophos-fw`はicmpとdnsの両probeについて5回連続失敗を発火閾値とする。
- 同L119: 自動mute契約として`proxmox_evacuate_node.yml`は`sophos-fw`等3 targetへ120分、`proxmox_patch_apply_node.yml`は60分、`proxmox_restore_vm_placement.yml`は90分、`proxmox_patch_weekly_full.yml`は360分を設定する。
- `playbooks/proxmox_patch_weekly_full.yml` L181-212で実際に360分muteを設定している。

つまりSophos再起動によるinternet断は期待される挙動であり、自律復旧の誤発火を防ぐのはmute契約である。この相互参照がPolicyに書く価値のある実質であり、削除するSB-084/SB-086(退避の一般規則の言い換え/判断境界のない空文)の代わりに置く。

## SBマーカー台帳の扱い(claude決定)

- 現状SB-001〜SB-090が欠番・重複なしで存在する(検査済み: count=90, min=001, max=090)。
- **削除するSB番号(049, 083, 084, 086)は退番とし、再利用しない**。旧レビュー記録(005 investigation、006 implement、007 review)が番号で参照しているため、番号を詰めると過去記録の追跡が壊れる。
- **新規規範はSB-091以降を採番する**。

## 変更内容(逐語指定)

以下の置換をそのまま適用する。文言の言い換え・要約・追加解釈は行わない。

### 変更1: §1 目的 — 達成済みの目的bulletを削除

SB-001のbullet listから次の1行を削除する(他のbulletは変更しない)。

```
- Sophos Firewall VMをProxmoxへ移行する前にpatch運用を確立する。
```

### 変更2: SB-003 — 曜日実値を除去

before:
```
重要コンポーネントでない更新だけから成る場合は`PATCH_READY`とし、土曜朝の自動適用を許可する。
```
after:
```
重要コンポーネントでない更新だけから成る場合は`PATCH_READY`とし、自動適用を許可する。実行scheduleの実値はscheduler設定とOperations Contextを正本とする。
```

### 変更3: SB-014 — 分類規則と終端不変条件を分離

before(SB-014の本文1行):
```
guestはtagにより分類する。`prefer<node名>`があり`hacritical`がないguestはnon-HAとして明示migrationする。`hacritical`があるguestはHA管理としてmaintenance modeで退避し、復帰時は明示relocateする。tagなしguestは明示migration対象外だが、runningのまま残れば最終確認で停止する。
```
after(SB-014を書き換え、直後に新規SB-091を追加):
```
guestはtagにより分類する。`prefer<node名>`があり`hacritical`がないguestはnon-HAとして明示migrationする。`hacritical`があるguestはHA管理としてmaintenance modeで退避し、復帰時は明示relocateする。tagなしguestは明示migration対象にしない。

<!-- SB-091 -->
退避完了後、対象nodeにrunning状態のguestを残さない。tagの有無や分類に関わらず、残存するrunning guestは強制停止する。これはtagなしguest向けの個別処理ではなく、migration失敗やHA退避漏れも捕捉する終端不変条件である。
```

### 変更4: SB-049 — 削除

次のmarkerと本文をまとめて削除する。前後の空行が二重にならないよう整える。

```
<!-- SB-049 -->
事前に手動適用され、土曜dry-runで`NO_UPDATES`ならapplyしない。pve2だけ手動適用済みの場合、Mode Aはpve1へ進む余地があるが、Mode Bはcontrol node所在条件を満たすpve1単一node patchだけを許可する。
```

削除理由: 前半は`NO_UPDATES`の定義の言い換え、後半はSB-047 / SB-048 / SB-078が既に定める条件の再導出であり、加えて曜日が事実誤り。非冗長な規範内容がゼロである。

### 変更5: SB-060 — 死んだ「移行前」分岐を削除

before:
```
`BLOCKED`ではtimerを止め、apply playbookを禁止し、両nodeへ適用しない。Sophos移行前なら移行を延期し、移行後ならSophos稼働nodeを固定して不要な移動をせず、pve1の安定を最優先する。
```
after:
```
`BLOCKED`ではtimerを止め、apply playbookを禁止し、両nodeへ適用しない。Sophos稼働nodeを固定して不要な移動をせず、pve1の安定を最優先する。
```

### 変更6: SB-080 — Mode A / Mode Bラベルを廃止し条件を直接書く

before:
```
Mode A、Mode B、`MAINTENANCE_REQUIRED`手動applyはいずれも、該当するcontrol node条件、healthcheck、Status、guest退避、必要な明示確認、post-healthcheckを満たす。pve1はpve2成功後にだけ別途判断する。
```
after:
```
cluster外control nodeからのfull flow、Proxmox上control nodeからの単一node flow、`MAINTENANCE_REQUIRED`手動applyはいずれも、該当するcontrol node条件(§2.3)、healthcheck、Status、guest退避、必要な明示確認、post-healthcheckを満たす。pve1はpve2成功後にだけ別途判断する。
```

`Mode A` / `Mode B`という語はこの変更後、Policy本文から完全に消える。Operations Context側は既に説明的な見出し(「cluster外control nodeのfull flow」「Proxmox上のcontrol nodeによる単一node flow」)を使っており、用語が揃う。

### 変更7: SB-085 — 常に真の条件節を除去

before:
```
Sophos Firewall VMがProxmox上で稼働している場合は、Sophos停止によるnetwork影響を許容できる時間帯だけpatchし、必要なnetwork interface / segment割当を確認し、Sophos VM移動後に通信を確認する。手順は[Operations Context](../context/operations/proxmox-patch.md)を参照する。
```
after:
```
Sophos停止によるnetwork影響を許容できる時間帯だけpatchし、必要なnetwork interface / segment割当を確認し、Sophos VM移動後に通信を確認する。手順は[Operations Context](../context/operations/proxmox-patch.md)を参照する。
```

### 変更8: §7.3 Sophos安全前提 — 全面書き換え

SB-083(見出し行+10 bullet全て)、SB-084、SB-086を削除し、§7.3の中身を次で置き換える。見出し`### 7.3 Sophos安全前提`は維持する。

after(§7.3全体):
```
### 7.3 Sophos安全前提

<!-- SB-092 -->
Sophos Firewall VMも他のguestと同じ退避規則(SB-012、SB-018)に従う。稼働中であれば反対nodeへ退避してからpatchし、Sophos専用の退避除外や個別の移動可否判断を設けない。

<!-- SB-093 -->
Sophos Firewall VMのHA relocateはstop → migrate → startであり、VM再起動を伴う。この間はinternet接続が切断される。これは退避・復帰の仕様であり障害ではない。切断中はicmp / dns probeが連続失敗し得るため、自律復旧の誤発火防止は[autonomous_recovery_policy.md](autonomous_recovery_policy.md)が定めるmute契約に依拠する。patch系playbookの自動muteが設定されていることを確認し、muteなしでSophos稼働nodeのpatchを進めない。
```

### 変更9: §8 変更履歴 — 行を追加

既存行は変更せず、表の先頭(2026-07-24行の上)へ次を追加する。

```
| 2026-07-25 | 移行完了済みのSophos前提(SB-083、SB-001の1 bullet、SB-060 / SB-085の条件節)を削除し、退避の一般規則で足りるSB-084とUrgency判断境界のないSB-086を廃止。代わりにHA relocateによるVM再起動・internet断とautonomous_recovery_policyのmute契約への依拠をSB-092 / SB-093として明記。定義が存在しない`Mode A` / `Mode B`参照を条件記述へ置換。冗長かつ曜日が事実誤りのSB-049を削除。SB-014を分類規則と終端不変条件(SB-091)へ分離。退番: SB-049 / SB-083 / SB-084 / SB-086(再利用しない) |
```

### 変更10: Operations Context — Sophos節をPolicyと整合させる

`docs/ai/context/operations/proxmox-patch.md`の`## Sophos VM稼働時`節。

before:
```
Policyの全安全前提を満たした後も、patch対象node上のSophos VMを先に別nodeへ移動できるか確認する。移動する場合は必要なinterface / segment割当を確認し、移動後に家庭内networkの通信を確認する。停止影響を許容できるmaintenance枠でだけ行う。
```
after:
```
Sophos VMは他のguestと同じく退避対象である。退避時は必要なinterface / segment割当を確認し、移動後に家庭内networkの通信を確認する。HA relocateはVM再起動を伴いinternet接続が切断されるため、停止影響を許容できるmaintenance枠でだけ行い、自律復旧のmuteが設定されていることを確認する。
```

「移動できるか確認する」という任意性を含む表現は、削除するSB-084の枠組みを引き継いでいるため、退避が既定であるPolicyの規範に合わせる。

## 制約

- **実装コードを変更しない**。`playbooks/`と`roles/`の差分はゼロであること。
- **他Policyを変更しない**。`autonomous_recovery_policy.md`へは参照リンクを張るだけで、同文書自体は編集しない。
- 上記変更9箇所+Operations Context1箇所以外のPolicy本文を編集しない。SB-002〜SB-090のうち本要件で触れないものは1文字も変えない。
- IPアドレス、VLAN ID、VM ID、認証情報、秘密情報の実値を書かない。
- 曜日・時刻の実値をPolicyへ書かない(変更2の趣旨)。
- 時刻表記はJST。

## レビュー観点(reviewer必須)

1. **逐語一致**: 変更1〜10がbefore/after指定どおりに適用され、指定外の文言変更・要約・追加解釈がないこと。`git diff`で全hunkを確認する。
2. **SB台帳**: 変更後のSBマーカーを全件抽出し、(a)重複なし、(b)退番したSB-049 / SB-083 / SB-084 / SB-086が本文から消えている、(c)新規SB-091 / SB-092 / SB-093が各1回だけ存在する、(d)それ以外の番号がSB-001〜SB-090から欠落していないこと。
3. **宙ぶらりん参照の消滅**: `Mode A` / `Mode B`がPolicy本文から完全に消えたことを`grep`で確認する。`docs/ai/reviews/`配下の過去記録に残る参照は履歴なので変更しない。
4. **陳腐化の掃引**: Policy本文に「移行前」「移行する前」等、Sophos移行完了前を前提とした表現が残っていないことを確認する。
5. **安全境界の非緩和**: 削除・書き換えによって、patch適用の許可範囲が広がっていないこと。特にSB-014の分割で「退避後にrunning guestを残さない」保証が弱まっていないこと、SB-049削除で`NO_UPDATES`時にapplyされる経路が生まれていないこと(SB-058、`_weekly_full_skip`の機構で担保されることを確認)。
6. **相互参照の妥当性**: SB-093が参照する`autonomous_recovery_policy.md`のmute契約(L119)とprobe閾値(L76)が実在し、記述内容と一致すること。
7. **scope**: `playbooks/` / `roles/`の差分がゼロ、他Policyの差分がゼロであること。

## テスト観点(tester)

本件はドキュメント変更のみで実行系に影響しないため、実機実行・playbook実行は不要。次の静的確認で足りる。

- `git diff --check`(whitespace異常なし)
- Policy本文のmarkdown link切れがないこと(特に新規の`autonomous_recovery_policy.md`相対リンク)
- `scripts/git-pre-commit-check.sh`のIPv4リテラル検査を通過すること
- `bash scripts/check-tester-gate.sh`がPASSすること(playbook無変更の確認として)
