# 規範文書横断監査 findings — Policy群担当(2026-08-25)

- 対象: CLAUDE.md / AGENTS.md / `docs/ai/core.md` / `docs/ai/context-classification.md` / `docs/ai/role-context-matrix.md` / `docs/ai/memory-classification.md` / `docs/ai/roles/*.md`(6本) / `docs/ai/policies/*.md`(12本)
- 検査軸: ①矛盾 ②宙ぶらりん参照 ③正本の二重化 ④読み取れない箇所 ⑤原則の言い直し(群固有)
- 参照先の実在確認はリポジトリ全体に対して行った(`docs/ai/memory/`・`docs/ai/reviews/`・`docs/ai/status.md`は監査入力にしていない。参照先実在の確認にのみ開いた)
- 技術的な正否・実装の良し悪しは判定していない

---

## 1. 矛盾

### 1-1. cert_renew: 運用頻度の新旧規定が同一文書内で両立しない

- `docs/ai/policies/cert_renew_policy.md:274`(CERT-013内):
  > 運用は両経路とも force_renew=true の月次強制再発行とする。閾値条件(残15日以下)は、月次実行間隔に対して安全マージンが不足するため運用上は使用しない(forceなし手動実行時のフォールバックとして残置)。
- `docs/ai/policies/cert_renew_policy.md:183`(CERT-024の表):
  > | `cert_renew.yml` | 週次。**週末に実行する** | しない（残り15日を切ったときだけ更新する） | 翌週の実行が拾う |

CERT-024(v2.5、2026-08-06新設)は `cert_renew.yml` を「週次・期限駆動・強制しない」と定めるが、CERT-013の旧文「両経路とも月次強制」が残っており、同じ入口の頻度と強制の要否について正反対の規定が併存する。v2.5の変更履歴(同ファイル:270)は移行を明記しており、274行が改訂漏れである。

### 1-2. time_sync: `time_sync_ntp_reference.yml` の分類がマーカー正本と食い違う

- `docs/ai/policies/time_sync_check_policy.md:90`(TIME-017):
  > time_sync_check.ymlのtester gateはsafe-readonly、time_sync_ntp_reference.ymlはrisk-acceptedであり、列挙は実行許可を追加しない。
- `playbooks/time_sync_ntp_reference.yml:51`:
  > # tester-gate: check-mode-native — TS-009 条件1(再起動してもchronyデーモンが

分類の正本はplaybookヘッダである(`docs/ai/policies/ansible_test_safety_policy.md:35` TS-007「個別playbookの分類実値は各ファイル先頭のマーカーが正本であり、本Policyへ一覧を複製しない(複製すると必ずドリフトする)」)。TIME-017が複製した分類値は現物と食い違っており、TS-007が予言したドリフトそのものになっている。

### 1-3. unifi_backup_fetch: UNIFI-019の`--check`意味論がTS-030/TS-022と両立しない

- `docs/ai/policies/unifi_backup_fetch_policy.md:81`(UNIFI-019):
  > tester gateはrisk-acceptedであり、check有無にかかわらず変更を生じ得る。本表は実行許可を追加しない。
- `docs/ai/policies/ansible_test_safety_policy.md:133`(TS-022):
  > **`risk-accepted`に`--check`を付けてはならない** — dry-runにはならず、playbook自身が停止する(TS-030)。
- 現物(`playbooks/unifi_backup_fetch.yml:19-21`)もTS-030どおり:
  > # tester-gate: risk-accepted — この playbook に dry-run 区分はない。--check
  > # を渡すと pre_tasks の停止 assert(TS-030)により変更を一切行わずに停止する。

TS-030(2026-07-31)以降、`risk-accepted`は`--check`で停止するため「check有無にかかわらず変更を生じ得る」は成立しない。UNIFI-019はTS-030導入前の意味論のまま残っている。

### 1-4. execution_boundary「全Roleが起動時に読む」がAuditor/Operatorの読み物規定と両立しない

- `docs/ai/policies/execution_boundary_policy.md:3`:
  > 対象業務ではなく実行主体の側で引く境界を扱うため、**全Roleが起動時に読む**(`docs/ai/role-context-matrix.md`)。
- `docs/ai/core.md:82` も同旨: 「実行境界のPolicyは、対象業務に関わらず全Roleが起動時に読む」
- 一方、`docs/ai/role-context-matrix.md:38`:
  > Auditorは**案件クローズ時に1回だけ**起動し、読むのは次の4つに限る。
  (続く表(同:40-44)に本Policyは含まれない)
- `docs/ai/roles/auditor.md:62-63`(必須Context):
  > **起動時に `docs/ai/core.md` を読む**(全Role共通の安全境界)。次に `docs/ai/roles/auditor.md`(本ファイル)で自分の責務を確認する。
  > 本Role固有: `docs/ai/status.md`(状態の正本とその規律)、対象の案件フォルダ。
- `docs/ai/roles/operator.md:21` も読むものを列挙するが、本Policyを常時読み込みに含めない:
  > 読むのは `docs/ai/core.md`(全Role共通の安全境界)、本ファイル、`docs/ai/context/operations/operator-request-channel.md`、`docs/ai/context/operations/agent-messaging.md`、および調査対象に該当するContext / Policyである。

「全Role」と言いながら、AuditorとOperatorの読み物規定は本Policyを起動時読み込みに含めない。しかも本Policy側が根拠として指すmatrix自体が、開発工程4Role分の行(matrix:25)しか持たず(matrix:34「この表はansy側の開発工程のRoleだけを扱う」)、Auditor節では限定列挙から外している。

### 1-5. EXEC-010: `monnie` が2つの区分に同時に載っており、承認要否の帰結が割れる

- `docs/ai/policies/execution_boundary_policy.md:52`:
  > | 到達手段が無い | `pve1` / `pve2` / `authy` / `quory` / `sophos-fw` / **`monnie`** | ansyが書込のできる接続手段を持たない(内訳と壊れ方は EXEC-003)。**`monnie` は2026-08-19に加わった** |
- `docs/ai/policies/execution_boundary_policy.md:53`:
  > | それ以外 | `monnie` / `ansy` / `sandbox` | 家庭向けサービスを提供せず、内容はGitから再現可能か、失っても停止を招かない観測データである |

4.1の承認区分は「到達手段が無いホスト」を「承認の対象ではない。届かない」(同:77)、「上記以外のホストへの非冪等操作」を「確認不要。Coordinatorが判断し実施、事後報告」(同:78)と別々に扱うため、`monnie`がどちらの行に従うのかを表から一意に決められない。v1.1(同:151)で「到達手段が無い」へ`monnie`を加えた際、「それ以外」行から除かれていない。

### 1-6. proxmox_operations: pve2先行の無条件規定が単一node適用の規定と両立しない

- `docs/ai/policies/proxmox_operations_policy.md:43`(SB-011):
  > pve1へ進めるのは、pve2更新後のhealthcheckがOKの場合だけである。
- `docs/ai/policies/proxmox_operations_policy.md:203`(SB-038):
  > pve2へ先行適用し、post-healthcheck OKの場合だけpve1へ進む。NGならpve1へ進まず停止・通知する。
- 一方 `docs/ai/policies/proxmox_operations_policy.md:16`(§1):
  > 「pve2を先行検証nodeとし、pve1を保護する」は、両nodeが利用可能なときの順序制約とする。pve2が到達不能または不健全でpve1だけが利用可能な場合は、pve2の先行検証・適用実績がないままpve1へ適用する(SB-028、SB-032、§2.2)。
- 同:141(SB-032)も「pve2の先行実績なしに…pve1へ直接適用する」と定める。

SB-011とSB-038は条件句を持たない無条件規定のままで、pve2利用不能時の単一node適用(§1、SB-028、SB-032、SB-094)と正面から衝突する。2026-08-01の変更履歴(同:411)は追随改訂した条項としてSB-007・SB-035・SB-046・SB-058・§5.1を挙げるが、SB-011・SB-038は挙がっておらず、改訂漏れと読める。

### 1-7. cert_renew_cloudkey: ansyを開発実行元とする規定がid_ann削除後のexecution_boundaryと両立しない

- `docs/ai/policies/cert_renew_cloudkey_policy.md:45`(CCK-003の表):
  > | 実行元（開発） | ansy（CLI 実行を許可） |
- `docs/ai/policies/cert_renew_cloudkey_policy.md:51-52`:
  > 実行ホストを特定名へ限定する規範は本Policyに置かない。実行権限の実体はSSH鍵`ann`の保有者であり、実行元の列挙は上表のとおり現状の運用形態を示すに留める。
- `docs/ai/policies/execution_boundary_policy.md:36`(EXEC-005):
  > **鍵を用途で分け、`id_ann` は ansy から削除した**(Yoshinobu決定、2026-08-19)。…**いま ansy が持つのは `id_sandbox` だけで、これは `sandbox` しか開けない。**

「実行権限の実体はSSH鍵`ann`の保有者」という規定を前提にすると、`id_ann`を持たなくなったansyは実行元(開発)たり得ず、CCK側の2つの記述(表と本文)が現行のexecution_boundaryと両立しない。CCK側は2026-07-26(v1.2)以降改訂されていない。

### 1-8. CloudKey API認証: 「共有」と明言された同一対象に、CSRF取得の異なる規定が2本ある

- `docs/ai/policies/cert_renew_cloudkey_policy.md:217`(CCK-008):
  > - CSRFトークンは JWTペイロードの `csrfToken` クレームから抽出する
- `docs/ai/policies/unifi_backup_fetch_policy.md:173-175`(UNIFI-007。§7見出しは「認証方式（cloudkey_cert_deploy と共有）」):
  > - CSRF（優先順位）: レスポンスヘッダー **`X-CSRF-Token` を最優先**、無ければ
  >   `X-Updated-CSRF-Token`。**両ヘッダーとも空のときに限り**、JWT ペイロードの
  >   `csrfToken` をデコードして fallback とする（ヘッダーが有効なら JWT は一切触らない）。

UNIFI側は認証方式を「cloudkey_cert_deploy と共有」と述べたうえで(unifi_backup_fetch_policy.md:12)、CSRFの導出を「ヘッダー最優先・JWTはfallback」と規定する。CCK側は無条件に「JWTクレームから抽出」と規定しており、共有と言われた同一の認証契約に対する規定が食い違う。

### 1-9. schedule・時刻の実値がPolicy本文に書かれ、context-classificationの規定に反する

- `docs/ai/context-classification.md:60`:
  > 秘密情報でなくても、次の値の**実値**をContext・Policy・Skillへ書かない。値そのものではなく正本へのポインタを書く。
- 同:64(表):
  > | 実行schedule、時刻、曜日、cadence | scheduler設定(systemd timer定義またはSemaphore UI)。… |
- これに対し:
  - `docs/ai/policies/unifi_backup_fetch_policy.md:60`: 「systemd timer で**週次**実行する（Semaphore UI 導入後は Schedule へ移行）。」
  - `docs/ai/policies/unifi_backup_fetch_policy.md:65-66`: 「参考: 深夜帯は 01:00 UniFi Console / 02:00 UniFi Device / 03:00 quory / 03:30 authy・monnie が稼働するため、本取得はそれらと重ならない週次枠に置く。」
  - `docs/ai/policies/cert_renew_policy.md:184`: 「| `cert_renew_quory.yml` | 月次（毎月1日 00:35） | する（`force_renew: true`） | …」

時刻・曜日・cadenceの実値がPolicy本文に直接書かれており、context-classification §3.2の「実値を書かない・ポインタを書く」と両立しない(cert_renew_policy.md:191は同じ節で「頻度・曜日…は `roles/semaphore_templates/defaults/main.yml` の `semaphore_schedules_catalog` が正本」と自らポインタも定めており、実値の併記はその宣言とも整合しない)。

---

## 2. 宙ぶらりん参照

### 2-1. coordinator.md → `docs/ai/status.md`「載せていないもの」節が存在しない

- `docs/ai/roles/coordinator.md:80`:
  > やらないと決めたことは `docs/ai/status.md`「載せていないもの」が持つ。
- 現在の `docs/ai/status.md` の見出しは「このファイルの規律」「Now(進行中)」「Next(着手候補) — 工程・体制」「Next(着手候補) — システム・運用」のみで、「載せていないもの」という節・文言は存在しない(`grep -n "載せていない" docs/ai/status.md` で0件)。

### 2-2. incident_capture_policy → coordinator.mdに「Policy改訂はYoshinobuの領域」の規定が無い

- `docs/ai/policies/incident_capture_policy.md:3`:
  > 状態: **正本**(**Yoshinobu承認済み**。以後の改訂もYoshinobuの領域である — `docs/ai/roles/coordinator.md`)
- `docs/ai/roles/coordinator.md` にPolicy本文の改訂権限に関する規定は無い(grepで「改訂」「領域」該当なし)。該当する規定が実在するのは `docs/ai/policies/execution_boundary_policy.md:75`(EXEC-030「Policy本文の改訂…常にYoshinobuへ上げる」)と `docs/ai/memory-classification.md`(「`docs/ai/policies/`本文の改訂はYoshinobuの領域」)であり、ポインタの指す先が誤っている。

### 2-3. core.md → coordinator.mdは「ホストで引く」境界を持たない

- `docs/ai/core.md:49`:
  > (到達できるホストどうしの承認の要否は別の軸で、`docs/ai/roles/coordinator.md` がホストで引く。)
- `docs/ai/roles/coordinator.md:76`:
  > **正本は [`docs/ai/policies/execution_boundary_policy.md`](../policies/execution_boundary_policy.md) である。** 承認区分、ホストの区分、状態を変えない確認の扱い、Roleごとの実行可否は、すべてそちらが定める。**値も表も、ここへ写さない。**

ホストで引く区分は現在 `execution_boundary_policy.md`(EXEC-010「境界はホストで引く」)にあり、coordinator.mdは委譲だけを持つ。core.mdの括弧書きは移設前の所在を指したまま残っている。

### 2-4. autonomous_recovery: 「P4」が文書中で未定義

- `docs/ai/policies/autonomous_recovery_policy.md:152`:
  > pullはlock、flapping、`pvesh`の4分岐を順に評価し、P4の条件を満たす段だけを実行する。
- 「P4」の出現はこの1箇所だけで(`grep -n "P4"` で唯一)、本文書のどこにもP4(およびP1〜P3)の定義・対応表が無い。何の条件を指すのか参照先が存在しない。

### 2-5. unifi_backup_fetch → ubuntu_vm_patch_policyは「深夜リブートスケジュール」の実値を持たない

- `docs/ai/policies/unifi_backup_fetch_policy.md:59-60`(UNIFI-014):
  > `ubuntu_vm_patch_policy.md` の深夜リブートスケジュールと衝突しない時間帯に、quory の
  > systemd timer で**週次**実行する（Semaphore UI 導入後は Schedule へ移行）。
- `docs/ai/policies/ubuntu_vm_patch_policy.md:256`(UV-079):
  > 定常job(nightly reboot判定、healthcheck等)の実行基盤(systemd timerまたはSemaphore Schedule)と正確な時刻はOperations Contextを正本とし、…

参照先のubuntu_vm_patch_policyは2026-07-25の改訂(変更履歴:375)で時刻実値をOperations Contextへ委譲済みであり、「深夜リブートスケジュール」という参照対象が参照先に存在しない。

### 2-6. time_sync: 「§3参照」が現在の節構成で解決しない

- `docs/ai/policies/time_sync_check_policy.md:76`:
  > - cloudkeyへのquory参照追加（GUI管理のため対象外。§3参照）。
- `docs/ai/policies/time_sync_check_policy.md:87`:
  > | `time_sync_ntp_reference.yml` | …cloudkey・sophos-fwは対象外（§3参照）。 |
- 現在の「## 3.」は「対応するPlaybook」(同:78)で、cloudkey対象外の理由(GUI管理)は「## 2.」配下のTIME-007(同:41-48)にある。文書内には旧番号の見出し(「### 8. スコープ」が## 2配下:63、「### 3. 対象と取得方式」が## 4配下:99)も残っており、「§3」がどちらの体系の3を指しても該当内容に到達しない。

---

## 3. 正本の二重化

### 3-1. `git commit` / `git push` の規則がcore.mdとexecution_boundaryの両方に本文で存在する

- `docs/ai/core.md:65`:
  > `git commit` / `git push` は、Yoshinobuの都度承認を得た対話セッションだけが行う。**subagentは承認の有無にかかわらず行わない。**
- `docs/ai/policies/execution_boundary_policy.md:74`(EXEC-030の表1行目):
  > | `git commit` / `git push` | **Yoshinobuの都度承認を得てCoordinatorが実行する。** 承認プロンプトを出す前に、stageした内容の分類とcommitメッセージ案を提示する — … |

core.md:25は承認区分の正本をexecution_boundary_policyと定めているが、core.md「Gitの扱い」節が同じ規則を自前の本文として持つ。既に片側にしか無い要素(stage内容の事前提示義務はEXEC側のみ、subagent禁止の明示はcore側のみ)が生じており、片方だけが直る経路ができている。

### 3-2. 閾値・世代数の実値がrole defaultsとPolicyの両方に存在する

context-classification.md:66 は「件数、閾値、世代数、保持期間」の正本を「role defaults / vars」と定める。これに対し:

- `docs/ai/policies/time_sync_check_policy.md:118-119`(TIME-005):
  > 他ホストより大きい専用閾値（`time_sync_check_sophos_threshold_ms`、既定5000ms）を用いる。`time_sync_check_threshold_ms`（既定500ms）はchrony/cloudkey共通。
  - 同値は `roles/time_sync_check/defaults/main.yml:32`(`time_sync_check_threshold_ms: 500`)・同:40(`time_sync_check_sophos_threshold_ms: 5000`)にある。
- `docs/ai/policies/unifi_backup_fetch_policy.md:107`(「世代数: 既定 **8 世代**」)、同:118(「**既定 60 秒**」)、および同:208-219の「既定パラメータ（defaults/main.yml）」表全体:
  - 同値は `roles/unifi_backup_fetch/defaults/main.yml:21`(`unifi_backup_keep_generations: 8`)・同:24(`unifi_backup_freshness_max_seconds: 60`)にある。
- さらに `docs/ai/policies/unifi_backup_fetch_policy.md:121`(UNIFI-012)は他Policy領域の閾値まで複製している:
  > pve2側の同期状態は`playbooks/time_sync_check.yml`が500msの厳しい閾値で独立監視している。

いずれもdefaults側だけが変更されたときにPolicy側が旧値のまま残る経路を作る(UNIFI-012は3箇所目の複製で、time_sync側の変更がここへ届く経路が無い)。

---

## 4. 読み取れない箇所

### 4-1. role-context-matrix: 「読むのは次の4つに限る」の直後の表が3行しかない

- `docs/ai/role-context-matrix.md:38`:
  > Auditorは**案件クローズ時に1回だけ**起動し、読むのは次の4つに限る。
- 続く表(同:40-44)の行は「案件フォルダの全成果物」「`docs/ai/status.md`」「成果物から参照されている先」の3つだけである。4つ目が何を指すのか(数え違いか、行の脱落か、`docs/ai/roles/auditor.md`が挙げるcore.md等を含めた数か)がこの文書から判別できない。

### 4-2. memory-classification: 「4層モデル」の表が5行ある

- `docs/ai/memory-classification.md:5`:
  > ## 1. 4層モデル
- 続く表(同:9-13)の行はCore / **状態** / Knowledge / Skill / Claude Memoryの5つである。「状態」行は「知識ではなく**現在地**」と自称しており層に数えない読み方も可能だが、その場合も表題と表の対応(どの4つが層なのか)を本文から確定できない。

---

## 5. 群固有: 原則の言い直し

### 5-1. execution_boundary §7がcore.md「安全機構がブロックしたとき」をほぼ逐語で再掲している

- `docs/ai/core.md:33`:
  > - **別の形で同じ結果へ到達しない。** 止めて、ブロックされた事実をCoordinatorへ報告する。
- `docs/ai/policies/execution_boundary_policy.md:136`(EXEC-080):
  > **安全機構(permission classifier、`permissions.deny`、`autoMode`)がブロックしたら、別の形で同じ結果へ到達しない。** 止めて、ブロックされた事実をCoordinatorへ報告する。…
- `docs/ai/core.md:35`(「ただし、その操作が目的に本当に必要かは問い直してよい。…この場合は必ず報告する」)と `docs/ai/policies/execution_boundary_policy.md:138-139`(EXEC-081)、`docs/ai/core.md:37`(「この機構…を変更したときは、症状ではなく設定そのものを確認する」)と同:145(EXEC-083)も同一内容の並立である。

EXEC-080/081/083は実行境界という領域への適用を加えておらず、core.mdの規則の言い直しになっている。どちらの側も他方を正本と指していないため、改訂時に片側だけが直る(実際、EXEC-081はcore.md:35の末尾の担保の一文を落としており、既に文言が分岐している)。

### 5-2. AR-102後段がcore.mdの「能力の不在で境界を作る」をそのまま言い直している

- `docs/ai/core.md:39`:
  > 実効的な境界は文章ではなく、能力の不在(鍵・到達先・wrapperが存在しないこと)で作る。
- `docs/ai/policies/autonomous_recovery_policy.md:373`(AR-102):
  > Codexの設定ファイルに書くコマンド制限(execpolicy等)を安全境界として設計してはならない。境界は能力の不在 — 鍵・wrapper・到達先が存在しないこと — で作る。

前段(execpolicy禁止)は領域適用だが、後段はcore.mdの原則文の言い直しであり、適用を加えていない。

### 5-3. 複数のPolicyが同じ対象(CloudKey非公開APIの認証契約)に別々の規定を置いている

- `docs/ai/policies/cert_renew_cloudkey_policy.md:205-227`(CCK-008「API contract」: ログインパス、TOKEN cookie、CSRF、Origin、ホスト名接続、`validate_certs: false`)
- `docs/ai/policies/unifi_backup_fetch_policy.md:165-181`(UNIFI-007/021「認証方式（cloudkey_cert_deploy と共有）」: 同じログインパス、TOKEN、CSRF、Origin、`validate_certs: false`)

UNIFI側は「共有」と述べる(同:12「認証方式…は cloudkey_cert_deploy と共有する」)のみで正本をCCK側へ委譲せず、契約全体を自前の規定として再定義している。同じ対象への二重規定であり、既にCSRF導出で内容が分岐している(→ 1-8)。

---

## 未確認(実在・解釈を確定しきれなかったもの)

1. **AGENTS.md:7の「`recovery_exec_setup`が配布する専用のAGENTS.md(`AGENTS.md.j2`)」** — `recovery_exec_setup`という名のroleは存在せず(実在するのは`roles/recovery_exec/`、テンプレは`roles/recovery_exec/templates/AGENTS.md.j2`)、`playbooks/recovery_exec_setup.yml`は存在する。playbook名を指す読みなら成立するため、宙ぶらりんとは断定しない。AR-104(`docs/ai/policies/autonomous_recovery_policy.md:245`)は同じものを「`recovery_exec`が配るもの」と呼び、呼称が揃っていない。
2. **UNIFI-014「（Semaphore UI 導入後は Schedule へ移行）」(unifi_backup_fetch_policy.md:60)** — Semaphoreは他文書で稼働中として扱われる(EXEC-052、BRV-042等)が、`roles/semaphore_templates/defaults/main.yml`の`semaphore_schedules_catalog`に`unifi_backup_fetch.yml`のschedule項は見当たらず(template定義のみ存在)、現行の起動主体がtimerのままなのか移行済みなのかを文書からもrepoからも確定できなかった。矛盾とは断定しない。
3. **`docs/ai/role-context-matrix.md:29`「Knowledge(`docs/ai/memory/`、Claude Memoryを含む)」** — `docs/ai/memory-classification.md:9-13`の4層モデルはKnowledgeとClaude Memoryを別の層として分ける。matrix側の行ラベルはこれをKnowledgeに包含しており分類語が食い違うが、行の実質(Coordinatorだけが読む)は両文書で一致するため、矛盾とは断定しない。
4. **Decision参照範囲の言い方の差** — `docs/ai/role-context-matrix.md:29`は「着手時(重要Decisionは常に前提とする)」、`docs/ai/memory-classification.md:134`は「全`decisions/`(重要度問わず)…を、着手時にCoordinator自身が確認する」。前者を「着手時は全部+重要は常時」と読めば両立するため、矛盾とは断定しない。
5. **core.md:3の読者列挙にOperator・Codexが無い** — `docs/ai/roles/operator.md:21`とAGENTS.md:3はいずれもcore.mdを読むと定める。core.md:3は「が読む」であって「だけが読む」ではないため、矛盾とは断定しない。
