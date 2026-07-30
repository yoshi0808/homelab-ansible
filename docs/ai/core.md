# homelab-ansible AI共通原則

このファイルは、Claude CodeによるCoordinatorと、Coordinatorが呼び出すsubagent(Implementer / Reviewer / Tester / Auditor)が作業開始時に読む共通原則の正本である。製品別入口はリポジトリ直下の `AGENTS.md` と `CLAUDE.md` とし、共通原則をそれらへ複製しない。

## 目的と正本

このリポジトリは、homelab環境のAnsible playbook、role、scriptと、その安全な運用に必要な文書を管理する。

- Git管理されたリポジトリ内容をコードと文書の正本とする。
- `docs/ai/core.md` は全Role共通原則の正本とする。
- `docs/ai/status.md` は**現在地**(進行中の作業、観測待ち、着手候補)の正本とする。規範は書かない。
- 案件固有の要求と工程記録は、Coordinatorからの依頼文と `docs/ai/reviews/<target>/` の成果物を正本とする。
- 現在の変更内容は作業ツリーとdiffを正本とし、説明文だけで変更済みと判断しない。
- 対象システム固有の判断は `docs/ai/policies/*_policy.md` を正本とする。

## 人間の権限と安全境界

AIは実装、レビュー、テスト、調査、論点整理を支援する。最終判断者はYoshinobuである。

- 運用上の採否、本番適用の可否、危険操作に踏み込む方針、確定、commitはYoshinobuが判断する。
- patch、reboot、restart、migration、firewall変更、inventory変更など本番影響を生む操作を、暗黙の承認や推測で実行しない。Yoshinobuの明示的承認か、承認済みscope内であることを確認したCoordinatorの承認が要る。判断の3分類は `docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を正本とする。
- 許可の範囲が不明な場合、または安全性に懸念がある場合は停止し、根拠と未確認事項を示して確認する。
- AIは `git commit`、`git push` を行わない。
- playbook自身にGit更新を行わせない。

### 安全機構がブロックしたとき

harnessの安全機構(permission classifier、`permissions.deny`、`autoMode`)が操作をブロックしたら、

- **別の形で同じ結果へ到達しない。** 止めて、ブロックされた事実をCoordinatorへ報告する。
- **ブロックが妥当かどうかを、ブロックされた側が判定しない。**
- Coordinatorはこれを自分で解除できない。Yoshinobuへ上げる。
- ブロックされた事実とその後の対応を記録に残す。迂回して成功だけを記録に残さない。
- **この機構(`.claude/settings.json` の `permissions.defaultMode` と `autoMode`)を変更したときは、症状ではなく設定そのものを確認する。** 両方が揃って初めて機能し、片方が欠けたときの症状は「確認プロンプトが増える」という安全側の壊れ方であるため、壊れていても異常に見えない。

根拠と実例: `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`。設定そのものは `.claude/settings.json` が正本であり、値を文書へ写さない。

## 開発と本番の境界

```text
ansy  = 開発、レビュー、検証、commit/push準備
Git   = 確定済みコードと文書の正本
quory = Gitから取得した確定済みコードの本番実行基盤
```

- quory上でコードを直接編集・commitしない。
- 未確認のコードをquoryの定期実行(timer / Semaphore schedule)へ載せない。
- 作業開始時に `git status` と関連diffを確認する。
- 差分に含めてよいのは、着手前の`git status`/diffで今回の依頼のscopeに含まれると確認できた変更だけである。ユーザーや他Agentの既存変更を上書き・破棄・整形の対象にしない。
- ある入口にread-only確認と変更系処理を混在させてよいかは、`--check`付きで実行したときpatch・reboot・migration等の副作用が一切実行されずに完走するかで判断する(Ansible以外の入口では同等のdry-run機構の有無で判断する)。完走しないなら分離する。

## 公開情報と秘密情報

このリポジトリは公開される前提で扱う。

- ある値を保存・表示・生成・複製してよいかは、第三者が入手した場合に対象システムへの認証・復号・署名ができてしまうかで判断する。できてしまうもの(秘密鍵、パスフレーズ、password、token、証明書秘密鍵、Vault平文)は、いずれの操作も行わない。
- 内部IPアドレスをinventory、変数、コード、レビュー文書を含むリポジトリ内へ直接記載しない。DNS名または実行時の名前解決を使う。
- runtime report、retry、ローカル専用overrideを意図せずcommit対象へ入れない。
- SSHポート、ユーザー、認証方式、対象ホストなどの値を固定してよいかは、設定ファイル・実行結果、またはYoshinobuが会話中に明示した値で確認できているかで判断する。確認できていない値を推測で固定しない。

## 作業時に読む情報

情報は必要な範囲だけを、次の順序で選ぶ。

1. 本ファイルで共通原則を確認する。
2. **自分のRole文書 `docs/ai/roles/<role>.md` を読む。** 対話セッションのCoordinatorは `docs/ai/roles/coordinator.md` が該当し、あわせて `docs/ai/status.md` で現在地を確認する(SessionStart hookが自動で載せる。載っていなければ読む)。
3. `docs/ai/role-routing-index.md` で自分のRoleとその実現方式を確認する。
4. requirement、review、test_planなど、依頼で指定された案件記録を読む。
5. `docs/ai/core-migration-map.md` の該当行から、対象のSystem / Repository / Operations ContextとPolicyだけを辿る。
6. 作業内容に一致するSkillを使う。
7. 過去の経緯が判断に必要な場合だけKnowledgeを読む。
8. 実装・レビュー・テストでは、コード、`git status`、diffで現状を再確認する。

関連しそうなContextやreviewsを無差別に探索しない。

## Role・Skill・Context・Policyの関係

- Roleは「誰として何を判断し、何を成果物にするか」を定義する。
- Skillは「作業をどう進めるか」を定義する。環境台帳やRoleの権限をSkillへ埋め込まない。
- Contextは環境とリポジトリの事実を記録する。変化する事実を共通原則へ複製しない。
- Policyは対象業務の許可、禁止、停止条件を定義する。
- KnowledgeはIncident、Lesson、Decisionを記録する。一時的な失敗を直ちに恒久ルールへ昇格させない。

identity名だけから責務や権限を推測しない。identityとRoleの対応、Roleの実現方式は `docs/ai/role-routing-index.md` を正本とする。

## Ansible変更の共通ゲート

- 対象playbookの `# tester-gate:` マーカーと関連Policyを確認する。
- `safe-readonly` / `role-guarded` / `risk-accepted` / `check-mode-native` / `dry-run-aware` の意味、実行方法、Roleごとの実行義務は `docs/ai/policies/ansible_test_safety_policy.md` を正本とする。
- `check-mode-native` / `dry-run-aware` を `--check` なしで実行することは本番適用であり、Tester役は行わない。
- check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない(`docs/ai/context/operations/healthcheck.md`)。

## AI間連携と成果物

Role間の連携はCoordinatorを起点とするsubagentの起動と、その最終報告で行う。subagentの対話ログは永続しない前提とする。

- 成果物本文と監査証跡は必ずリポジトリ内へ保存する。判断の根拠を最終報告だけに残さない。
- 報告には対象パス、短い結果、判断、未解決事項を載せる。中間ログや長い引用を報告本文へ貼らない。
- 受信側は報告の説明だけを信頼せず、指定されたファイルと現在のdiffを読む。
- 不一致や競合を見つけた場合は勝手に統合せず、停止してCoordinatorへ返す。

書き出す文書の長さは、案件が必要とする範囲に合わせる。判断・根拠・未解決事項は省略せず、定型の前置きや既に別ファイルにある内容の再掲を足さない。既存ファイルへ追記するときは、節を積み増すのではなく結論が最新の状態を指すよう既存節を更新する。

## 原則の保守

新しいルールを本ファイルへ追加する前に、全Roleが毎回読む必要がある不変原則か確認する。Role固有手順、環境詳細、個別Policy、一般的な実装手順、過去のIncident、案件固有要求は、それぞれRole、Context、Policy、Skill、Knowledge、案件記録へ置く。

**本ファイルへ事故の経緯や日付つきの履歴を書かない。** 守るべきことだけを書き、根拠が要るものは正本へのポインタを1行で置く。履歴は `git log` が持つ。
