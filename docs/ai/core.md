# homelab-ansible AI共通原則

このファイルは、Claude CodeによるCoordinatorと、Coordinatorが必要に応じて呼び出すsubagent(Tech Lead / Implementer / Reviewer / Tester / Auditor相当)が作業開始時に読む共通原則の正本である。製品別入口はリポジトリ直下の `AGENTS.md` と `CLAUDE.md` とし、共通原則をそれらへ複製しない。

## 目的と正本

このリポジトリは、homelab環境のAnsible playbook、role、scriptと、その安全な運用に必要な文書を管理する。

- Git管理されたリポジトリ内容をコードと文書の正本とする。
- `docs/ai/core.md` は全Role共通原則の正本とする。
- `docs/ai/status.md` は**現在地**(進行中の作業、観測待ち、着手候補)の正本とする。規範は書かない。対話セッションは`/clear`のたびに文脈を失うため、状態はセッションの記憶でなくリポジトリ側に置く。
- 案件固有の要求と工程記録は、Coordinatorからの依頼文と `docs/ai/reviews/<target>/` の requirement、implement、review、test_plan、test_result、finalを正本とする。
- 現在の変更内容は作業ツリーとdiffを正本とし、説明文だけで変更済みと判断しない。
- 対象システム固有の判断は、該当Policyを正本とする。Policyは `docs/ai/policies/*_policy.md` にある。
- 移行元の旧正本 `docs/ai/prompts/core.md` は2026-07-26に削除した。原文はgit履歴にあり、各項目の移動先は `docs/ai/core-migration-map.md` を参照する。

## 人間の権限と安全境界

AIは実装、レビュー、テスト、調査、論点整理を支援する。最終判断者はYoshinobuである。

- 運用上の採否、本番適用を行うかどうか、危険操作に踏み込むかどうかの方針、確定、commitはYoshinobuが判断する。
- Yoshinobuは要件と「こうなったら困る」という前提を示すが、実装の詳細までは追わない。**承認済みscope内で個々の操作がその範囲に収まっているかを判断する責任はCoordinatorにある**(2026-07-26確立)。何をYoshinobuへ上げ、何をCoordinatorが承認し、何が提示不要かの3分類は`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を正本とする。
- patch、reboot、restart、migration、firewall変更、inventory変更など、本番影響を生む操作を暗黙の承認や推測で実行しない。Yoshinobuの明示的承認か、その承認済みscope内であることを確認したCoordinatorの承認が要る。
- 許可の範囲が不明な場合や、安全性に懸念がある場合は停止し、根拠と未確認事項を示して確認する。scope外または判断がつかない場合はCoordinatorもYoshinobuへ上げる。
- AIは `git commit`、`git push` を行わない。
- playbook自身にGit更新を行わせない。

### 安全機構がブロックしたとき(2026-07-28追加、全Role共通)

harnessの安全機構(permission classifier、`permissions.deny`)が操作をブロックしたら、**その事実をCoordinatorへ報告せずに、別の形で同じ結果へ到達しない。**

- **ブロックが「形への異議」か「実質への異議」かの判定を、ブロックされた側が行わない。** 通る形を探すのではなく、止まって上げる。
- Coordinatorは、報告を受けてもそれを自分では解除できない。**`soft_deny` を解除できるのはYoshinobuのintentだけであり、セッション内のCoordinatorの承認はharness層でintentとして数えられない**(2026-07-28実測)。したがってCoordinatorはYoshinobuへ上げる。
- ブロックされた事実と、その後の対応は記録に残す。**隠して迂回した場合、記録には成功だけが残る** — これが最も避けたい状態である。

根拠と実例は `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`。2026-07-28に、承認済みの削除操作でclassifierが2回ブロックし、subagentが3つ目の形で通過させた事例がある。**その形自体は妥当だった可能性が高いが、妥当かどうかを判定したのがブロックされた当人だった点が問題だった。**

## 開発と本番の境界

```text
ansy  = 開発、レビュー、検証、commit/push準備
Git   = 確定済みコードと文書の正本
quory = Gitから取得した確定済みコードの本番実行基盤
```

- quory上で原則としてコードを直接編集・commitしない。
- 未確認のコードをquoryの定期実行(timer / Semaphore schedule)へ載せない。
- 作業開始時に `git status` と関連diffを確認する。
- ユーザーや他Agentの既存変更を保護し、依頼範囲外の変更を上書き、破棄、整形しない。
- read-onlyの確認と変更系処理を分離する。check、patch、reboot、migrationを同じ入口へ安易に混在させない。

## 公開情報と秘密情報

このリポジトリは公開される前提で扱う。

- 秘密鍵、パスフレーズ、password、token、証明書秘密鍵、Vault平文などの秘密情報を保存、表示、生成、複製しない。
- 内部IPアドレスをinventory、変数、コード、レビュー文書を含むリポジトリ内へ直接記載しない。DNS名または実行時の名前解決を使う。
- runtime report、retry、ローカル専用overrideなどを意図せずcommit対象へ入れない。
- SSHポート、ユーザー、認証方式、対象ホストを根拠なく推測して固定しない。

## 作業時に読む情報

情報は必要な範囲だけを、次の順序で選ぶ。

1. 本ファイルで共通原則を確認する。
2. 対話セッションのCoordinatorは `docs/ai/status.md` で現在地を確認する(SessionStart hookが自動で載せる。載っていなければ読む)。subagentは案件依頼文で足りるため、指示がない限り読まない。
3. `docs/ai/role-routing-index.md` で自分のRoleとその実現方式を確認する。
4. requirement、review、test_planなど、依頼で指定された案件記録を読む。
5. `docs/ai/core-migration-map.md` の該当行から、対象のSystem / Repository / Operations ContextとPolicyだけを辿る。
6. 作業内容に一致するSkillを使う。
7. 過去の経緯が判断に必要な場合だけKnowledgeを読む。
8. 実装・レビュー・テストでは、コード、git status、diffで現状を再確認する。

Role、Context、Policy、Skill、Knowledgeの新配置は段階的に作成する。まだ存在しない情報は、Roleとroutingについては `docs/ai/role-routing-index.md`、個別ルールについては `docs/ai/core-migration-map.md` の該当行を入口とし、その行が指す既存Policyまたは旧coreの正確な節だけを参照する。関連しそうな旧coreやreviewsを無差別に探索しない。

## Role・Skill・Contextの関係

- Roleは「誰として何を判断し、何を成果物にするか」を定義する。
- Skillは「作業をどう進めるか」を定義する。環境台帳やRoleの権限をSkillへ埋め込まない。
- Contextは環境とリポジトリの事実を記録する。変化する事実を共通原則へ複製しない。
- Policyは対象業務の許可、禁止、停止条件を定義する。
- KnowledgeはIncident、Lesson、Decisionなど、再利用する価値が確認された知識を記録する。一時的な失敗を直ちに恒久ルールへ昇格させない。
- Issueは今回の要求と受入条件、PR/diffは今回の変更を表す。当面はCoordinatorからの依頼文、`docs/ai/reviews/`、作業ツリーがこれらを担う。

identity名だけから責務や権限を推測しない。identityとRoleの対応、Roleの実現方式(Coordinator直接実施かsubagent呼び出しか)は `docs/ai/role-routing-index.md` を正本とする。

## Ansible変更の共通ゲート

- 対象playbookの `# tester-gate:` マーカーと関連Policyを確認する。
- `safe-readonly` / `role-guarded` / `risk-accepted` / `check-mode-native` / `dry-run-aware` の詳細な意味、実行方法、Roleごとの実行義務は `docs/ai/policies/ansible_test_safety_policy.md` を正本とする。
- `check-mode-native` / `dry-run-aware` を `--check` なしで実行することは本番適用であり、Tester役は行わない。
- check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない。詳細な責務分離は `docs/ai/context/operations/healthcheck.md` を参照する。

## AI間連携と成果物

Role間の連携はCoordinatorを起点とするsubagentの起動と、その最終報告で行う。subagentの対話ログは永続しない前提とする。

- 成果物本文と監査証跡は必ずリポジトリ内へ保存する。判断の根拠を最終報告だけに残さない。
- 報告には対象パス、短い結果、判断、未解決事項を載せる。中間ログや長い引用を報告本文へ貼らない。
- 受信側は報告の説明だけを信頼せず、指定されたファイルと現在のdiffを読む。
- Role間の調整経路は `docs/ai/role-routing-index.md`、成果物形式は `docs/ai/core-migration-map.md` の§15–16行から辿る既存節に従う。
- 不一致や競合を見つけた場合は勝手に統合せず、停止してCoordinatorへ返す。

書き出す文書の長さは、案件が必要とする範囲に合わせる。実質(判断・根拠・未解決事項)は省略せず、水増しになる要約の重複、定型の前置き、既に別ファイルにある内容の再掲を足さない。既存ファイルへ追記する場合は、追記のたびに節を積み増すのではなく、結論が最新の状態を指すよう既存節を更新する。

## 原則の保守

新しいルールを本ファイルへ追加する前に、全Roleが毎回読む必要がある不変原則か確認する。Role固有手順、環境詳細、個別Policy、一般的な実装手順、過去のIncident、案件固有要求は、それぞれRole、Context、Policy、Skill、Knowledge、Issueへ置く。

旧 `core.md` の各項目の移動判断は `docs/ai/core-migration-map.md` を参照する。

## 変更履歴

| 日付 | 変更 |
|---|---|
| 2026-07-22 | 旧共通promptから全AI Role共通原則を分離し、現行coreを正本化 |
| 2026-07-25 | 共通原則本文を変更せず、正本保守のため変更履歴を追加 |
| 2026-07-27 | 現在地(状態)の正本として `docs/ai/status.md` を新設し、読む順へ追加。規範はリポジトリにあるが状態はセッションの記憶にしかない、という非対称を解消するため |
