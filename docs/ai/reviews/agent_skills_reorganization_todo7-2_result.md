# TODO 7-2: Phase 7 pilotから見えたRole別の不足分析

- 分析日: 2026-07-22
- 対象pilot: `radius_healthcheck` disk使用率チェック追加
- 対象成果物: `docs/ai/reviews/radius_healthcheck/2026-07-21_016_implement.md`〜`020_final.md`
- owner: `techlead2`
- 状態: Coordinator確認待ち

## 結論

限定Context、2付きtrio routing、Role別手動読込順序は機能した。Role責務の不適切な重複や、不要Contextの大量読込はなかった。

一方、初回要件のdisk `used_percent`の意味論、markerと実コードの副作用・guard整合、Coordinator原依頼のtraceabilityに改善余地が見つかった。これらは全Role共通の不変原則ではないため、`docs/ai/core.md`へ追加しない。Role / Workflow Context / Policy / Skill / Issueへ分け、Knowledge候補は昇格を保留する。

## Tech LeadのContext選択漏れ

### 実例と評価

Context量と参照範囲は概ね適切だった。`radius_servers`、対象role、旧coreのshell責務とtester-gateだけで実装・レビュー・テストを完結でき、他healthcheck roleや過去review全文は不要だった。

不足はContextそのものより、要件の意味論と現行構造の確認にあった。

1. 「既存memoryと対称」という指定だけでは、disk `used_percent`を`used / total`で算出するのか、予約領域と切り上げを含む`df` Use%を使うのか一意でなかった。
2. Coordinator原依頼はreport/debugの追加先を`tasks/main.yml`としていたが、現行コードでは2026-07-11以降`tasks/check.yml`へ分離済みだった。Tech Leadが着手前調査で補正し、Coordinator確認を得た。
3. trio memberはCoordinator原agmsg本文を直接参照できない場合があり、ownerが正規化したsetupと依頼文だけでは元要求とのtraceabilityが弱かった。

### 反映先

| 改善 | 反映先 | 理由 |
|---|---|---|
| 数値指標は名称だけでなく意味論、入力source、丸め、境界を受入条件へ書く | Tech Lead Role / Requirements Skill | 要件分解時の手順であり全Role共通原則ではない |
| ファイル指定は現行コードで責務分割を確認してから確定する | Tech Lead Role / Repository Context選択手順 | 構造変化へ追従する案件開始手順である |
| 原依頼の送信元・時刻またはmessage IDをsetup/requirementへ残す | Workflow Context / agmsg Skill | 工程間traceabilityの規則である |

## Implementerの実装Skill不足

### 実例と評価

Implementerは限定Contextを守り、shellを収集・JSON整形、Ansibleを判定・reportへ分離し、変更を2ファイルに限定した。修正対応、fixture、lint分離も適切で、基本Skillは十分だった。

初回実装では「memory対称」を式まで対称と解釈し、`round(used / total * 100)`を採用した。`df`が既に返すUse%との比較や、filesystem予約領域・切り上げ境界を自己検証しなかったため、80/90%を過小判定する可能性を残した。これは一般的な実装力不足ではなく、ドメイン指標の意味論をsourceと照合するチェックの不足である。

### 反映先

| 改善 | 反映先 | 理由 |
|---|---|---|
| OS commandが同じ指標を返す場合、自前計算前に意味論と境界を比較する | Ansible Implementer Skill / Validation Skill | 再利用可能な実装・自己検証手順である |
| percent閾値は境界直下・境界値に加え、予約領域や丸め差のfixtureを置く | Validation Skill | 特定案件だけでなく数値監視へ再利用できる |
| 新規lint違反0と既存lint負債を分離する | Implementer Skill / Reviewer Skill | 既存負債をscopeへ混ぜず退行を防ぐ手順である |

## Reviewerの見落とし

### 実例と評価

Reviewerは初回差分で最重要の意味論バグを発見した。ローカル`df`の46%に対し初回JSONが45%になる実例、予約領域で76%が80%相当になる例を示し、修正後のfixtureとlintまで再確認した。主要責務は十分に果たした。

一方、初回レビューはplaybookが無変更であることと`safe-readonly`維持を確認したが、marker理由の`tester_mode`が廃止済みで、実guardが`skip_notifications`であるdrift、およびcopy/reportという副作用までは検出しなかった。今回のdiffレビューscope外という面はあるが、tester-gateを安全根拠として評価する場合は理由文と実行経路の照合が必要である。

### 反映先

| 改善 | 反映先 | 理由 |
|---|---|---|
| markerを安全根拠に使うレビューでは、分類名だけでなく理由文・guard名・実行経路を照合する | Reviewer Skill / Test Safety Policy | 安全分類のレビュー手順と判断基準である |
| diff外の既存不整合は機能判定と分離し、follow-up Issueへ送る | Reviewer Skill / Workflow Context | scope拡張を防ぎつつ安全課題を失わない手順である |

## Testerの検証不足

### 実例と評価

Testerは不足より強みが確認された。静的確認、実`df`比較、失敗・不正値、79/80/89/90、予約領域fixture、source `tasks/check.yml`のlocalhost harnessを独立実行し、実装・Reviewerの証拠を再利用するだけで終わらなかった。

また、markerを盲信せずremote copy、local report、条件付き通知を再評価し、local証拠で受入条件を満たせるため実hostを実行しない判断をした。これにより既存marker理由のdriftを発見した。

改善余地は、Coordinator原依頼へ直接到達できず、setupで正規化された要件を使った点である。機能検証には不足しなかったが、要求の改変有無を独立確認するtraceabilityは弱い。加えてlocalhost harnessは有効だったが一時作成であり、同型テストへ再利用する標準手順はまだない。

### 反映先

| 改善 | 反映先 | 理由 |
|---|---|---|
| Tester入力に原要求の監査参照を含める | Workflow Context / agmsg Skill | Role間の証拠連鎖である |
| source taskを副作用なしでfixture評価するlocalhost harness手順を一般化する | Tester Skill | 再利用可能な検証能力である |
| markerと実コードの副作用が違う場合は、実hostよりlocal証拠を優先し差異を報告する | Tester Skill / Test Safety Policy | 安全な検証選択の判断基準である |

## Knowledge候補の扱い

### 1. disk `used_percent`は`df` Use%を正本にする

- 状態: pilot finding / Lesson候補。
- 根拠: Reviewerの実値差、予約領域fixture、80/90境界で再現済み。
- 現時点の置き場: 今回のrequirement/setup、実装、review、test、final。
- 判断: 共通Knowledgeへはまだ昇格しない。別のfilesystem監視でも再発する、または共通Validation Skillへ一般化するときにLessonとして評価する。

### 2. `safe-readonly`でも副作用とguard名を実コードで再評価する

- 状態: 既存marker driftの発見 / Policy・保守Issue候補。
- 根拠: `radius_healthcheck.yml`の理由は廃止済み`tester_mode`を指すが、実guardは`skip_notifications`。通常実行にはcopy/reportもある。
- 現時点の置き場: `2026-07-21_019_test_result.md`と`020_final.md`のfollow-up。
- 判断: coreへ追加せず、7 playbookの実態棚卸し結果に基づいてコメント修正または別Issueへ送る。分類自体の変更はYoshinobu / Coordinator判断まで行わない。

## TODO 7-2判定

- Tech Lead: Context量は適切。指標意味論・現行構造確認・原要求traceabilityをRole/Skill/Workflowへ改善候補として送る。
- Implementer: 責務分離とscope管理は良好。指標sourceとの照合と境界fixtureをSkill候補とする。
- Reviewer: 主要バグ検出は良好。marker理由と実guardの照合をReviewer Skill / Policy候補とする。
- Tester: 独立検証と副作用判断は良好。監査参照とlocalhost harness一般化をWorkflow / Tester Skill候補とする。
- core: 変更しない。
- Knowledge: 2件とも昇格保留。

Coordinator確認後に計画書TODO 7-2を完了へ更新する。次PhaseやRole / Skillファイルの本実装はYoshinobuの指示を待つ。
