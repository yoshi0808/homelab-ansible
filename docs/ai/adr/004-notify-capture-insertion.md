# ADR-004: `notify.yml` への捕捉(T1)の挿入方式・失敗隔離・相関IDの所有者

**Status:** Proposed

対象案件: `docs/ai/reviews/incident_auto_capture/2026-07-27_002_requirement.md`(R1、R3、R6、AC1、AC3、AC4)
前提決定: 同 `..._001_design_agreement.md` のD6(捕捉の起点は2つ。`notify.yml` 冒頭は抑止ゲートより前)、D7(要約と生ログの両方)
調査の一次記録: 同 `..._003_investigation.md`

## Context

`roles/common_slack/tasks/notify.yml` に捕捉(T1)を挿入する。ここは homelab-ansible で**最も広く共有されている1ファイル**であり、失敗すると全通知経路に波及する。

現物調査(HEAD `8310126`)で確定した事実:

1. **include は 38箇所 / 25ファイル**(D6・requirementの「33箇所」は古い値)。うち `playbooks/ubuntu_nightly.yml` が8箇所、`roles/ubuntu_vm_full_upgrade/` が7箇所。
2. **include はすべて `{{ playbook_dir }}/../roles/common_slack/tasks/notify.yml` という絶対形**で書かれている。`common_slack` は role として import されておらず、task fileを直接指名する形で共有されている。
3. **`notify.yml` は `run_once` を持たず、play のホストごとに実行される。** 全taskが `delegate_to: localhost` + `become: false`。したがって複数ホストのplayでは同一のnotifyが複数回走る。
4. **38箇所のうち13箇所は include 自体に `when:` を持つ。うち3箇所(`radius_healthcheck` / `monitoring_healthcheck` / `proxmox_healthcheck`)は `not skip_notifications` でゲートしている。** つまり `notify.yml` は「全ジョブ結果の絞り」ではなく「送ろうとした通知の絞り」であり、冒頭に何を置いても届かない経路がある。
5. `notify.yml` は既に `block:` / `rescue:` を使って Slack送信の失敗を握りつぶす形になっている(`:69-74`)。失敗隔離の前例が同ファイル内にある。
6. **T1はSemaphoreのジョブ番号を知らない可能性が高い。** playbook側からジョブIDが見えるかは未観測(`..._003_investigation.md` §9 T-OQ3)。一方 D6/R6 は「IDは発明せずジョブ番号を使う」と定めている。
7. `.gitignore` は `reports/**/*.{json,log,md}` のみを除外し、`*.tmp` はグローバルに除外される。

## Options Considered

### (a) 挿入の形

| Option | Pros | Cons |
|---|---|---|
| a-1: `notify.yml` 冒頭に捕捉taskを**直書き** | ファイルが1つで済む | 共有ファイルの行数が増え、以後の捕捉仕様変更のたびに38経路の入口を直接触ることになる。`notify.yml` を読む人が通知の話と捕捉の話を分離できない |
| a-2: 冒頭に `include_tasks` を**1行**足し、実体を `roles/common_slack/tasks/capture.yml` に置く | 共有ファイルへの差分が1タスク分に固定される。捕捉仕様の変更が `capture.yml` に閉じる。既存の「task fileを絶対形で指名して共有する」慣行と同じ形 | includeが1段深くなる(実行コストは無視できる)。指名するファイルが存在しないと**ハードエラー**になるため、パス指定を誤れない |
| a-3: Ansible **callback plugin** で全play/taskを拾う | `notify.yml` を一切触らない。UNREACHABLE中断・構文エラー・kill まで拾える | **D6の決定を覆す。** その死角はSemaphoreのDBが既に埋めており(D6)、重複する。加えて `ansible.cfg` の変更が38 playbook・Testerのansy実行・全ad-hoc実行に一律で効き、影響範囲がT1より遥かに広い。callbackはcontrollerプロセス内で動くため、例外時の挙動がAC4(観測が被観測を壊さない)にとってむしろ不利 |

### (b) 失敗隔離の機構

| Option | Pros | Cons |
|---|---|---|
| b-1: `block:` / `rescue:`(rescueは `debug` のみ) | 書き込みtaskの失敗も、taskの引数テンプレート展開失敗も rescue が受ける。**同ファイル `:69-74` に前例がある** | rescueに入ると `rescued=1` がPLAY RECAPに出る(failedは増えない) |
| b-2: 単一taskに `failed_when: false` | 最短。recapに何も足さない | `failed_when` 式そのものの評価失敗は救えない。taskを1つに保つ制約が付く |
| b-3: `ignore_errors: true` | 簡単 | PLAY RECAPの `ignored` が増える。**赤い "failed... ignoring" が全通知経路に毎回出て**、本物の失敗を読みにくくする |

### (c) 捕捉の条件付け

| Option | Pros | Cons |
|---|---|---|
| c-1: `slack_status` が `warning`/`critical`/`error` のときだけ書く | ファイル数が減る | **D7が最も価値を置いた食い違い(要約=`ok` / ジョブ全体=失敗、実例 #461)を構造的に検出できなくなる。** `when:` 式が1つ増え、それ自体がAC4の失敗経路になる |
| c-2: 到達したすべての通知を無条件に書く | D7の突き合わせが成立する。`when:` が無いためAC4の面が最小 | `ok` 通知でもファイルが1つ増える(1件あたり数KB。保持ローテーションで吸収できる規模) |

### (d) 相関IDを誰が決めるか

| Option | Pros | Cons |
|---|---|---|
| d-1: T1がバンドルIDを確定し、`reports/incidents/<id>/` を直接作る | AC1の文面(playbook実行後にバンドルが在る)にそのまま合う | **T1はSemaphoreジョブ番号を知らない可能性が高い**(制約6)。知らない場合IDを発明することになり、D6/R6「発明しない」に反する。仮にジョブID相当の環境変数が在ったとしても、T1がSemaphoreの実装詳細に結合する |
| d-2: T1は spool レコードだけを書き、**収集器がIDを確定する**。収集器がレコードをバンドルへ取り込む | ジョブ番号の入手可否に設計が依存しない。Semaphore外の通知も `timer-<unit>-<ts>` として同じ経路で扱える。T1が最小・最速のまま(R1「安価かつローカル完結、SSHもHTTPも行わない」)を保てる | AC1の観測時点が「playbook終了直後」から「次の収集周期の後」へずれる(requirementの差戻しが必要) |

## Decision

- **(a) a-2を採用。** `notify.yml` の**冒頭1行**に

  ```yaml
  - name: Capture notification evidence (best-effort, never fails the play)
    ansible.builtin.include_tasks: "{{ playbook_dir }}/../roles/common_slack/tasks/capture.yml"
  ```

  を置き、実体を `roles/common_slack/tasks/capture.yml` に書く。**パスは既存38箇所と同じ `{{ playbook_dir }}/../roles/...` の絶対形で書く**(相対 include にしない。`notify.yml` 自身がrole invocationではなく絶対形で指名されて読み込まれるため、相対解決に依存しない)。`notify.yml` の既存行は**1行も変更しない**。
- **(b) b-1を採用。** `capture.yml` の中身全体を `block:` / `rescue:` で包む。`rescue:` は `ansible.builtin.debug` 1つのみ。書き込みtaskには `changed_when: false` を付け、changed数も動かさない。**`assert` / `fail` / `ignore_errors` を使わない。**
- **(c) c-2を採用。** `capture.yml` に `when:` を付けず、到達したすべての通知を記録する。`slack_status: ok` も記録する。フィルタは収集器と叙述側(Step 2)が行う。
- **(d) d-2を採用。** T1はバンドルIDを決めない。`reports/incidents/_spool/<epoch>-<rand8>.json` にレコードを1件書くだけとする。収集器がSemaphoreジョブと突き合わせてIDを確定し、レコードをバンドルへ取り込む。
- **(補1) `check_mode: false` を付けない。** `--check` 実行では捕捉も書かない。`check_mode` の値自体はレコードのフラグとして持つ(通常実行時のみ書かれるので常に false になるが、将来 `check_mode: false` を足した場合に意味を持つ)。
- **(補2) 参照する変数はすべて `| default('')` を通す。** `slack_channel` / `slack_status` / `slack_title` / `slack_message` のいずれかを定義していない呼び出し元があっても、T1が原因でplayが落ちないようにする。
- **(補3) `no_log` を付けない。** T1は `vars/slack.yml` の読み込み(`notify.yml:23-28`)より**前**に走るため webhook URL / token に到達しない。記録すべき内容を隠さない。
- **(補4) ファイル名にランダム成分を必ず入れる。** 制約3により同一秒に複数ホスト分のレコードが出る。秒精度のタイムスタンプだけでは衝突する。既存ファイルを上書きしない書き方にする。
- **(補5) 一時ファイルは `*.tmp` を使い `rename` で確定する。** `*.tmp` はグローバルに `.gitignore` 済みで、中断時にも作業ツリーを汚さない。

## Trade-off Analysis

最大の争点は a-3(callback plugin)である。技術的には「捕捉」という要求に対して最も網羅的で、`notify.yml` を触らずに済む点でAC4に有利にも見える。**採らない理由は2つ**で、(i) D6が既に「Semaphoreのジョブ結果」で同じ死角(UNREACHABLE中断、構文エラー、kill)を埋めると決めており、callbackはその重複であること、(ii) `ansible.cfg` 経由の変更は38 playbookどころか**リポジトリ内のあらゆるAnsible実行**(Testerのansy実行、ad-hoc、開発中の試行)に一律で効き、影響範囲がT1より一桁広いこと。「観測が被観測の挙動を変えない」という要求に対して、影響範囲の広い機構を選ぶのは筋が悪い。将来D6を見直す場合の第一候補として記録しておく。

(b) の `block`/`rescue` は `rescued=1` をPLAY RECAPへ出す。AC1は「終了コードが同一」「failed数が増えていない」を要求しており `rescued` には触れていないが、**平常時に `rescued` が出続ける状態は誤りである**(rescueに入るのは捕捉が失敗したときだけ)。Testerは `rescued` も計測対象に含める。b-3(`ignore_errors`)を退けた理由は機能ではなく可読性で、全通知経路に毎回赤い行が出ると本物の失敗が埋もれる — これはAC4の文面には現れないが、AC4の趣旨(観測が運用を劣化させない)に含まれる。

(c) の無条件記録は「余計なファイルが増える」ように見えるが、**D7の突き合わせは `ok` のレコードが無いと成立しない**。D7の実例(Semaphore #461: 要約 `Result=OK` / ジョブ rc=4)は、まさに `ok` の要約と失敗したジョブを並べたときにだけ見える。c-1を選ぶと、設計合意が最も価値を置いた情報を実装段階で捨てることになる。

(d) の代償はAC1の文面との不一致である。これは実装を曲げて文面に合わせるべきではない — d-1を選ぶと「ジョブ番号を発明しない」(D6/R6)と両立できないケースが残る。**requirementの側を直す**のが正しく、`..._003_investigation.md` §7-3 でCoordinatorへ差し戻す。

なお、この決定でも**捕捉できない経路が残る**。制約4により、`skip_notifications: true` を渡すと3 role では `notify.yml` が include されず、冒頭に置いた捕捉も走らない。「抑止ゲートより前に置く」というD6の指示は `notify.yml` 内部のゲートについては満たせるが、caller側のゲートには届かない。これはT1の実装欠陥ではなく呼び出し構造の性質であり、AC3の範囲をCoordinatorが決める(同 §7-1)。

## Consequences

- `roles/common_slack/tasks/notify.yml` の差分は**先頭2行の追加のみ**になる。既存行の変更はゼロ。Reviewerはこの点を最初に確認する。
- `roles/common_slack/tasks/capture.yml` が新規に増える。**このファイルの出力スキーマはStep 2の入力契約になる**ため、`record_version` を持たせ、role内に仕様をコメントで固定する。
- Reviewerは **38箇所すべて**で、`slack_channel` / `slack_status` / `slack_title` / `slack_message` の4変数が定義されていることを照合する(補2でplayは落ちないが、空文字が記録されるとバンドルの質が落ちるため、欠けている呼び出し元があれば finding として上げる)。
- `--check` 実行では捕捉が走らない。Testerの `--check` ベースの検証では spool レコードが生成されないことを**期待挙動として**test planに明記する(生成されないことを不具合と誤認しない)。
- spool の場所は `reports/incidents/_spool/` とする。理由は、そこが「quoryでAnsibleを実行しているユーザが既に書けることが実証済みの唯一の場所」だからである(既存の各roleが `reports/<name>/` へ `delegate_to: localhost` + `become: false` でJSONを書いている)。repo外(`/var/lib/...`)へ置くと、Semaphoreがどのユーザで `ansible-playbook` を起動するかに依存する新しい書き込み権限問題が生まれる。
- 生成物の拡張子は `.json` のみ(一時ファイルは `.tmp`)。`.jsonl` は `.gitignore` の `*.json` に一致しないため使わない。
- AC1の観測時点をrequirement側で改める必要がある(§7-3)。AC3の範囲も同様(§7-1)。**両方ともCoordinatorの承認が要る。**
