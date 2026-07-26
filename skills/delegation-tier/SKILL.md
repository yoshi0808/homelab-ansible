---
name: delegation-tier
description: homelab-ansibleのCoordinatorが案件をどこまで分解するかを決めるときに使う。「Tierを判定する」「誰に振るか決める」「分解方針を決める」場面で使う。Tech Leadへ渡した時点で分解は既に選択されているため、判定を下流へ委ねない。
---

# 委任Tier判定

案件を受けたCoordinatorが、Roleへ渡す前にTierを確定する。Tech Leadへ渡すこと自体が分解の選択であるため、判定を下流へ委ねない。

## 判定手順

まず**引き上げ条件**を確認し、該当しなければ上から順に問う。最初にYesになったTierを採用する。迷ったら1つ軽い側へ倒す。

**引き上げ条件(runtime影響の有無に関わらずTier 4)**: 多ファイル横断、安全境界の再定義、Policy本文の再編、Role間の責任分界の変更。これらはruntimeに影響しなくても意味判断の量が多く、逐行照合が必要である。

**Role固有Skillの適合**: 役割を分ける目的は、各機能が専門Skillを使えるようにすることである。したがって**分解する価値は、そのRole固有のSkillが実際に適用される場合に生じる**。Implementerは`skills/ansible-implementation-style`、Reviewerは`skills/code-review`・`skills/duplication-reuse-check`・`skills/ansible-security-review`、Testerは`skills/test-strategy`を持つ。これらがどれも適用対象外の案件(Policy / Context / docのみの変更など)は、Tier 3以上へ上げても実装寄りの専門性が働かず、必要なのはCoordinator側の`skills/requirements-analysis`だけである。この場合は工程を上げずCoordinatorが担う。

1. **runtimeに影響せず、変更が局所的か**(単一または少数ファイルの機械的編集、コメント、docの部分修正) → **Tier 1**
2. **変更ロジック自体は自明で、実ホストでの確認だけが必要か** → **Tier 2**
3. **本番影響のある実ロジック変更、複数ホストのorchestration、破壊的操作、セキュリティか** → **Tier 3**
4. **上記に加えて引き上げ条件のいずれかを含むか** → **Tier 4**

Tier 4であっても、意味判断(何をどう変えるか)はCoordinatorが確定してから渡す。下流に発明させない。

**例外: 破壊的操作でもTier 2に留まる場合(2026-07-26)**: 3.の「破壊的操作」は本来、trio側に「何をどう壊すか」の設計判断が残っている場合にTech Leadの査読を要求する趣旨である。Yoshinobuが実行内容(具体的な操作・コマンド)そのものを直接指定・承認済みで、Coordinator/trioに設計判断の余地が残っていない場合は、その指定範囲内での実行はTier 2のまま扱ってよい。ただし破壊的操作である以上、「Tier 2でTech Leadへ一報を入れる理由」節の運用(着手前共有)は必須とする。trioや実行者側が手順・方式を選ぶ余地がある破壊的操作は、この例外の対象外でありTier 3とする。

## Tier 2でTech Leadへ一報を入れる理由(2026-07-26の実例)

Tier 2はTech Leadを飛ばしてCoordinatorが直接Testerへ依頼する経路である。しかし**Testerは想定外の事態に遭遇したとき、自分の担当Tech Leadへエスカレーションする**(`docs/ai/roles/tester.md`の経路)。このときTech Leadに案件の文脈が無いと、誰が何を承認したか分からないまま判断を迫られる。

2026-07-26、CoordinatorがLoki全データ削除をTesterへ直接依頼した際、削除後にLokiが起動せず、Testerが指示範囲を超える復旧手順の可否をTech Leadへ確認した。Tech Leadは案件自体を知らず、Yoshinobuが直接依頼した可能性を疑ってCoordinatorへ照会することになった。Tech Leadの判断(サービス停止中のため復旧を優先して許可)自体は適切だったが、文脈の欠落は避けられた。

したがってTier 2では、**指示は出さなくてよいが、着手前に「誰が何をTesterへ依頼したか」をTech Leadへ共有する**。あわせて承認所有権がCoordinatorにあることを明示し、Tech Leadが同じTesterへ二重に指示しない状態をつくる。二重承認は誤操作の原因になる(`feedback_confirm_prompt_proxy_scope`の所有権ルール)。

## Tierごとの工程

| Tier | 工程 | 成果物 |
|---|---|---|
| 1 | Coordinatorが実装し静的検査まで自分で完了する。Roleへ渡さない | 変更本体。記録は必要な場合だけ |
| 2 | Coordinatorが実装し、Testerにだけ実機検証を依頼する。**着手前にTech Leadへ一報を入れる**(下記) | 変更本体 + test_result |
| 3 | Tech Lead → Implementer → Reviewer → Tester。着手前に分解方針をCoordinatorへ報告する(`docs/ai/context/operations/agmsg-message-format.md`) | requirement / implement / review / test_result |
| 4 | Tier 3に加えて調査→Coordinator受入→実装の2段階とし、Reviewerは逐行照合する | Tier 3の成果物 + investigation |

## 判断の根拠(2026-07-25実測)

- Tier 1相当をTier 3工程で流すと純粋なoverheadになる。Policy整理案件では上流で逐語仕様を作った結果、Implementer差し戻し0・Reviewer blocking 0・suggestion 0で、工程が付加したのは検証のみだった。
- Tier 2相当をTier 3工程で流すと40分かかる(`unifi_backup_fetch`のpve1→pve2フェイルオーバー追加)。リソース逼迫はなく、工程設計そのもののコストである。
- **重すぎた場合の損失は実測済みだが、軽すぎた場合の損失は未観測である**。したがって迷ったら軽い側へ倒す。
- Reviewerを通してもCoordinatorの仕様漏れは検出されないことがある(同日、Policy本文の「Mode別」表記残存を工程通過後にCoordinatorが発見)。**独立レビューの有無より仕様の質が支配的**であり、レビュー工程を不安の保険として使わない。
- 上流で before / after を逐語指定するとき、下流へ「再判断が必要と思ったら勝手に変えず差し戻せ」を明示する。これで「上流の仕様ミスを下流が気づく」という難しい要求を「疑ったらエスカレーション」という易しい要求へ変換できる。

## 禁止

- Tier判定をTech Leadへ委ねない。Tech Leadが受領した案件はTier 3以上として扱われる。
- Tier 1 / 2でCoordinatorが実装する場合も、実ホストへのad-hocコマンド実行は行わない。実機操作が必要なら必ずTier 2としてTesterへ渡す。
- 所要時間やコンテキスト消費を理由にTierを下げない。判定軸はruntime影響と本番影響だけである。
