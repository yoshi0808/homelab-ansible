# homelab-ansible AI共通原則

このファイルは、CodexとClaude Codeを含む全AI Roleが作業開始時に読む共通原則の正本である。製品別入口はリポジトリ直下の `AGENTS.md` と `CLAUDE.md` とし、共通原則をそれらへ複製しない。

## 目的と正本

このリポジトリは、homelab環境のAnsible playbook、role、scriptと、その安全な運用に必要な文書を管理する。

- Git管理されたリポジトリ内容をコードと文書の正本とする。
- `docs/ai/core.md` は全Role共通原則の正本とする。
- 案件固有の要求と工程記録は、agmsgの依頼と `docs/ai/reviews/<target>/` の requirement、implement、review、test_plan、test_result、finalを正本とする。
- 現在の変更内容は作業ツリーとdiffを正本とし、説明文だけで変更済みと判断しない。
- 対象システム固有の判断は、該当Policyを正本とする。Policyは `docs/ai/policies/*_policy.md` にある。
- `docs/ai/prompts/core.md` は移行元の旧正本である。未移行の詳細を確認するため残すが、共通原則は本ファイルを優先する。

## 人間の権限と安全境界

AIは実装、レビュー、テスト、調査、論点整理を支援する。最終判断者はYoshinobuである。

- 運用上の採否、本番適用、危険操作、確定、commitはYoshinobuが判断する。
- patch、reboot、restart、migration、firewall変更、inventory変更など、本番影響を生む操作を暗黙の承認や推測で実行しない。
- 許可の範囲が不明な場合や、安全性に懸念がある場合は停止し、根拠と未確認事項を示して確認する。
- AIは `git commit`、`git push` を行わない。
- playbook自身にGit更新を行わせない。

## 開発と本番の境界

```text
ansy  = 開発、レビュー、検証、commit/push準備
Git   = 確定済みコードと文書の正本
quory = Gitから取得した確定済みコードの本番実行基盤
```

- quory上で原則としてコードを直接編集・commitしない。
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
2. `docs/ai/role-routing-index.md` でagmsg identityから自分のRoleと案件ownerを解決する。
3. requirement、review、test_planなど、依頼で指定された案件記録を読む。
4. `docs/ai/core-migration-map.md` の該当行から、対象のSystem / Repository / Operations ContextとPolicyだけを辿る。
5. 作業内容に一致するSkillを使う。
6. 過去の経緯が判断に必要な場合だけKnowledgeを読む。
7. 実装・レビュー・テストでは、コード、git status、diffで現状を再確認する。

Role、Context、Policy、Skill、Knowledgeの新配置は段階的に作成する。まだ存在しない情報は、Roleとroutingについては `docs/ai/role-routing-index.md`、個別ルールについては `docs/ai/core-migration-map.md` の該当行を入口とし、その行が指す既存Policyまたは旧coreの正確な節だけを参照する。関連しそうな旧coreやreviewsを無差別に探索しない。

## Role・Skill・Contextの関係

- Roleは「誰として何を判断し、何を成果物にするか」を定義する。
- Skillは「作業をどう進めるか」を定義する。環境台帳やRoleの権限をSkillへ埋め込まない。
- Contextは環境とリポジトリの事実を記録する。変化する事実を共通原則へ複製しない。
- Policyは対象業務の許可、禁止、停止条件を定義する。
- KnowledgeはIncident、Lesson、Decisionなど、再利用する価値が確認された知識を記録する。一時的な失敗を直ちに恒久ルールへ昇格させない。
- Issueは今回の要求と受入条件、PR/diffは今回の変更を表す。当面はagmsgの依頼、`docs/ai/reviews/`、作業ツリーがこれらを担う。

identity名だけから責務や権限を推測しない。identity対応とtrio routingは `docs/ai/role-routing-index.md` を正本とする。

## Ansible変更の共通ゲート

- 対象playbookの `# tester-gate:` マーカーと関連Policyを確認する。
- `safe-readonly` / `role-guarded` / `risk-accepted` / `check-mode-native` / `dry-run-aware` の詳細な意味と実行方法は、`docs/ai/core-migration-map.md` の§18行から既存の正確な節を辿る。
- `check-mode-native` / `dry-run-aware` を `--check` なしで実行することは本番適用であり、testerは行わない。
- check系shellは原則として観測に留め、危険操作を混ぜない。詳細な責務分離はAnsible Policyまたは移行元を参照する。

## AI間連携と成果物

- AI間の依頼、完了報告、引き継ぎにはagmsgを使う。
- 成果物本文と監査証跡はリポジトリ内に保存し、agmsgには対象パス、短い結果、判断、未解決事項を載せる。
- 受信側はメッセージの説明だけを信頼せず、指定されたファイルと現在のdiffを読む。
- Role間の調整経路は `docs/ai/role-routing-index.md`、成果物形式は `docs/ai/core-migration-map.md` の§15–16行から辿る既存節に従う。
- 不一致や競合を見つけた場合は勝手に統合せず、変更の所有者とtechleadへ知らせる。

## 原則の保守

新しいルールを本ファイルへ追加する前に、全Roleが毎回読む必要がある不変原則か確認する。Role固有手順、環境詳細、個別Policy、一般的な実装手順、過去のIncident、案件固有要求は、それぞれRole、Context、Policy、Skill、Knowledge、Issueへ置く。

旧 `core.md` の各項目の移動判断は `docs/ai/core-migration-map.md` を参照する。
