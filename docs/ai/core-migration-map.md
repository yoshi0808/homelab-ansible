# `core.md` 移行追跡表

対象: 旧 `docs/ai/prompts/core.md`（1,253行、18セクション）

> **⚠️ 2026-07-26: 旧coreファイルは削除済み。** 稼働コードから参照されていた§18(tester-gate、49箇所)を `docs/ai/policies/ansible_test_safety_policy.md` と `skills/ansible-implementation-style/SKILL.md` へ、§7・§17のshell責務詳細を `docs/ai/context/operations/healthcheck.md` へ移設し、全live参照を張り替えたうえで削除した。
>
> **本表の各行の「旧core参照」(L番号・§番号)は、git履歴に対する参照として読む。** 原文が必要な場合は `git log --all -- docs/ai/prompts/core.md` から該当commitを辿る。削除直前の内容は2026-07-26のcommitの親に存在する。
>
> したがって本表は「移行中のfallback index」ではなく、**未移行項目の棚卸しリスト**として機能する。`[予定 Phase N]` / `[分類のみ Phase N]` の行は、その情報が現時点でどの正本にも無いことを意味する。必要になった時点で、この表の「内容」列の要約とgit履歴の原文から、指定先へ移す。

このファイルは、旧coreの情報を移行後に一項目ずつ消失確認するためのindexである。Role/routingは `docs/ai/role-routing-index.md` から解決する。

## 判断基準と移動先マーカー

新 `docs/ai/core.md` に残すのは、全Roleが毎回必要とし、homelab固有で短期間には変わらず、Role / Context / Policy / Skill / Knowledge / Issue / PR・diffだけで読む方が適切ではない原則または安全境界に限る。

移動先の状態は次のマーカーで機械的に区別する。

- **[既存]**: 現在存在し、移行中も正本として読めるパス。
- **[予定 Phase N]**: 具体パスまで決めたが、Phase Nで作成・移行する。
- **[分類のみ Phase N]**: 分類だけを決め、ファイル名・パスはPhase Nで確定する。

「一部残す」は共通原則だけを新coreへ残し、独立した手順・例外を別行で追跡する判断である。「統合」は重複を指定先の一項目へ吸収する判断である。予定先が作成されるまで、各行の「旧core参照」をfallbackとする。

## セクション移行サマリ

| 旧core項目 | 判断 | 分類 | 移動先状態と具体先 | 理由 |
|---|---|---|---|---|
| 冒頭の巨大正本宣言 | 置換 | core / index | **[既存]** `docs/ai/core.md`, 本表, `docs/ai/role-routing-index.md` | 共通原則・routing・詳細追跡を分離する |
| §1 リポジトリの目的 | 一部残す | core / System Context | **[既存]** `docs/ai/core.md`; **[予定 Phase 2]** `docs/ai/context/system/overview.md` | 目的は共通、対象機能一覧は変化する |
| §2 主要ノードと役割 | 移す | System Context | **[予定 Phase 2]** `docs/ai/context/system/overview.md` | 環境事実である |
| §2 ansy / Git / quory境界 | 残す | core | **[既存]** `docs/ai/core.md` | 全Roleの開発・本番境界である |
| §3 名前解決、DNS、inventory例 | 一部残す | core / Context / Policy | **[既存]** coreのIP禁止; **[予定 Phase 2]** System / Repository ContextとNetwork Policy | 禁止は共通、値と手順は変化する |
| §4 inventory groupとplaybook対応 | 移す | Repository Context | **[予定 Phase 2]** `docs/ai/context/ansible/inventory-map.md`, `playbook-map.md` | リポジトリ地図である |
| §5 管理user、SSH鍵、例外host | 一部残す | core / Context / Policy | **[既存]** coreの秘密保護; **[予定 Phase 2]** System ContextとSSH / Secrets Policy | 秘密境界以外は環境・認証詳細である |
| §6 playbook / role / files / vars責務 | 移す | Repository Context | **[予定 Phase 2]** `docs/ai/context/ansible/repository-overview.md` | 構造説明である |
| §7 check shellとAnsibleの責務 | 移す | Operations Context | **[既存]** `docs/ai/context/operations/healthcheck.md` §1(2026-07-26移設) | 主に実装・レビュー時に必要 |
| §8 files / templates / script | 移す | Policy / Skill | **[分類のみ Phase 2]** Ansible Design Policy; **[既存]** `skills/ansible-implementation-style/SKILL.md` | 実装手順と例外である |
| §9 read-onlyと変更系の分離 | 一部残す | core / Policy | **[既存]** coreの共通境界; **[分類のみ Phase 2]** Change Safety Policy | 詳細条件は個別判断である |
| §10 命名、playbook一覧、Policy一覧 | 移す | Repository Context / Policy index | **[既存]** `playbook-map.md`; Policyは **[既存]** `docs/ai/policies/*_policy.md`(2026-07-23移行完了) | 一覧は変化する |
| §11 Git / quory反映 | 一部残す | core / Deployment Policy | **[既存]** coreの正本・自己更新禁止; **[分類のみ Phase 2]** Deployment Policy | 操作詳細だけを分離する |
| §12 自動実行 | 移す | Operations Context / Policy | **[分類のみ Phase 2]** Scheduling Policy | 実行基盤依存の判断である |
| §13 `.gitignore` | 一部残す | core / Repository Context / Skill | **[既存]** coreの秘密・生成物境界; **[分類のみ Phase 2/5]** Repository Context / Contribution Skill | pattern詳細はコードから確認可能 |
| §14 AI運用、Role、2セッション | 一部残す | core / Role / Operations Context | **[既存]** coreとRole/routing index; **[予定 Phase 3]** `docs/ai/roles/`; **[分類のみ Phase 2]** Operations Context | 権限境界だけが全員共通 |
| §15 要求・文書・agmsg・review | 一部残す | core / Role / Workflow / Skill | **[既存]** coreとRole/routing index; **[予定 Phase 3]** Role / Workflow; **[分類のみ Phase 4–5]** Requirements / Review / Documentation Skill | 工程・担当別手順である |
| §16 review・test・final | 移す | Role / Workflow / Policy / Skill | **[予定 Phase 3]** Role / Workflow; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md`; **[分類のみ Phase 4–5]** Test / Documentation Skill | Role固有の成果物と判断である |
| §17 禁止事項 | 一部残す | core / Policy / product差分 / Knowledge | **[既存]** coreと`CLAUDE.md`; **[分類のみ Phase 2]** Policy; **[予定 Phase 6]** Knowledge | 共通境界、製品差、教訓を分ける |
| §18 tester-gate | 一部残す | core / Policy / Skill / Knowledge | **[既存]** coreの分類確認; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md`; **[分類のみ Phase 4–5]** Skills; **[予定 Phase 6]** Lessons | 詳細は実装・テスト時だけ必要 |

## 独立した許可・禁止・例外・停止条件

以下は、他の項目とまとめず個別に移行完了を確認する。旧core参照は2026-07-21版の行番号と節名である。

| ID | 旧core参照・独立ルール | 種別 | 判断 | 分類 | 移動先状態と具体先 | 理由 |
|---|---|---|---|---|---|---|
| C03-01 | §3: IP literalをrepo全体へ書かない | 禁止 | 残す | core | **[既存]** `docs/ai/core.md` | 全Role共通の公開安全境界 |
| C03-02 | §3: IPが必要なら実行時に名前解決する | 代替条件 | 移す | Network Policy | **[分類のみ Phase 2]** Network / Naming Policy | 実装方法はPolicy向き |
| C05-01 | L201-202: 秘密鍵を生成・表示しない | 禁止 | 残す | core | **[既存]** `docs/ai/core.md` | 全Role共通。2026-07-29に判断基準形式へ書換(種別は移行時点の記録) |
| C05-02 | L203: `~/.ssh/id_ann` をrepoへコピーしない | 禁止 | 統合 | core | **[既存]** coreの秘密情報を複製しない規則 | C05-01の具体例として消失確認する |
| C05-03 | L204: `authorized_keys` を勝手に上書きしない | 禁止 | 移す | SSH Policy | **[分類のみ Phase 2]** SSH / Access Policy | 認証資産固有の変更禁止 |
| C05-04 | L205: SSH port/userを推測して固定しない | 禁止 | 残す | core | **[既存]** `docs/ai/core.md` | 全Roleの推測禁止。2026-07-29に判断基準形式へ書換(種別は移行時点の記録) |
| C05-05 | L206: vault/secret/local平文を作らない | 禁止 | 統合 | core / Secrets Policy | **[既存]** core; **[分類のみ Phase 2]** Secrets Policy | 共通境界と形式詳細を分離 |
| C07-01 | L261: boolean等の観測値をshellが返すことは許容 | 許可 | 移す | Operations Context | **[既存]** `docs/ai/context/operations/healthcheck.md` §1 | sensor出力境界の明示的許可 |
| C07-02 | L262-263: `status: critical` / warnings生成は禁止 | 禁止 | 移す | Operations Context | **[既存]** `docs/ai/context/operations/healthcheck.md` §1 | 観測と判定の境界 |
| C08-01 | L269-273 + L278-279: 静的shellはfiles、一時実行なら`script`を許容 | 原則・例外 | 移す | Policy / Skill | **[分類のみ Phase 2]** Ansible Design Policy; **[既存]** `skills/ansible-implementation-style/SKILL.md` | 一時実行だけの例外を保持する |
| C08-02 | L281-285: templateは変数埋込が必要な場合だけ | 許可条件 | 移す | Policy / Skill | **[分類のみ Phase 2]** Ansible Design Policy; **[既存]** `skills/ansible-implementation-style/SKILL.md` | template採用の停止条件 |
| C09-01 | §9: checkへ変更操作を混ぜず変更系入口を分離 | 禁止 | 一部残す | core / Change Policy | **[既存]** core; **[分類のみ Phase 2]** Change Safety Policy | 共通境界と実装詳細を分ける |
| C11-01 | §11: quoryのpullはclean確認後`--ff-only` | 前提条件 | 移す | Deployment Policy | **[分類のみ Phase 2]** Deployment Policy | 本番取得手順である |
| C11-02 | §11: playbook内でgit pullしない | 禁止 | 残す | core | **[既存]** `docs/ai/core.md` | 自己更新問題は全Role共通 |
| C12-01 | L393-399: 自己停止/再起動・job中断はsystemd timer | 選択条件 | 移す | Scheduling Policy | **[分類のみ Phase 2]** Scheduling Policy | 実行基盤の停止条件 |
| C12-02 | L401-404: module/package更新だけなら一律timerにせずSemaphore可 | 例外・訂正 | 移す | Scheduling Policy / Knowledge | **[分類のみ Phase 2]** Scheduling Policy; 経緯は **[予定 Phase 6]** Lesson | 過剰なtimer適用を防ぐ例外 |
| C13-01 | L455: 実運用がない `all.yml.example` を無条件に作らない | 作成条件 | 移す | Repository Policy / Skill | **[分類のみ Phase 2/5]** Repository Policy / Contribution Skill | 不要なplaceholder作成を防ぐ |
| C14-01 | §14: YoshinobuのGOなしに危険操作・commitしない | 停止条件 | 残す | core | **[既存]** `docs/ai/core.md` | 人間ゲートの根幹 |
| C14-02 | L503-506: ASK代行はtask ownerのみ、未GO破壊操作は不可、移管後旧ownerは停止 | 許可・停止・移管条件 | 移す | Role / Workflow | **[予定 Phase 3]** Coordinator Roleとrouting移管規則(2026-07-29、Tech Lead廃止によりTech Lead側の宛先は消滅) | owner競合を防ぐ |
| C14-03 | L507-508: Yoshinobuは`claude` / `techlead`へ同一案件を同時依頼せず、逐次引継ぎは許容する | 禁止・引継ぎ許可条件 | 移す | Role / Workflow / Operations Context | **[予定 Phase 3]** owner / routing規則(`techlead`は2026-07-26の常駐trio廃止、2026-07-29のTech Lead役廃止のいずれでも現存しないidentityである。Phase 3実施時はCoordinator/subagent体制向けに書き直すこと) | 二重ownerを防ぎつつ、明示的な逐次引継ぎを可能にする |
| C15-01 | L587-588: 空の工程ファイルを事前作成しない | 禁止 | 移す | Documentation Skill | **[分類のみ Phase 4–5]** Documentation Skill | 不要成果物を防ぐ |
| C15-02 | §15 agmsg: 本文はrepo、messageはpath中心 | 正本条件 | 一部残す | core / Workflow | **[既存]** core; **[予定 Phase 3]** Workflow | 監査証跡と配送を分ける |
| C15-03 | §15 watcher: 通知を承認と扱わず秘密を転載しない | 禁止・停止条件 | 移す | Operations Context / agmsg Skill | **[分類のみ Phase 2/5]** Agent Operations Context / agmsg Skill | ASK検知は実行許可ではない |
| C16-01 | L910-911: SSH自体でなく接続先コマンドの性質で安全分類 | 判断条件 | 移す | Test Safety Policy | **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | 実行方法でなく副作用を評価する |
| C16-02 | L914: pve2先行、pve1/本番はdry-run後に人間判断 | 順序・停止条件 | 移す | System Context / Test Policy | **[予定 Phase 2]** Proxmox ContextとTest Safety Policy | 環境固有の先行検証境界 |
| C16-03 | L917: quory SSHは指定鍵を先に試し、鍵なし失敗で不可と断定しない | 例外 | 移す | System Context / Test Skill | **[分類のみ Phase 2/5]** quory Context / Tester Skill | 誤った到達不能判定を防ぐ |
| C17-01 | §17: Claude Codeはssh、commit/push、無確認playbook、実host ad-hocを行わない | 製品固有禁止 | 移す | product差分 / Policy | **[既存]** commit/push禁止は`docs/ai/core.md`、実host ad-hoc禁止は`docs/ai/roles/coordinator.md`と`skills/delegation-tier/SKILL.md`、無確認playbook禁止は`docs/ai/policies/ansible_test_safety_policy.md` TS-021。**ssh直接実行禁止は2026-07-26に廃止**(承認境界をCoordinatorへ移管、`~/.claude/settings.json`のssh askも削除) | Codex共通原則へ混ぜない |
| C17-02 | L1016-1021: localhost + connection local + 無副作用ロジック検証は事前確認なし可、後で削除・記録 | 例外・記録義務 | 移す | Claude Execution Policy / Skill | **[既存]** `docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」の提示不要リスト(2026-07-26移設) | 製品固有禁止の限定例外 |
| C17-03 | §17: 技術的hookを過信せず、人間確認を最後の安全網とする | Lesson / 原則 | 移す | Knowledge / Policy | **[予定 Phase 6]** Lesson; **[分類のみ Phase 2]** Execution Policy | 過去経緯と現在の停止条件を分離 |
| C18-01 | §18.1: 全playbookに5分類のmarker必須 | 必須条件 | 一部残す | core / Test Policy | **[既存]** core; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | 全員は存在を知り、詳細は必要時に読む |
| C18-02 | L1074-1082: risk-acceptedは実害なし/復旧容易かつ本体省略無意味の2条件、costを理由にしない | 許可条件 | 移す | Test Safety Policy | **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | 本実行許可を過度に広げない |
| C18-03 | L1099-1110: dynamic includeへ`check_mode`直付け不可、static化かblock | 実装例外 | 移す | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson | include種別固有の落とし穴 |
| C18-04 | L1112-1115: loop付きincludeはblock化不可、include先へ個別指定 | 実装例外 | 移す | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson | C18-03とは別の停止条件 |
| C18-05 | L1161-1166: orchestratorはimport先のcheck-modeを上位whenで潰さない | 実装禁止 | 移す | Ansible Skill / Test Policy | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | read-only検証消失を防ぐ |
| C18-06 | L1173-1183: moduleごとのcheck_mode差と`check_mode:false`条件 | 実装条件 | 移す | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson | module挙動の差を保持する |
| C18-07 | L1184-1185: handlerは通知元の`check_mode:false`を継承しない | 実装例外 | 移す | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson | handler固有の例外 |
| C18-08 | L1186-1189: `end_play` / `end_host` はalwaysもskipする | 実装例外 | 移す | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson | 無音停止を防ぐ |
| C18-09 | L1190-1192: check-mode結果を通知/報告分岐へ含める | 実装義務 | 移す | Ansible Skill / Test Policy | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | dry-run誤通知を防ぐ |
| C18-10 | L1193-1195: blockへloop不可 | 実装例外 | 統合 | Ansible Skill / Lesson | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[予定 Phase 6]** Lesson（C18-04と相互参照） | 同じ制約の重複説明を統合する |
| C18-11 | §18.4: marker欠落はlintでcommitを止める | 機械的停止条件 | 移す | Repository Context / Test Policy | **[既存]** `docs/ai/policies/ansible_test_safety_policy.md`(TS-019/020) | 規約でなく実装済みgateである |
| C18-12 | §18.5: testerはmarker確認、check-mode系を`--check`なしで実行しない | Role義務・禁止 | 移す | Tester Role / Test Skill | **[既存]** `docs/ai/policies/ansible_test_safety_policy.md`(TS-021/022/023) + `docs/ai/roles/tester.md` | tester固有の実行境界 |
| C18-13 | §18.6: Codexはsafe wrapperを使い、risk-acceptedは対象外 | 製品固有手順・例外 | 移す | Codex Test Skill | **廃止(2026-07-26)** Codexが開発工程から外れたためprefix依存の手順は不要。`--check`付け忘れ防止という効能のみ`docs/ai/policies/ansible_test_safety_policy.md` TS-024/025へ保持 | Codex承認prefix依存の手順 |
| C18-14 | L1157-1159: dry-run-awareで安全な引数を選んでも、`command` / `expect` 等のcheck_mode非対応moduleへ`check_mode:false`がなければtask自体がauto-skipされる | 実装条件・検証停止条件 | 移す | Implementer / Reviewer Skill + Test Safety Policy | **[既存]** `skills/ansible-implementation-style/SKILL.md`; **[既存]** `docs/ai/policies/ansible_test_safety_policy.md` | dry-run引数の選択だけでは実行保証にならず、auto-skipならdry-run検証が成立しないことを保持する |

## 移行完了の確認方法

各IDは、予定先が作成された時点で次を確認してから旧coreから削除する。

1. 意味、許可範囲、禁止範囲、例外、停止条件が予定先に存在する。
2. Role/routing indexまたは正式Role indexから、必要なRoleだけが到達できる。
3. 新旧で競合せず、PolicyとSkillへ同じ判断を二重記載していない。
4. 機械gateがある項目は、文書だけでなくlint/scriptの現状も確認した。

旧coreを一括削除しない。すべてのサマリ行と独立IDが移行済みになった後に、Phase 5の読込経路とPhase 8のboot経路を検証して廃止する。
