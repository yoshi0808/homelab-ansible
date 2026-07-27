# レビューA: W6 通知経路の変更(`roles/common_slack/`)

日付: 2026-07-27(JST)
レビュー対象: `roles/common_slack/tasks/capture.yml`、`roles/common_slack/tasks/notify.yml`(未commit差分)
対象外(別レビュー): `roles/incident_capture/`、`scripts/`
参照: ADR-004、`2026-07-27_002_requirement.md`(R1/R3/R6, AC1/AC4/AC6/AC8)、`2026-07-27_011_w6_plan.md`、`2026-07-27_012_w6_implement.md`
返却先: Coordinator(W6はCoordinator起案・Tech Lead不在のため、`docs/ai/roles/reviewer.md`の`+R`相当の経路として扱う)

## 検証方法の要旨

実装記録の記述を鵜呑みにせず、以下を自分で確認した(すべて `hosts: localhost` + `/tmp` 配下の一時playbookで実施し、検証後に削除・`git status --short`で無害を確認済み。実ホストへは一切アクセスしていない)。

1. `ansible.builtin.copy`のatomicity: ローカルの`ansible-core`(`module_utils/basic.py: AnsibleModule.atomic_move`、`modules/copy.py: main()`)を直接読んだ。`content:`指定時、action pluginがローカル一時ファイル(`DEFAULT_LOCAL_TMP`)へ書き込み→`atomic_move`が`os.rename()`を試み、失敗時(EXDEV等)のみ`tempfile.mkstemp(dir=宛先ディレクトリ, prefix=b'.ansible_tmp', suffix=宛先basename)`→最終`os.rename()`にフォールバックする。フォールバック経路でも最終配置は宛先ディレクトリ内での`rename`のため常にatomic。
2. 上記フォールバック時の残骸ファイル名(`.ansible_tmp<random><id>.json`)が`glob.glob('*.json')`にマッチしないこと(先頭ドットのため)をPythonで実測した。
3. `set_fact`の兄弟キー相互不可視、および`{% set %}`によるlookup単一評価の主張を、独立の検証playbookで実測した(カウンタファイルで呼び出し回数を計測)。
4. footerの欠陥シナリオ(「後段taskが失敗してrescueへ落ちても`_capture_ctx`が定義済みのまま残る」)を、capture.ymlと同形の検証playbookで再現し、footerにID文字列が出る一方でディスク上にレコードファイルが存在しないことを実測で確認した。
5. `community.general.slack`モジュール(`plugins/modules/slack.py`)を読み、`attachment_keys_to_escape`に`footer`が含まれないこと(実装記録の主張どおり)を確認した。
6. `playbooks/recovery_probe_notify.yml`を実装記録と同一コマンド(`tester_mode=true`、`capture_spool_dir`をscratchpad配下に向ける)で実行し、W0ベースラインとのパリティ(`rc=0 / ok=7 / changed=0 / failed=0 / skipped=5 / rescued=0 / ignored=0`)を独立に再現した。生成されたspoolレコードのJSON内容も確認した。

いずれも実装記録の主張と一致した。以下、重大度別にfindingsを示す。

## Critical Issues

なし。ADR-004の不変条件(`when:`なし、block/rescue隔離、rescueはdebug 1つ、全taskに`delegate_to: localhost`+`become: false`+`changed_when: false`、`check_mode: false`を付けない、拡張子`.json`のみ)はすべて維持されていることを確認した。W0ベースラインとのパリティも独立に再現できた。`mv`削除によるatomicity/AC6の懸念も、ソース読解と実測の両方で裏付けが取れた。

## 重点1についての判断(footerが実在しないレコードを指しうる問題)

**結論: このスコープでは受け入れてよいが、"既知の限界"のまま放置せず、最も安い形で今回のうちに閉じるべきである。** 理由と対処案は以下。

### 再現条件と影響

`capture.yml`のtask1(`set_fact: _capture_ctx`)が成功し、task2(ディレクトリ作成)またはtask3(書き込み)が失敗する場合。上記の検証(方法4)で実際に再現した — `_capture_ctx.id`は定義済みのままfooterに表示されるが、対応するレコードファイルはディスク上に存在しない。

R6の目的(「通知を終点でなく入口にする」)にとって、このケースで人がSlackのfooterから存在しないIDを`recovery.io`へ渡す事態は、目的を否定する。requirementで最重要とされる「動いたことと結果を区別しない」欠陥クラスに正確に一致する。

### 最も安い直し方

ADR-004(b-1)は「rescueは`debug` 1つのみ」という不変条件を課しており、これは変えるべきではない(理由: rescue自体の複雑化はAC4のリスクを増やす方向であり、この不変条件はここまでのW0〜W5全体で堅持されてきた)。したがって**rescue側で`_capture_ctx`を後始末する案は不変条件と衝突するため採らない**。

代わりに、**「footerが参照する事実の確定を、書き込み成功後まで遅らせる」**のが最も安い。具体的には:

- block内に4つ目のtaskを追加する: `Confirm capture write succeeded`(`set_fact: _capture_written_id: "{{ _capture_ctx.id }}"`、`delegate_to: localhost` / `become: false` / `changed_when: false`)。task3(書き込み)の**直後**に置く。
- `notify.yml`のfooter式を`_capture_ctx.id`から`_capture_written_id`に差し替える: `{{ 'capture: ' ~ _capture_written_id if _capture_written_id is defined else '' }}`。
- rescueが発火した場合(task1〜3のどこで失敗しても)、この4つ目のtaskには到達しないため`_capture_written_id`は未定義のままとなり、footerは自動的に`''`へ縮退する。rescue自体は無改修(不変条件を壊さない)。

このコストは正常系のtask数が4→5に戻る(AC8の測定は「閾値は設けず実測値でCoordinatorが判断する」としており、4→5はハードな基準を破らない)。task数削減の目標(AC8)と、R6の目的(footerが常に実在のレコードを指す)は、この1task追加で両立できる。**Coordinatorはこの案の採否を判断すること。** 採らない場合も、「footerが指すIDが必ずしも実在しない」という制約をrequirement文書(またはコメント)に明記し、"既知の限界"として一過性の実装記録だけに留めないことを推奨する(実装記録には既に書かれているが、requirement/ADR側には未反映)。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `roles/common_slack/tasks/capture.yml` | コメントブロック(旧`slack_title`/`slack_message`等の行) | フィールド一覧コメントの`slack_title`/`slack_message`/`tester_mode`/`skip_notifications`/`check_mode`行でインデント幅が1桁分ズレている(diffに現れる空白のみの変更)。可読性への実害は小さいが、次にこのコメントを触る人が意図的な調整と誤解しないよう、一括で列を揃えるとよい | Style |
| 2 | `roles/common_slack/tasks/capture.yml` | コメント末尾(`_capture_ctx`の説明) | footerの限界(「実在しないレコードを指しうる」)は実装記録(`012_w6_implement.md`)にのみ書かれており、`capture.yml`自身のコメントには明記されていない。将来この不変条件を知らずに触る実装者のために、コメント側にも1〜2行残すことを勧める | Documentation |

## What Looks Good

- **ADR-004の不変条件**: `when:`なし、block/rescue隔離、rescueは`debug`1つ、全taskの`delegate_to: localhost`/`become: false`/`changed_when: false`、`check_mode: false`未設定、拡張子`.json`のみ — すべて現物で確認した。既存の`notify.yml`側の行は`footer:`追加の1行以外無変更。
- **`mv`削除の安全性**: `copy`のatomicityはソース読解と実測の両方で裏付けられた。フォールバック経路の残骸ファイルも`glob('*.json')`に一致しないこと(先頭ドット)を確認しており、実装記録が言及していない追加の安全マージンも確認できた。
- **`{% set %}`によるlookup単一評価の技法**: 独立実測でlookup呼び出しが1回であることを確認した。可読性は1つのJinja式に複数のローカル変数を詰め込む分やや読みにくくなるが、コメントで技法の理由と検証方法が明記されており、次にこのファイルを触る人が同じ罠(sibling keyの相互不可視、`vars:`の複数回評価)を再び踏む可能性は低い。
- **W0ベースラインとのパリティ**: 独立実行で`rc=0 / ok=7(+4) / changed=0 / failed=0 / skipped=5 / rescued=0 / ignored=0`を再現した。実装記録の主張(`ok=3→7`)と一致。
- **footerのエスケープ**: `community.general.slack`のソースで`footer`キーがエスケープ対象外(かつ意図的にエスケープ不要な固定文字列+ID)であることを確認した。注入面の懸念はない。

## 未確認事項

- **重点6(footerが空文字列のときのSlack表示)**: コードからは判断できない。`community.general.slack`は`footer: ""`をそのままpayloadへ転記する(確認済み)が、Slack側が空文字列のfooterをどう描画するか(何も表示しない/空行が出る等)は実際のSlack配信でしか確認できない。全38経路の通知に影響するため、Testerによる実配信での視覚確認(1回でよい)を推奨する。blockingにはしない — 最悪でも見た目の劣化であり、R3(観測が被観測を壊さない)には抵触しない。
- **`+R`工程としての重複確認**: `duplication-reuse-check`はTech Leadが指定した既存資産との照合を軽量に行うものだが、W6はTech Lead不在のため照合対象の指定がない。この観点でのfindingsは成立しない旨を明記する。
- **`roles/incident_capture/`側のフィールド追加(`id`)の扱い**: `capture.yml`のコメントには「`REQUIRED_SPOOL_FIELDS`は意図的に未変更」とあるが、収集器コード自体はレビューB(担当外)の範囲のため、このレビューでは実物を確認していない。

## Verdict

**Needs Discussion.**

理由: ブロッキングな欠陥はないが、「重点1」で指摘したfooterの整合性問題はR6の目的そのものに関わる設計判断であり、Reviewerの権限で採否を決められない(このW6は`+R`相当の経路でCoordinatorが実装者を兼ねるため、返却先はCoordinator)。上記の4taskへの追加案(task数4→5)を採用するか、既知の限界として明示的に受け入れて文書へ反映するかをCoordinatorが判断すること。それ以外の指摘はSuggestionレベルであり、この判断と独立にApprove相当で問題ない。
