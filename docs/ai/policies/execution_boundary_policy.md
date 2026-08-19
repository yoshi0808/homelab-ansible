# Execution Boundary Policy

本書は、**AIが実ホストへ何をしてよいか、誰の承認が要るか**の正本である。対象業務ではなく実行主体の側で引く境界を扱うため、**全Roleが起動時に読む**(`docs/ai/role-context-matrix.md`)。他のPolicyのように該当分野のときだけ読むものではない。

環境事実と実装詳細は対応Contextを参照し、競合時は本Policyを優先する。**実際に強制している機構は `.claude/settings.json` が正本であり、値を本書へ写さない。**

## 1. 目的

<!-- EXEC-001 -->
**判断軸は「Policy(`docs/ai/policies/*_policy.md`)の許可・禁止・停止条件に触れるか」である。** 触れるものはYoshinobu、それ以外はCoordinatorの権限とする。**列挙されていないものを勝手にYoshinobu必須へ格上げしない。**

<!-- EXEC-002 -->
**実効的な境界は、承認の規則ではなく能力の不在で作られている。** `pve1` / `pve2` / `authy` / `quory` / `sophos-fw` / `monnie` へ、ansyは書込のできる接続手段を持たない。届くのは read 専用の forced command dispatch だけで、そこに書込の語彙は1つも無い。**本書の承認区分は、届く相手についてしか意味を持たない。**

<!-- EXEC-003 -->
**能力が欠けている場所は、ホストによって違う。この違いは壊れ方の違いである。**

| ホスト | 欠けているもの | 復活のしかた |
|---|---|---|
| `quory` / `pve2` / `authy` | **鍵そのものが ansy に無い**(`~/.ssh/id_ann` は2026-08-19に削除)。受け側の `authorized_keys` も受け付けない | **戻すには新しい鍵を作るところから。**2026-08-18まであった「相手側で1行足せば復活する」経路は、秘密鍵の削除で消えた |
| `monnie` | **同上**(`id_ann` の削除で閉じた、2026-08-19)。**読み取り専用の名前付きチェックは `monnie-investigate` で今も通る** | 同上 |
| `pve1` | **未確認**(平日停止のため到達せず判定できていない)。同じ鍵・同じユーザー・同じ group_vars のため `pve2` と同じと見るのが自然だが、確かめてはいない | 同上 |
| `sophos-fw` | **鍵ファイルそのものが無い**(`~/.ssh/id_rsa_sophos` は存在しない)。これは欠落ではなく規範の実装である(EXEC-006) | ansy 側で鍵を用意しない限り復活しない |

<!-- EXEC-006 -->
**開発環境から `sophos-fw` へ接続しない**(Yoshinobu、2026-08-18)。`~/.ssh/id_rsa_sophos` が ansy に存在しないのは**この規範を能力で実装したもの**であり、直すべき欠落ではない。**鍵を作らない、置かない、他ホストからコピーしない。**

`sophos_trim.yml` と `time_sync_check.yml` の sophos 分岐は、Ansible の接続プラグインではなく `delegate_to: localhost` + `expect` の中で自前の `ssh -i` を起動する(メニューから advanced shell へ遷移する対話が要るため)。**したがって ansy から流すと必ず ssh の時点で失敗する。これは正しい失敗である。** 両playbookはquoryのSemaphoreから実行する(`roles/semaphore_templates/defaults/main.yml`)。

**`group_vars/sophos.yml` の `ansible_ssh_private_key_file` は、Ansibleの接続設定ではなく `expect` へ渡す `ssh -i` の引数の置き場である。** 変数名から接続設定と読まない。

<!-- EXEC-004 -->
**受け側で失効させた境界は、日次のドリフト検査の対象外である。** 検査が見ている `authorized_keys` は `recovery-exec` と `dev-investigate` の2つで、`ann` のものは含まない。**「届かない」は、こちらから確かめ続けられる性質ではない**と理解して扱う。

<!-- EXEC-005 -->
**鍵を用途で分け、`id_ann` は ansy から削除した**(Yoshinobu決定、2026-08-19)。それまで `id_ann` は到達できる相手(`monnie` / `sandbox` / `ansy`)と到達できない相手の両方の `group_vars` から指されており、**鍵を用途で分けていないため「鍵の不在」で境界を表現できなかった**。**いま ansy が持つのは `id_sandbox` だけで、これは `sandbox` しか開けない。**

**本番の `monnie` の管理は何も止まっていない** — `monitoring_servers` を対象にする playbook 12本はすべて quory の Semaphore template に載っており、quory 自身の鍵で走る。止まったのは ansy 自身が起動する実行、つまり開発とテストである。

**`monnie` を相手にした開発用の到達先(VM の複製)を作るかは未決である。** 先に鍵を切り、不便を実際に測ってから判断する(Yoshinobu、2026-08-19)。

**`inventories/homelab/group_vars/` の6本は `~/.ssh/id_ann` を指したまま残してある。整理の対象にしないこと。** これらを読むのは quory の Semaphore でもあり、そこでは quory 自身のホームへ解決される — 削除当日のジョブ #763 が pve1 / pve2 へ `unreachable=0` で到達している。**ansy から見ると存在しないファイルを指すが、それがansy側で失敗する正しい形である。** (quory 上にそのパスの実体があるかどうかは、開発側からは確かめられない。dispatch のカタログにファイルを見る手段が無い。)

## 2. 対象と実行範囲

<!-- EXEC-010 -->
**境界はホストで引く。「書き込むかどうか」では引かない。**

| 区分 | ホスト | 根拠 |
|---|---|---|
| 保護対象 | `pve1` / `pve2` / `authy` / `sophos-fw` / UniFi機器 | 家庭向けサービスを提供しており、停止が生活に影響する |
| 到達手段が無い | `pve1` / `pve2` / `authy` / `quory` / `sophos-fw` / **`monnie`** | ansyが書込のできる接続手段を持たない(内訳と壊れ方は EXEC-003)。**`monnie` は2026-08-19に加わった** |
| それ以外 | `monnie` / `ansy` / `sandbox` | 家庭向けサービスを提供せず、内容はGitから再現可能か、失っても停止を招かない観測データである |

<!-- EXEC-011 -->
**`sandbox` は壊れてよいものとして用意されている**(Yoshinobu、2026-08-06)。監視対象ではなく、他に何もこのホストへ流さない。

<!-- EXEC-012 -->
**この区分は `.claude/settings.json` の `autoMode` と対応させて維持する。** 片方だけ変えるとドリフトする。

## 3. 対応するPlaybook

<!-- EXEC-020 -->
**特定のplaybookに紐づかない。** 本書は実行主体の側で引く境界であり、全playbookおよびplaybook以外の実行手段(ad-hoc、dispatch、CLI)に等しくかかる。個別playbookの安全分類(`# tester-gate:`)は `docs/ai/policies/ansible_test_safety_policy.md` が正本であり、**本書と直交する** — 分類が実行してよいと言っても、対象ホストが本書で承認を要するなら承認が要る。

## 4. 判断軸

### 4.1 承認区分

<!-- EXEC-030 -->

| 区分 | 扱い |
|---|---|
| `git commit` / `git push` | **Yoshinobuの都度承認を得てCoordinatorが実行する。** 承認プロンプトを出す前に、stageした内容の分類とcommitメッセージ案を提示する — プロンプト自体にはdiffが載らないため、提示が無ければ承認は形式になる |
| Policy本文の改訂、要件段階で未許可の破壊的操作、復旧不能なデータ削除、安全境界そのものの変更 | 常にYoshinobuへ上げる |
| **保護対象ホスト**への非冪等操作でYoshinobu承認済みscope内のもの | Coordinatorが着手前に計画を確認し承認。scope外/不明なら停止してYoshinobuへ。**このうち `pve1` / `pve2` / `authy` / `sophos-fw` へは到達手段が無く、次行が優先する** — 届かない要求に発火しても無害であり、認証情報が復活したとき意図が生き残るため、行そのものは残す |
| **到達手段が無いホスト** | **承認の対象ではない。届かない。** 配備・適用が要るときはquoryのSemaphore(Yoshinobu起動)へ回す |
| **上記以外のホスト**への非冪等操作 | **確認不要**。Coordinatorが判断し実施、事後報告 |
| 冪等な操作カタログへの追加(allowlist等) | 事前承認不要。追加した事実と内容を事後報告。Codexからも呼べるカタログの場合はその旨明記 |
| systemd timer/serviceの有効化・無効化等、**Policyに関わらず**逆操作で戻せる運用切替 | Coordinatorが判断し実施、事後報告 |
| `soft_deny` / `hard_deny` に該当する操作 | Coordinatorの承認では通らない。harnessのブロックはYoshinobu本人のintentのみ解除可。発火したらYoshinobuへ上げる(`git commit` / `git push` は1行目が扱う。あれもYoshinobu本人のintentで通る `soft_deny` であり、例外ではなく同じ規則の適用である) |

### 4.2 状態を変えない確認は、承認の対象外

<!-- EXEC-040 -->
**状態を変えない確認は、どのホストに対しても確認不要である。** 確認を制約で塞ぐと、確認の代わりに推測が入る。

<!-- EXEC-041 -->
**冪等であることは「変えない」の根拠にならない。** `systemctl stop` やAnsibleのapplyは何度実行しても同じ状態になるが、本番を止める。

<!-- EXEC-042 -->
**提示不要**: 状態を変えない確認(healthcheck / `--syntax-check` / `--check`経由 / `ansible-lint`)、decoy inventoryでの検証、ansyリポジトリ作業ツリーと`/tmp`に閉じた操作、`hosts: localhost` + `connection: local` で副作用のない使い捨てplaybook(検証後削除し、実行事実を記録へ残す)。

<!-- EXEC-043 -->
**届かないホストでは、Coordinator自身が使える手段はdispatchが公開する名前付きチェックだけである。** 一覧は `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`。**カタログに無いことを理由に、自分で別の手段を組み立てない。** カタログに無い事実が要るとき、検証の難易度が高いとき、本番でしか再現しないときは、Operator Request Channelでquory側Operatorへ調査を依頼する(運用の正本は `docs/ai/context/operations/operator-request-channel.md`)。requestは情報交換だけを行い、本番操作の指示にはしない。

### 4.3 Roleごとの実行可否

<!-- EXEC-050 -->

| Role | 実ホストへの到達 |
|---|---|
| Coordinator | 状態を変えない確認は可。状態を変える操作は4.1に従う。**受入条件(AC)の実機検証は自分で済ませない**(Testerへ渡す) |
| Tester | **subagentのうち、実ホストへ到達してよい唯一のRoleである。** 保護対象ホストへの非冪等操作は、着手前に計画をCoordinatorへ提示して承認を得る |
| Implementer / Reviewer | **実ホストへansibleを実行しない。状態を変えない確認も含む。** 必要と判断したら実行せず、理由を添えてCoordinatorへ返す |
| Auditor | 実ホストへ触れない |

<!-- EXEC-051 -->
**実ホストへ触れないRoleでも、次の3つは実行してよい** — `--syntax-check`等のローカル検証、decoy inventoryでの検証(成立条件は `docs/ai/core.md`「Ansible変更の共通ゲート」)、ansyのリポジトリ作業ツリーと`/tmp`に閉じた操作。

<!-- EXEC-052 -->
**Testerが使ってよい検証環境**。到達可否が環境ごとに違う。**足りないと判断したら、権限や経路を自分で広げずCoordinatorへ返す。**

| 環境 | 到達 | 用途 |
|---|---|---|
| decoy inventory | 直接使える(承認不要) | 実ホストへ触れずに実行経路を通す |
| **`ansy`のSemaphore** | **直接使える** | quoryとは別インスタンスで、**SSH鍵を持たずどのホストへも到達できずcloneもできない**。この無害さゆえに**APIの実挙動を本番へ触れずに確かめられる**。**鍵を再登録しない** — した瞬間にこの性質が失われる。素性と既知の落とし穴は `docs/ai/context/system/semaphore.md` |
| **`sandbox` VM** | **AIからは起動できない** | 自律復旧ラダーの検証用target。probeの窓の開閉もfailover段のテンプレート起動もquory上の操作であり、ansyは到達手段を持たない。必要ならCoordinator経由でYoshinobuへ回す。前提は `docs/ai/context/system/autonomous-recovery.md`「検証用target」 |

## 5. ライフサイクル・処理フロー

<!-- EXEC-060 -->
**打鍵を伴う承認の入口を増やさない。** ansyでYoshinobuに押させてよいのは `git` の確定だけとし、本番実行の承認はquory側で押す。判断を要さない打鍵が混ざるとゲートは薄まり、この機構は確認プロンプトが希少であることで機能している。**方針・採否・安全境界の変更をYoshinobuへ確認することは、ここでいう入口に当たらない**(それらは打鍵ではなく対話で決まる)。

<!-- EXEC-061 -->
迷ったら上げてよい。ただし必ず推奨を添える。**既に推奨済みの事項へ同意の再確認を求めない。**

## 6. 通知方針

<!-- EXEC-070 -->
**本Policy固有の通知は無い。** 承認は対話で行われ、Slack等の通知経路を使わない。playbookの通知方針は各業務Policyが定める。

## 7. 制約・禁止事項

<!-- EXEC-080 -->
**安全機構(permission classifier、`permissions.deny`、`autoMode`)がブロックしたら、別の形で同じ結果へ到達しない。** 止めて、ブロックされた事実をCoordinatorへ報告する。**ブロックが妥当かどうかを判定しない** — 被ブロック側もCoordinatorも解除できない。

<!-- EXEC-081 -->
**ただし、その操作が目的に本当に必要かは問い直してよい。** 必要でなければ、迂回でも停止でもなく、**その結果を必要としない形へ検証設計を組み替える**のが正解になる。**この場合は必ず報告する** — 報告が無ければ迂回と区別が付かない。

<!-- EXEC-082 -->
**実行identityを昇格しない。** `sudo --become-user` 等で別のidentityを引き受けない。到達できないと分かったら、権限の足りる経路を探さず止めてCoordinatorへ返す。「正しいidentityを使っただけで迂回ではない」という整理でこれを越えない。

<!-- EXEC-083 -->
**この機構を変更したときは、症状ではなく設定そのものを確認する。** `.claude/settings.json` の `permissions.defaultMode` と `autoMode` は両方が揃って初めて機能し、片方が欠けたときの症状は「確認プロンプトが増える」という安全側の壊れ方であるため、壊れていても異常に見えない。

## 8. 変更履歴

| 版 | 日付 | 内容 |
|---|---|---|
| v1.1 | 2026-08-19 | **`id_ann` を ansy から削除**し、`sandbox` 専用の `id_sandbox` へ分けた。EXEC-003 に `monnie` の行を足し、**「相手側で1行足せば復活する」経路が消えた**ことを書いた。EXEC-005 を過渡期の記述から実施済みの内容へ差し替え、EXEC-010 の「到達手段が無い」へ `monnie` を加えた |
| v1.0 | 2026-08-18 | 新設。`docs/ai/roles/coordinator.md`「実ホストへの非冪等操作の承認」、`docs/ai/core.md`、`docs/ai/roles/tester.md`「使ってよい検証環境」、`implementer.md` / `reviewer.md` の禁止節に分散していた実行境界を1本へ集約した。**分散していたのは単一の問いの答えであり、6箇所のうち2箇所が実際にドリフトしていた。** 移設した規範に追加・削除は無い。**EXEC-020 だけが新規である** — `# tester-gate:` 分類と本書が直交することは、分散していた間はどの文書も書いていなかった |
