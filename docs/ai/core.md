# homelab-ansible AI共通原則

このファイルは、Claude CodeによるCoordinatorと、Coordinatorが呼び出すsubagent(Implementer / Reviewer / Tester / Auditor)が作業開始時に読む共通原則の正本である。製品別入口はリポジトリ直下の `AGENTS.md` と `CLAUDE.md` とし、共通原則をそれらへ複製しない。

## 目的と正本

このリポジトリは、homelab環境のAnsible playbook、role、scriptと、その安全な運用に必要な文書を管理する。

- Git管理されたリポジトリ内容をコードと文書の正本とする。
- `docs/ai/core.md` は全Role共通原則の正本とする。
- `docs/ai/status.md` は**現在地**(進行中の作業、観測待ち、着手候補)の正本とする。規範は書かない。Coordinatorのauto-memoryは正本ではない。
- Role本文(責任・権限・成果物・禁止事項)は `docs/ai/roles/<role>.md` を正本とする。**identity名だけから責務や権限を推測しない。**
- 案件固有の要求と工程記録は、Coordinatorからの依頼文と `docs/ai/reviews/<target>/` の成果物を正本とする。
- 現在の変更内容は作業ツリーとdiffを正本とし、説明文だけで変更済みと判断しない。
- 対象システム固有の判断は `docs/ai/policies/*_policy.md` を正本とする。
- **競合したときは、Yoshinobuの当該案件に対する最新の明示指示が常に最優先である。**

## 人間の権限と安全境界

AIは実装、レビュー、テスト、調査、論点整理を支援する。最終判断者はYoshinobuである。

**Yoshinobuは判断者であって実行者ではない。** リスクを理解して採否を決めるのが役目であり、コマンドを組み立てて流すことではない。人の手に残すのは判断だけになるよう設計する。

- 運用上の採否、本番適用の可否、危険操作に踏み込む方針、確定、commitはYoshinobuが判断する。
- patch、reboot、restart、migration、firewall変更、inventory変更など本番影響を生む操作を、暗黙の承認や推測で実行しない。Yoshinobuの明示的承認か、承認済みscope内であることを確認したCoordinatorの承認が要る。判断の3分類は `docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」を正本とする。
- 許可の範囲が不明な場合、または安全性に懸念がある場合は停止し、根拠と未確認事項を示して確認する。
- **打鍵を伴う承認の入口を増やさない。** ansyでYoshinobuに押させてよいのは `git` の確定だけとし、本番実行の承認はquory側で押す。承認面は能力の所在に従わせる。判断を要さない打鍵が混ざるとゲートは薄まり、この機構は確認プロンプトが希少であることで機能している。**方針・採否・安全境界の変更をYoshinobuへ確認することは、ここでいう入口に当たらない**(それらは打鍵ではなく対話で決まる)。

### 安全機構がブロックしたとき

harnessの安全機構(permission classifier、`permissions.deny`、`autoMode`)が操作をブロックしたら、

- **別の形で同じ結果へ到達しない。** 止めて、ブロックされた事実をCoordinatorへ報告する。
- **ブロックが妥当かどうかを判定しない。** 被ブロック側もCoordinatorも解除できない。Yoshinobuへ上げる。
- **ただし、その操作が目的に本当に必要かは問い直してよい。** 必要でなければ、迂回でも停止でもなく、**その結果を必要としない形へ検証設計を組み替える**のが正解になる。これは別の手段で同じ結果へ到達することとは別物で、到達すべき結果の側を小さくしている。**この場合は必ず報告する** — 報告が無ければ迂回と区別が付かず、本質かどうかを都合よく判定していないことの担保がそれしかない。
- ブロックされた事実とその後の対応を記録に残す。迂回して成功だけを記録に残さない。
- **この機構(`.claude/settings.json` の `permissions.defaultMode` と `autoMode`)を変更したときは、症状ではなく設定そのものを確認する。** 両方が揃って初めて機能し、片方が欠けたときの症状は「確認プロンプトが増える」という安全側の壊れ方であるため、壊れていても異常に見えない。

設定そのものは `.claude/settings.json` が正本であり、値を文書へ写さない。実効的な境界は文章ではなく、能力の不在(鍵・到達先・wrapperが存在しないこと)で作る。

## 開発と本番の境界

```text
ansy  = 開発、レビュー、検証、commit/push
Git   = 確定済みコードと文書の正本
quory = Gitから取得した確定済みコードの本番実行基盤
```

- **ansyから本番へ届く唯一の経路(forced command dispatch)に何を持たせてよいかは、「quoryに触れるか」ではなく「本番の状態を変えるか」で決める。** 読み取り(情報共有)は持たせてよい。**状態を変えるものは、forced commandであっても持たせない。** dispatchへ動詞を1つ足す形の提案は、その動詞が情報を共有するのか状態を変えるのかで判定する。(到達できるホストどうしの承認の要否は別の軸で、`docs/ai/roles/coordinator.md` がホストで引く。)
- quory上でコードを直接編集・commitしない。
- **quoryのGit取得は自動だが、配備物(`/usr/local/` や `/etc/systemd/system/` へ配置したscript・unit)の更新は含まれない。** 経路と突合の手段は `docs/ai/context/operations/code-delivery-to-production.md`。
- 未確認のコードをquoryの定期実行(timer / Semaphore schedule)へ載せない。
- ある入口にread-only確認と変更系処理を混在させてよいかは、`--check`付きで実行したときpatch・reboot・migration等の副作用が一切実行されずに完走するかで判断する(Ansible以外の入口では同等のdry-run機構の有無で判断する)。完走しないなら分離する。

### 開発と運用の分離

**開発と運用を同じ主体に兼ねさせない。開発側はコードを書けるが実行の権限を持たず、運用側は実行できるが実行する中身を変えられない。**

運用が出す一次情報は原因の確定ではなく、真因の特定と修正の著述は開発側が行う。

## Gitの扱い

- 作業開始時に `git status` と関連diffで現状を確認する。
- 差分に含めてよいのは、着手前の `git status` / diff で今回の依頼のscopeに含まれると確認できた変更だけである。他者の変更を上書き・破棄・整形の対象にしない。
- **自分が作った変更以外を元に戻さない**(`git checkout` / `git restore` / `git stash` を含む)。
- `git add` を行うのはCoordinatorだけである。
- `git commit` / `git push` は、Yoshinobuの都度承認を得た対話セッションだけが行う。**subagentは承認の有無にかかわらず行わない。**
- playbook自身にGit更新を行わせない。

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
3. requirement、review、test_planなど、依頼で指定された案件記録を読む。
4. 対象領域のSystem / Repository / Operations Contextと、対象業務のPolicyだけを辿る(分類の定義は `docs/ai/context-classification.md`、誰がいつ読むかは `docs/ai/role-context-matrix.md`)。
5. 作業内容に一致するSkillを使う。
6. **Knowledge(`docs/ai/memory/`)を読むのはCoordinatorだけである。** subagentは読まない。過去の経緯のうち各Roleが常に持つべきものは、そのRole文書へ蒸留して置く。
7. 実装・レビュー・テストでは、コード、`git status`、diffで現状を再確認する。

関連しそうなContextやreviewsを無差別に探索しない。

## Role・Skill・Context・Policyの関係

- Roleは「誰として何を判断し、何を成果物にするか」を定義する。
- Skillは「作業をどう進めるか」を定義する。環境台帳やRoleの権限をSkillへ埋め込まない。
- Contextは環境とリポジトリの事実を記録する。変化する事実を共通原則へ複製しない。
- Policyは対象業務の許可、禁止、停止条件を定義する。
- KnowledgeはIncident、Lesson、Decisionを記録する。一時的な失敗を直ちに恒久ルールへ昇格させない。

Roleの実現方式(誰がどのモデルで、どう起動されるか)は `docs/ai/roles/coordinator.md` を正本とする。起動を決めるのはCoordinatorであり、他のRoleはこれを判断に使わない。

## Ansible変更の共通ゲート

- 対象playbookの `# tester-gate:` マーカーを確認する。分類(`safe-readonly` / `role-guarded` / `risk-accepted` / `check-mode-native` / `dry-run-aware`)の意味、実行方法、Roleごとの実行義務は `docs/ai/policies/ansible_test_safety_policy.md` を正本とする。
- `check-mode-native` / `dry-run-aware` を `--check` なしで実行することは本番適用であり、Tester役は行わない。
- check系shellは観測に留め、判定・分類・通知・保存をshellへ持たせない(`docs/ai/context/operations/healthcheck.md`)。

**decoy inventory** は、実ホストへ触れずに実行経路を通すための検証手段である。次の3条件を満たすものを指し、**全Roleで承認不要**とする(都度の提示も要らない)。

1. 実host名・実IPを書かない。
2. ループバック宛の閉ポート(接続拒否で `UNREACHABLE` を作る)または `ansible_connection: local` を使う。
3. 実システムに影響するモジュールを使わない。

値の目視で終えず、playbookを完走させる。**ただし完走は成立の証明ではない** — 対象モジュールが宛先を実際にどう決めるか(引数をそのまま使うのか、別のパラメータから組み立て直すのか)を確かめない限り、decoyが成立していると仮定しない。

**decoyが偽装するのは接続先だけで、実行主体(ansy自身)への副作用は防がない。** playbookが実行ホスト自身へ行う変更(ユーザー作成、`/etc/sudoers.d/`、ACL付与など)はdecoyでもそのまま起きる。**`--check` を添えたことを安全の根拠にしない** — `--check` が何を意味するかは対象playbookの分類が決めるものであり、decoyの側が決めるものではない。

## subagentが共通して守ること

Role間の連携はCoordinatorを起点とするsubagentの起動と、その最終報告で行う。subagentの対話ログは永続しない前提とする。起動時の依頼文に書かれていなくても、次はすべてのsubagentへ常に適用される。**依頼文はこれらを複製せず、案件固有の制限だけを書く。**

- 成果物本文と監査証跡は必ずリポジトリ内へ保存する。判断の根拠を最終報告だけに残さない。**実質的な証跡は `docs/ai/reviews/<target>/` 配下のファイル**(requirement / plan / implement / review / test_result / audit、該当すれば `docs/ai/adr/`)であり、subagentとのやりとりそのものではない。
- 報告には対象パス、短い結果、判断、未解決事項を載せる。中間ログや長い引用を報告本文へ貼らない。**書き出す文書の長さは案件が必要とする範囲に合わせる** — 判断・根拠・未解決事項は省略せず、定型の前置きや既に別ファイルにある内容の再掲を足さない。既存ファイルへ追記するときは、節を積み増すのではなく結論が最新の状態を指すよう既存節を更新する。
- 指定された成果物ファイルと `/tmp` 配下以外の、**リポジトリ内ファイルを自分で変更しない。**
- 他のsubagentが並行して作る未追跡ファイルを、自分の成果物として報告・削除・整形しない。
- **自分でさらにsubagentを起動しない。** 起動単位を決めるのはCoordinatorの責務である。
- **先行成果物・先行subagentの主張を、現物で確かめずに引き継がない。** 説明だけを信頼せず、指定されたファイルと現在のdiffを自分で読む。「検証済み」「無改修で流用できる」といった記述も、file:line・commitの参照も、自分で読むか実行して裏を取る。このリポジトリは短期間に文書が大幅改訂されるため、記録に書かれた参照が既に無効になっていることがある。
- **本番Slackへ通知が送られた状態で報告を返さない。** 通知経路を動かす検証では抑止変数を使うか、送信先が本番でないことを自分で確かめる。
- **実ホストへ触れてよい範囲は自分のRole文書が定める。** 依頼文がそれより狭い場合は依頼文が優先する。広げる方向へ解釈しない。
- 上記に反しそうな状況になったとき、および**記録どうしの不一致や他Agentの変更との競合を見つけたとき**は、別の手段で同じ結果へ到達せず、勝手に統合せず、止めてCoordinatorへ返す(「安全機構がブロックしたとき」と同じ扱い)。

これで塞げるのは書き落としまでで、解釈による逸脱は塞げない。

## 原則の保守

新しいルールを本ファイルへ追加する前に、全Roleが毎回読む必要がある不変原則か確認する。Role固有手順、環境詳細、個別Policy、一般的な実装手順、過去のIncident、案件固有要求は、それぞれRole、Context、Policy、Skill、Knowledge、案件記録へ置く。

**本ファイルへ事故の経緯や日付つきの履歴を書かない。** 守るべきことだけを書き、根拠が要るものは正本へのポインタを1行で置く。履歴は `git log` が持つ。
