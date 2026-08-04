# 2026-08-02〜08-04 に事実として変わったこと(掃引の共通入力)

作成日: 2026-08-04 / 作成: Coordinator

**このファイルは事実の一覧であり、findingsではない。** 「どの文書が古くなったか」「何が矛盾しているか」は**意図的に書いていない** — それを独立に検出することが本掃引の目的である。各項目は commit で裏が取れるので、必要なら `git show <hash>` と現物で確かめること。

対象期間の commit は41本(`git log --since=2026-08-02`)。うち規範文書に触れたものが22ファイル。

## 1. ansy から本番ホストへの到達手段が無くなった(dev_prod_boundary 案件、Phase 1〜4)

`25e5e80` `0e412e5` `ce32268` `3e8b336` `5140306` `07d8e94` `33f8898` `795cff3` `5328ff7` `c11fccd` `e07e48a` `7904ba2` `73dd527`

- **ansy は `pve1` / `pve2` / `authy` / `quory` / `sophos-fw` に対する認証情報を1つも持たない。** SSH鍵を削除した(`id_rsa_sophos` を含む)。
- ansy からこれらのホストへ届く経路は、**forced command dispatch 1つだけ**である。dispatch が公開するのは名前付きの read チェックのみで、書込の語彙は無い。公開されているチェックの一覧は `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md`。
- 期間中に dispatch へ追加された read チェック: `acl-status` / `users` / `unit-files` / `forced-command-keys` / `deployed-hash` / `unit-cat` / `journal-ssh` / `semaphore-query template-list` / `semaphore-query running`。
- **`monnie` への到達は残っている。**
- 本番Ansibleの実行は quory の Semaphore が担う。quory 上では `ansible_connection` が `local` へ切り替わる(`inventories/homelab/host_vars/quory.yml`)。

## 2. incident_sync(転送段)が退役した

`7904ba2` `6a592a9`

- 障害捕捉パイプラインが **4段から3段**になった。ansy へ毎時複製する段は存在しない。
- 月次の滞留カウントは dispatch 経由の読み取りへ移した。
- `incident_capture_policy.md` は同時に改訂済み(IC番号の新設・退番あり)。

## 3. 月次のKnowledge振り返りから無人セッションが無くなった

`6a592a9`

- `claude -p` を使う無人ジョブ2本を**廃止**した。
- systemd timer が出すのは「きっかけの通知」だけで、振り返り自体は Yoshinobu が主体で行い、対話セッションが補助する。
- **この環境に無人の Claude Code セッションは1つも残っていない。**
- 証拠の保持期間は quory 側1コピーのみとなり 90日へ延長した。

## 4. `git commit` / `git push` が全面禁止から都度承認(ask)になった

`079ea09` `a7012fa` `b368a50`

- 対話セッション(Coordinator)は、Yoshinobu の都度承認を得てから実行してよい。承認なしには行わない。
- **subagent は承認の有無にかかわらず行わない。**
- `push` 側も承認プロンプトを通ることを実地で確認済み。

## 5. quory の作業ツリーが自動で追随するようになった

`68f40b4` `c9d64b8` `60ec11a` `2b7130a` `58fc343`

- `worktree_sync`(1分間隔の systemd timer)が `git pull --ff-only` を行う。
- 日次ドリフト検査に `worktree-sync.timer` の生存を追加した。
- **Semaphore はジョブ実行のたびに GitHub から `/opt` 配下へ clone しており、この作業ツリーを共有していない**(2026-08-04にYoshinobuが明示)。

## 6. 配備の経路が Context として明文化された

`fc3201d` `2a0c898` `d4f7e2e` `8ad9294`

- `docs/ai/context/operations/code-delivery-to-production.md` を新設。
- **`git pull` は配備物(`/usr/local/`・`/etc/systemd/system/` 配下)を更新しない。** 配備は人が Semaphore から流す。
- commit 時に「配備が要る」と予告する検査(`scripts/check-deploy-needed.py`)と、日次ドリフト通知の「直し方」の行を追加した。
- 変更1つに対して人が押すのは2回(`git` の確定、Semaphore のボタン)。

## 7. Semaphore のテンプレートが repo の正本になった

`65923ae` `c8bebbf` `bffa6ba`

- 定義の正本は `roles/semaphore_templates/`。同定は各 template の `description` に書いたマーカーで行う。
- **schedule / inventory / environment は管理対象に含めていない。**

## 8. 規範文書そのものの変更(2026-08-04)

`ac7555f` `95774da` `f8e69ed` `194ff9f` `1914459`

- `docs/ai/core.md`「人間の権限と安全境界」に2点を追加 — **Yoshinobu は判断者であって実行者ではない**。**打鍵を伴う承認の入口を増やさない**(ansy で押させてよいのは `git` の確定だけ)。
- `docs/ai/core.md`「開発と本番の境界」に1点を追加 — forced command dispatch に何を持たせてよいかは「quory に触れるか」ではなく**「本番の状態を変えるか」**で決める。
- `docs/ai/core.md`「開発と運用の分離」を書き直した。**エージェント名(Claude Code / Codex)を全廃し、原則だけにした** — 開発側はコードを書けるが実行の権限を持たず、運用側は実行できるが実行する中身を変えられない。このプロジェクトに「このエージェントに任せる」という決めは無い。
- `docs/ai/roles/coordinator.md` に1点を追加 — **経緯は commit メッセージへ書く。** `docs/ai/memory/decisions/` へ独立したファイルを起こすのは例外。
- `docs/ai/memory/decisions/ansy-must-not-trigger-production-changes.md` を新設(配備を ansy 側から起動する2案の却下理由)。

## 9. その他、期間中に確定した事実

- `a0eef95` ACPI shutdown の非対称は欠陥ではなかった(実測でクローズ)。
- `19170f8` `b0b6058` `journal-ssh` の配備後確認と `Connection reset by peer` の決着。
- `03de668` Lesson を2件昇格(`enumerate-credentials-that-reach-you-not-those-you-placed` / `blocked-redesign-the-verification-not-the-route`)。
- `76b6ecb` 規約(時刻表記JST等)を、守る人の見える場所へ移した。
- `8ad9294` 日次ドリフト検査が `incident-investigate.py` の版ずれを実際に検出し、再配備で解消した。
