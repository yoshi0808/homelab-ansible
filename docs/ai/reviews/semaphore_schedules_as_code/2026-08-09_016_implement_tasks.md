# implement: semaphore schedule reconcile — task/catalog/playbook層

作成日: 2026-08-09 / 作成: Implementer(task・カタログ・playbook層。filter plugin/単体testは対象外)
改訂: 2026-08-09 — 独立レビュー`2026-08-09_017_review_implementation.md`の差し戻し(自分の担当範囲の指摘6件)を反映。節は積まず、内容を現状へ更新した。
改訂2: 2026-08-09 — 再査読`2026-08-09_019_review_implementation_r2.md`(前回7件はすべてclosed、`always:`化自体が生んだ新規回帰2件)を反映。節は積まず、内容を現状へ更新した。
改訂3: 2026-08-09 — 3回目の査読`2026-08-09_020_review_implementation_r3.md`(前回High #1はclosed、Medium #2が再指摘、extra-vars優先順位を突いた新規Highが1件)と、ansy実機でのTester結果`2026-08-09_022_test_result.md`(`reports_base_dir`権限問題)を反映。節は積まず、内容を現状へ更新した。
改訂4(最終): 2026-08-09 — 4回目の査読`2026-08-09_023_review_implementation_r4.md`(Medium #2・ansy report保存先はclosed、「schedule成功+report-only UNREACHABLE+report失敗factをnative falseで固定」という残り1枝がopen)を反映。節は積まず、内容を現状へ更新した。この改訂でCoordinatorから「これが通れば実装完了、commit提示へ移る」と伝えられている。

## 1. 担当範囲

`docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md`(正本)の確定済みインターフェース契約に基づき、Ansibleのtask・カタログ・playbook側を実装した。`roles/semaphore_templates/filter_plugins/semaphore_schedules.py`と`scripts/tests/semaphore_schedules/`は対象外で、一切変更していない(現物を読んで契約を確認した。もう一方のImplementerが並行してfilter側を修正しており、その差分は自分のものとして報告していない)。

## 2. 成果物

| パス | 内容 |
|---|---|
| `roles/semaphore_templates/tasks/schedules_validate_config.yml`(新規) | `semaphore_schedules_closed_world`/`semaphore_schedules_allow_activation`の入口型検証と正規化(査読Critical #2)。最初のtaskとして、`(_)?semaphore_schedules_*`という内部状態名が外部から事前定義されていないかを一括で拒否するreserved-name guardを追加(4回目査読Critical #1) |
| `roles/semaphore_templates/tasks/schedules_read.yml`(新規) | schedule一覧GET、template一覧のfresh GET(R10)、preflight時点idスナップショット |
| `roles/semaphore_templates/tasks/schedules_timezone_check.yml`(新規) | `GET /api/info`とcatalogの前提timezoneの照合(R11/AC10) |
| `roles/semaphore_templates/tasks/schedules_preflight.yml`(新規) | R9 7検査の呼び出しとfail-closed。template名解決エラーにはR10の2段階規約を名指しする補足を付ける(査読指摘6) |
| `roles/semaphore_templates/tasks/schedules_diff.yml`(新規) | 個別schedule detail取得、diff計算、stage1 desired状態の算出、apply outcome accumulator初期化、activationプレビュー |
| `roles/semaphore_templates/tasks/schedules_apply_new_item.yml`(新規) | 新規schedule作成(POST)+検証(R16-2) |
| `roles/semaphore_templates/tasks/schedules_apply_stage1_item.yml`(新規) | 既存schedule stage1 PUT(R8/R8-3)+identity check(R8)+PUT直前fresh GETからのdesired再計算(査読Critical #1)+検証(R16-2)+非管理フィールド保持検証(査読High #4) |
| `roles/semaphore_templates/tasks/schedules_apply_stage1.yml`(新規) | new/stage1の2ループを束ねる |
| `roles/semaphore_templates/tasks/schedules_apply_stage2_item.yml`(新規) | 有効化PUT(R8-3 stage2)+stage2_precheck+検証(R16-2)+非管理フィールド保持検証(査読High #4) |
| `roles/semaphore_templates/tasks/schedules_apply_stage2.yml`(新規) | R16 freshな集合再取得+activation_gate評価+stage2ループ |
| `roles/semaphore_templates/tasks/schedules_report.yml`(新規) | diff+outcomeレポートの保存(R19)。失敗経路でも安全な範囲で保存できるよう全参照を`default(...)`で防御(査読High #3)。failed*3事実は自分では計算せず、`main.yml`のrescueが作るscrub済みfactを読むだけに変更(再査読High #1)。report保存3taskに`ignore_unreachable: true`+`register:`を付け、UNREACHABLEでもrescueを介さず明示的に`semaphore_schedules_report_save_failed*`を記録する(3回目査読Medium #2) |
| `roles/semaphore_templates/tasks/main.yml`(既存へ配線) | template apply後にschedule系をnested block/rescue/alwaysで包んでimport(R10、査読High #3)。rescueはfailせずscrub済みfactを作るだけにし、レポート保存自体もさらに内側のblock/rescueで包んで、両方の失敗を保持したまま最後に1回だけ非ゼロで再送出する(再査読High #1/Medium #2)。最終再送出の`when:`を、外部から上書き可能な素のfactの真偽値だけに依存させず`ansible_failed_result is defined`とのORへ変更(3回目査読Critical #1) |
| `roles/semaphore_templates/defaults/main.yml`(既存へ追記) | scheduleカタログ3件、R17/R15/R11/R19の設定変数、`semaphore_target`によるapi_base_urlの導出。token_pathは両ホスト共通の単一絶対pathへ戻した(査読High #4/Critical#4、旧称)。`semaphore_templates_report_dir`/`semaphore_schedules_report_dir`もquory/ansyで分岐させ、ansy向けは`ann`が書き込めることを確認済みの`/home/ann/homelab-reports/...`へ(3回目査読・Tester実機`_022`) |
| `playbooks/semaphore_templates_setup.yml`(既存へ変更) | `hosts:`を`semaphore_target`から取得、未知値のfail-closed play新設、ansy向け使用例からtoken_path上書き例を削除 |
| `roles/semaphore_templates/tests/task_flow/fixture_pattern.yml`(新規) | `main.yml`のschedule block/rescue/alwaysの形(3・4回目査読での修正含む)を構造的に再現するfixture playbook。先頭にreserved-name guardの構造的な写しも追加(4回目査読テスト依頼) |
| `roles/semaphore_templates/tests/task_flow/run_task_flow_tests.py`(新規) | 上記fixtureを5シナリオ(token非漏えい/レポート保存失敗時の元失敗保持/native false extra-varでの再送出抑止不可/UNREACHABLEでも元失敗保持/schedule成功+report-only UNREACHABLE+report失敗factのnative false固定という複合exploitをreserved-name guardが事前に拒否)で駆動する自動テスト |
| 本ファイル | implement記録 |

## 3. 確定済み設計事項の実装

- **カタログ**: 要求どおりSAFE 3件を`name`/`template`の空白有無を実物どおり転記した。`task_params.environment`はJSON文字列`"{}"`(dictでない)。
- **設定変数**: `semaphore_schedules_closed_world`(既定false)/`semaphore_schedules_allow_activation`(既定false)/`semaphore_schedules_canonical_api_base_url`(quoryのリテラル、他変数から導出せず)/`semaphore_schedules_expected_timezone`(Asia/Tokyo)/`semaphore_schedules_report_dir`(`semaphore_templates_report_dir`とは別置き場)をすべて追加した。
- **実行先の切り替え(`semaphore_target`)**: playbookの`hosts:`は`"{{ semaphore_target | default('quory') }}"`。`semaphore_templates_api_base_url`の既定値は`{'quory': ..., 'ansy': ...}[semaphore_target | default('quory')]`という辞書添字式(quory向けの値は不変)、`-e`個別上書きは従来どおり効く。
  - **未知の`semaphore_target`のfail-closed**: Ansibleの既定挙動は「hostsパターンが1件も一致しないとき、WARNINGを出すだけでexit code 0のまま黙ってplayをskipする」ことを`--list-hosts`と実行の両方で実測確認した。この既定挙動のままでは要求(「未知の値は停止する」)を満たさないため、`hosts: localhost, connection: local`の前段playを新設し、`semaphore_target`が`groups['semaphore_servers']`に無ければ`ansible.builtin.fail`で停止する構成にした。実測でrc=2になることを確認済み。
  - api_base_urlの派生defaultsも未知の`semaphore_target`に対して二重にfail-closed — 辞書添字アクセスが存在しないキーで`jinja2.exceptions.UndefinedError`(`'dict object' has no attribute '...'`)を投げ、`defaults/main.yml`の該当行を指すエラーで停止することを実測確認した。
  - **`semaphore_templates_token_path`は`semaphore_target`から導出しない(2026-08-09、査読差し戻しHigh #4で撤回)。** 一度はansy向けに`~/.semaphore-api-token-ansy`を導出する案を実装したが、`~`の展開先が`become: true`下で曖昧なことと、`tasks/token.yml`のroot所有0600検査をこのファイルが通らないことの2点で「ansy/quory双方へ同じroleで反映する」というゴールを満たせなかった。**この解決はCoordinatorが環境側(ansy上にroot所有0600の実体を配置)で行う方向で調整中であり、コード側の所有権検査は緩めていない。** 既定値は両ホスト共通の単一絶対path(従来のquory向けの値)に戻した。ansyで別のtokenファイルを使いたい場合は`-e semaphore_templates_token_path=<root所有0600の絶対path>`で個別に上書きする。
  - **`semaphore_templates_report_dir`/`semaphore_schedules_report_dir`は`semaphore_target`で分岐させた(2026-08-09、3回目査読・Tester実機`_022`§1への対応)。** `reports_base_dir`の既定値(`/home/yoshi/homelab-ansible/reports`)は`yoshi:yoshi`所有・mode 0775で、ansyへSSH接続する`ansible_user`の`ann`(グループ外)からは書けないことをTesterが実機で発見した(template側のreport taskも同じ経路で全run停止)。**quory側の既定値(`reports_base_dir`基準)は変えていない。** ansy向けだけ`/home/ann/homelab-reports/...`へ切り替えた。**確認手段(実ホストへansibleを実行していない)**: このセッションはansy自身(`hostname`=ansy)の上で`yoshi`として動作しており、`ann`は同じマシンのローカルUnixユーザーである。`ansible-playbook`は使わず、素のシェル(`sudo -n -u ann mkdir/test -w/ファイル書き込み/rm -rf`という後始末込みの一連の操作)だけで、`/home/ann/`配下の新規ディレクトリを`ann`自身が作成・書き込み・削除できることを実測した。**ただしこれはこのマシン上のローカル権限の実測であり、SSH経由の接続そのもの(鍵・sshd設定等)や、Semaphoreが実際にどのcwd/checkoutから`ann`として実行するかは確認していない**(`ann`は`/home/yoshi`配下を辿れないため、Semaphoreの実行はこの作業ツリーとは別のcheckoutを使っているはずだが、その場所は未確認)。この点はTester/Coordinatorの範囲として残す。
- **設定フラグの型検証(2026-08-09、査読差し戻しCritical #2)**: `schedules_validate_config.yml`をschedule系の最初のtaskとして新設した。`-e semaphore_schedules_allow_activation=false`は文字列`"false"`として渡り、filter側の素朴な`if not allow_flag`評価がこれをtruthyとして通してしまう(Coordinator実測済みの欠陥)。task層では、値が①ネイティブ真偽値、②既知のtoken集合(`true/false/yes/no/on/off/1/0`、大小無視)のいずれかでなければ`ansible.builtin.fail`で停止し、該当すれば`| bool`で正規化する。
  - **正規化した値は元の変数名へ書き戻さず、`semaphore_schedules_closed_world_bool`/`semaphore_schedules_allow_activation_bool`という別名で持つ。** 元の変数名へ`set_fact`で書き戻す版を最初に実装したが、**`-e`(extra-vars)はAnsibleの変数優先順位で最上位であり、同名への`set_fact`はextra-vars経由の値を上書きできない**ことをmock APIサーバでの統合実行で発見した(`-e myflag=false`の後に`set_fact: myflag: "{{ myflag | bool }}"`をしても、以後`myflag`を読むと文字列`"false"`のまま`type_debug`が`str`を返すことをローカルdecoyで再現・確認済み)。これは「文字列`"false"`が有効化許可として扱われる」という元の欠陥を、正規化のつもりの実装がそのまま再現してしまう危険な落とし穴であり、mockでの統合実行が無ければ気付けなかった。以降、preflight・diffのactivationプレビュー・stage2の認可評価・stage1の分岐・レポート表示はすべて`_bool`suffix付きの新変数を参照する。
- **task順序**: `tasks/main.yml`で`apply.yml`(template側apply)の**後**にschedule系をimportした(R10)。読み取り系はcheck modeでも常に実行(`check_mode: false`をuriタスクへ個別付与)、書き込み(POST/PUT)を含む`schedules_apply_stage1.yml`/`schedules_apply_stage2.yml`だけを`when: not ansible_check_mode`でゲートした(R7)。
- **失敗経路でもレポートを保存する(2026-08-09、査読差し戻しHigh #3。再査読で2件の回帰を修正)**: schedule系全体を`block: [validate_config, read, timezone_check, preflight, diff, apply_stage1, apply_stage2] / rescue: [...] / always: [schedules_report.yml]`というnested block/rescue/alwaysで包んだ。`always:`はblockが成功した場合と、rescueが(自身failするか否かに関わらず)実行された場合のいずれでも走ることをローカルdecoyで実測確認した上で採用した。
  - **再査読High #1(トークンがscrubを経ずコンソール/レポートへ流れる)**: 初版のrescueは`ansible_failed_result.msg`をそのまま`ansible.builtin.fail`で再送出しており、この時点は外側(既存)のtoken scrubより手前だった。`schedules_report.yml`も同じ生メッセージを`failed_msg`としてmode 0644のJSONへ保存していた。**修正: rescueはこの場で`fail`せず、このrole既存のscrubパターン(`regex_replace`+`no_log: true`)で作った`semaphore_schedules_run_failed`/`_task`/`_msg`という3つのfactだけを残す。** `schedules_report.yml`はこのscrub済みfactを`default(...)`付きで読むだけに変更し、自分では`ansible_failed_result`を一切読まない。
  - **再査読Medium #2(レポート保存の失敗が元の失敗を置き換える)**: rescueがその場でfailし直後に`always:`のレポート保存が別の理由(ディスク容量・権限等)で失敗すると、外側から見える失敗情報がレポート保存の失敗だけになり、元のschedule失敗と既適用分のoutcomeが消える欠陥があった。**修正: `schedules_report.yml`のimport自体をさらに内側のblock/rescueで包み、保存失敗はその場でfailさせず`semaphore_schedules_report_save_failed`/`_msg`という独立したfactへ格納するだけに留める。** named blockの外(outer blockの兄弟task)に置いた最終taskが、`semaphore_schedules_run_failed`と`semaphore_schedules_report_save_failed`のどちらか一方または両方を見て、両方の内容を含めて非ゼロで`fail`する — 元の失敗が後発の失敗に上書きされない。
  - `schedules_report.yml`は、preflight失敗のように早期に止まった場合でも自分自身が未定義変数エラーで死なないよう、参照するすべての事実に`default(...)`を付けている。
  - **3回目査読Critical #1(内部の失敗fictがextra-varsのnative falseで上書きされ、失敗がrc 0になる)**: 上記2つのfact(`semaphore_schedules_run_failed`/`_report_save_failed`)は素の`set_fact`であり、`-e '{"semaphore_schedules_run_failed": false}'`のようなnative falseは`set_fact`より強い(Ansibleの変数優先順位でextra-varsは最上位)。scheduleの`task_params`がジョブ実行時に`-e`として渡る設計(実データで`Ubuntu vm full upgrade`の`environment`が`{"dry_run":"true"}`)のため、この2フラグの名前空間はscheduleの設定値と共有されており、外部からの上書きは机上の懸念ではない。Reviewerが同型fixtureでrc 0への吸収を実際に再現した。**修正(1段目): 最終再送出の`when:`を、フラグの真偽値だけでなく`(...) or (ansible_failed_result is defined)`とした。** `ansible_failed_result`はrescueが発火したときにansible-core自身が設定する特別変数であり、extra-varsで**値**を汚すことはできても(実測)、**存在の有無**(`is defined`)をfalseへ偽装することはできない(ローカルdecoyで`-e '{"ansible_failed_result": false}'`を渡しても`is defined`はtrueのまま残ることを確認済み)。
  - **3回目査読Medium #2(再指摘。レポート保存がUNREACHABLEになると集約へ到達しない)**: `ansible.builtin.block`の`rescue:`はUNREACHABLE(接続先でremote temp directoryが作れない等)を捕捉しない — 発生した瞬間にplay全体が即座に終了し、`rescue:`/`always:`のどちらにも到達しない。ローカルdecoy(`connection: local`+書き込み不可な`ansible_remote_tmp`)で、この状態を実測再現した上で対策した。**修正: `schedules_report.yml`の3つの保存task(ディレクトリ作成・保存・publish)へ`ignore_unreachable: true`+`register:`を付け、後続taskで`.unreachable`を明示的に判定し、`semaphore_schedules_report_save_failed`/`_msg`を直接`set_fact`する経路を追加した。** `ignore_unreachable: true`を付けるとUNREACHABLEでもplayが即死せず、同じblock内の後続taskへ進むことをローカルdecoyで確認済み(rescueは発火しない — それは元々「通常のFAILED」用の経路であり、UNREACHABLEは別経路として明示的に扱う)。
  - **4回目査読Critical #1(残り枝。schedule処理は成功しreport保存だけがUNREACHABLEになり、`semaphore_schedules_report_save_failed`をnative falseで固定される場合)**: この組合せでは`rescue`が一度も発火しないため`ansible_failed_result`は未定義のままであり、1段目の`(...) or (ansible_failed_result is defined)`という安全網も働かない — 最終再送出の3条件がすべてfalseになり、レポート未保存のままplayが成功で終わる。`register`した結果へ判定を差し替えても、registerされた変数もただの名前でありextra-varsに上書きされるため解決しない(Reviewer指摘)。**修正(2段目、最終形): 値ではなく「その名前が外部から事前定義されていること自体」を、schedule処理のtaskが1つも走る前に`schedules_validate_config.yml`の最初のtaskで拒否する。** extra-varsは定義済みの名前を未定義にはできないため、この向きの検査は上書きできない。**対象は指摘された2変数に限らず、この roleがschedule処理の内部状態として使う名前全体とした** — 個々の名前を手で列挙する代わりに、`lookup('varnames', '^_?semaphore_schedules_.*', wantlist=True)`(`vars`辞書直接参照はansible-core 2.20.1で非推奨警告が出るため、推奨されるlookup pluginを使う)で現在定義済みの該当prefix変数を列挙し、role defaultsが正当に持つ6つの設定変数(catalog/closed_world/allow_activation/canonical_api_base_url/expected_timezone/report_dir)だけをallowlistとして許可、それ以外が1件でもあれば停止する。**allowlist補集合という設計にしたことで、この先この役割に内部変数を追加しても、allowlistへ載せない限り自動的に保護される。** 検査自身のヘルパー変数名(`_reserved_name_guard_*`)は検査対象パターンに一致しない命名にし、自己参照でfalse positiveにならないことをローカルdecoyで確認した。
- **timezone照合(R11)**: 書き込みに使うのと同一の`semaphore_templates_api_base_url`に対し`GET /api/info`を発行し、`schedule_timezone`を`semaphore_schedules_expected_timezone`と照合、不一致ならfail-closed(AC10)。
- **preflight(R9)**: `semaphore_schedules_preflight`フィルタを呼び、`errors`が1件でもあれば`ansible.builtin.fail`で即停止。template名の解決件数エラー(③)が含まれる場合は、R10の「templateを先にapplyする2段階」運用制約を名指しする補足メッセージを追加する(2026-08-09、査読差し戻し指摘6。設計は変えず、メッセージだけを改善)。
- **diff/stage1/stage2の分離(R8/R8-2/R8-3)**: `schedules_diff.yml`で個別schedule detail(単一GET)を取得し`semaphore_schedules_diff`を呼ぶ。
  - **stage1のPUTは、PUT直前のfresh GETからdesiredを再計算してから送る(2026-08-09、査読差し戻しCritical #1)。** 以前の実装は`schedules_diff.yml`の早い時点のGETから算出した`item.after`をそのままPUTのdesiredとして使っており、直前fresh GETはidentity確認とmerge元にしか使っていなかった。カタログ`active: true`・早いGET`active: true`・cron差分ありのscheduleを、PUT直前にUIが`active: false`へ変えると、古い`active: true`が書き戻され、R12の4条件を経ずに再有効化される欠陥があった。修正後は、identity一致を確認した直後に`semaphore_schedules_desired(entry, フレッシュなdetail, template_id, 1)`でstage1 desiredを**その場で**再計算し、payload・直後検証・`semaphore_schedules_stage1_desired_by_id`(stage2 precheckが参照する検証済み状態)のすべてに、その再計算した値だけを一貫して使う。書き込みに成功したschedule idについては、`semaphore_schedules_stage1_desired_by_id`をその再計算値で**上書き**し、stage2 precheckが古い(pre-write)スナップショットを見ないようにした。
  - stage1は各PUT直前にfresh GETを取り直し(R8)、identityが変わっていればphaseで分岐(移行期間=skip・closed-world=`fail`で残り全件中止)。stage2は`schedules_apply_stage2.yml`がR16のfresh current_ids取得+`activation_gate`評価を行い、許可された場合のみ`schedules_apply_stage2_item.yml`を`pending_activation`へloopし、各アイテムで`stage2_precheck`を再確認する。
  - **非管理フィールドの保持検証(2026-08-09、査読差し戻しHigh #4)**: もう一方のImplementerがfilterへ追加した`semaphore_schedules_nonmanaged_diff(before_raw, after_raw)`(管理5項目以外で値が変わったフィールド名のlist)を、stage1・stage2それぞれのPUT直前raw/直後rawに対して呼び、非空なら`ansible.builtin.fail`で停止する呼び出しを両item fileへ追加した(AC4/AC17)。
- **abort-on-fail構造の実測**: `include_tasks`+`loop:`で、ループ内タスクが`fail`すると**それ以降のループ反復も、以後の全task importも実行されない**ことを、実ホストに触れないローカルdecoy loop(`/tmp`限定、SSH接続なし)で実測確認した(closed-world時の「残りのPOST/PUTを中止」がこの仕組みで成立する根拠)。
- **レポート(R19)**: `schedules_report.yml`は全schedule処理(stage1/stage2含む)の**後**、または失敗時は`always:`から実行し、diff・timezone情報・preflightのunmanaged・apply outcome(created/stage1_written/stage1_skipped/stage2_activated)・activation_gateの最終判定・(失敗時)失敗タスク名とメッセージを1つのJSONへまとめて`semaphore_schedules_report_dir`(templateの`latest.json`とは別ディレクトリ)へ保存する。--checkでも常に保存する(R7)。

## 4. 自己検証

### 4.1 実行したこと(初回実装分)

- `ansible-playbook playbooks/semaphore_templates_setup.yml --syntax-check`(既定/`-e semaphore_target=ansy`の両方) → rc=0。
- `python3 scripts/tests/semaphore_schedules/run-tests.py` → 全件OK(先行Implementerの単体testは無改変で引き続き全件通過)。
- `ansible-lint`を新規・変更ファイル全件に実行 → `name[template]`・`key-order[task]`・`yaml[line-length]`はすべて解消。動的include先(`--syntax-check`が中身を検証しないファイル)にYAML構文エラー(`name:`末尾の裸コロン)を1件発見・修正した。
- `hosts:`切り替えの実測: `--list-hosts`と実行の両方で、既定(`quory`)・`-e semaphore_target=ansy`・未知の値の3パターンを確認した。未知の値はrc=2で明示的に停止することを確認(4.2詳細)。
- 派生defaults(`semaphore_templates_api_base_url`)の値と型を、`include_role: tasks_from: noop, public: true`(ネットワーク到達なし)で`quory`/`ansy`/未知の3パターンとも確認した。`task_params.environment`が`str`型であることも`type_debug`で確認した。

### 4.2 `hosts:`未知値のfail-closed実測(抜粋)

```
$ ansible-playbook playbooks/semaphore_templates_setup.yml -e semaphore_target=totally_bogus_host
...
fatal: [localhost]: FAILED! => {"msg": "semaphore_target=totally_bogus_host は inventoryの
semaphore_servers グループに存在しないホスト名です (既知の値: ansy, quory)。..."}
rc=2
```

Ansibleの既定挙動(`--list-hosts`で確認): 未一致のhostパターンは`[WARNING]: Could not match supplied host pattern, ignoring: ...`を出すだけでexit code 0のまま`skipping: no hosts matched`となる。この既定挙動に頼らず明示のfail-closed playを前段へ置いたのは、この実測結果に基づく。

### 4.3 動的includeのYAML構文エラーを1件発見・修正

`--syntax-check`は`import_tasks`(静的)は検証するが、動的`include_tasks`先の中身までは検証しない(`skills/ansible-implementation-style/SKILL.md`「動的includeは静的検査も実行時のrescueも届かない」)。全新規ファイルを`python3 -c "yaml.safe_load(...)"`で個別に構文確認する運用に切り替えた。

### 4.4 var-naming[no-role-prefix]についての判断

`ansible-lint`は本roleのディレクトリ名(`semaphore_templates`)から、全変数が`semaphore_templates_`prefixを持つべきと推定し、schedule関連の新変数(`semaphore_schedules_*`、現在52箇所)をすべて指摘する。**これは意図的に受け入れた**:

1. カタログ変数名・5設定変数名は、Coordinatorの依頼文で名前そのものが明示指定されている。
2. filter plugin(変更禁止)は既に8関数すべてを`semaphore_schedules_*`という名前で確立している。
3. 1と2に合わせ、task層で新設した内部変数も同じprefixへ統一した — 一貫性を欠き誤読を招く混在を避けた。

### 4.5 モックSemaphore APIサーバによる統合実行(2026-08-09、査読差し戻し後に追加)

初回実装時は、後述する`_strict_equal()`の欠陥(§5、当時ブロッキング)のため、実際にPOST/PUTが発生する経路の実行を意図的に避けていた。査読差し戻しへの対応で、もう一方のImplementerが`_strict_equal()`を修正したこと、および`semaphore_schedules_nonmanaged_diff`を追加したことを踏まえ、**モックAPIサーバをtemplate用のPOST/PUT/GET(id別)にも対応させ、実際に書き込みが発生するapply mode(`--check`なし)を含めて再検証した。** 引き続き実ホスト・実IPには一切到達していない(接続先はすべてループバック、`hosts: localhost, connection: local`)。

確認できたこと:

- **Critical #2の修正確認**: `-e semaphore_schedules_closed_world=bogus`は`schedules_validate_config.yml`で明示的に`fail`し(rc=2)、レポートにも`failed: true`として記録される。`-e semaphore_schedules_closed_world=true -e semaphore_schedules_allow_activation=false`(いずれも文字列)は、activation_gateの`reasons`に「有効化が実行ごとに明示許可されていない(R12条件3)」という**正しい**理由が出ることを確認した(修正前は`_bool`変数を導入する前の版で、extra-vars優先順位の問題により文字列のまま`_AnsibleTaggedStr`としてfilterへ渡り、filter側の型検査に別の理由で弾かれることを発見 → `_bool`別名への変更で解消したことも確認済み)。
- **Critical #1の修正確認 / AC5(冪等性)**: migration phaseでcatalogと完全一致するschedule 3件(過去のtask_paramsに余分なキーが無い状態)に対し実apply(`--check`なし)を実行 → rc=0、「第1段階 更新: 3件(書込=3件、見送り=0件)」。**直後にもう一度同じコマンドを再実行** → rc=0、「無変更: 3件」「第1段階 更新: 0件」となり、冪等性を確認した。
- **stage2有効化フロー**: closed-world・`allow_activation=true`・管理外0件・canonical URL一致の条件で、API側`active=false`・catalog`active=true`のschedule 1件を含む状態でapply → rc=0、「有効化待ち: 1件(有効化済み=1件)」。**直後に再実行** → rc=0、「有効化待ち: 0件」となり、こちらも冪等性を確認した。
- **High #3の修正確認**: `-e semaphore_schedules_closed_world=bogus`での失敗時、コンソールに`Save the schedules diff/outcome report`と`Publish the latest schedules report under a stable name`が`changed`として現れ(=`always:`が実行された)、保存された`latest.json`が`"failed": true`と失敗タスク名・メッセージを含むことをファイル内容で確認した。real apply(`--check`なし)での別の失敗(template側の名前重複)でも同じ挙動を確認した。
- **High #4(呼び出し側)の疎通確認**: `semaphore_schedules_nonmanaged_diff`がfilter側へ追加された後の3.のstage1書き込みで、非管理フィールド不一致の`fail`タスクが`skipping`(=条件不成立、非管理フィールドは保持されていた)として通過することを確認した — 呼び出し自体がエラーなく評価され、意図した分岐(不一致0件で発火しない)が成立することを確認した。**意図的に非管理フィールドを壊すシナリオ(fail発火の確認)はmockのPUTハンドラが単純な上書きのため作り込んでおらず、今回は行っていない。**
- **指摘6(R10メッセージ)の確認**: 新しいtemplateを含む変更をtemplate側apply前にschedule preflightへ到達させると、エラーメッセージに「このうちtemplate名の解決件数エラーは、新規templateをこの変更で追加した場合に起こりえます。R10は…」という補足が実際に付くことを確認した。

### 4.6 task層のnested block/rescue/always自動テスト(2026-08-09、再査読差し戻し指摘3、3回目査読テスト依頼への対応)

filterの92単体testは`main.yml`のnested rescue/alwaysを一度も通らない(pure Pythonでansible runtimeを介さない)ため、`roles/semaphore_templates/tests/task_flow/`を新設した(`scripts/tests/semaphore_schedules/`は先行Implementer所有のため触れていない。`.gitignore`の許可リスト問題も、この新パス`roles/semaphore_templates/tests/`は対象外であることを`git check-ignore`で確認済み)。

- `fixture_pattern.yml`: `main.yml`のschedule block/rescue/alwaysと**構造的に同一の形**(3・4回目査読の修正を含む — 先頭にreserved-name guard → block内でno_logタスクが失敗(`fixture_should_fail`で成功に切替可能) → rescueはfailせずscrub済みfactだけを作る → alwaysはレポート保存をさらに内側のblock/rescueで包み、保存task自体には`ignore_unreachable: true`+`register:`を付けてUNREACHABLEを明示的に検出、FAILEDは内側rescueが、UNREACHABLEはその後続taskが、それぞれ別factへ分離 → named blockの外の最終taskが`ansible_failed_result is defined`とのORで非ゼロ再送出)を持つ、実ホスト・実APIに触れないfixture。
- `run_task_flow_tests.py`: このfixtureを5シナリオで駆動する。A: レポート保存が成功する場合(sentinel非漏えい)。B: `chmod`でレポート保存を意図的にFAILEDにする場合(元failureの保持)。C: `-e '{"fixture_run_failed": false}'`(native false)で内部factを外部から固定しても、rcが必ず非ゼロになること(3回目査読Critical #1)。D: `ansible_remote_tmp`を書き込み不可pathへ向けてレポート保存をUNREACHABLEにしても、元failureの識別情報が残ること(3回目査読Medium #2再指摘)。E: `fixture_should_fail=false`(block自体は成功)+report-onlyのUNREACHABLE+`-e '{"fixture_report_save_failed": false}'`という4回目査読の複合exploitで、reserved-name guard自身の停止メッセージが(block/report-writeより先に)出て非ゼロになること。5シナリオとも3回連続実行して安定を確認した。

**実装中に発見した事実(修正はしていない、Ansible-core自体の挙動)**: ansible-core 2.20.1は、`no_log: true`を付けたtaskが失敗しても、`[ERROR]: Task failed: ...`という診断バナーに**そのtaskの生の`msg`をそのまま表示する**(`fatal: ... => {"censored": ...}`という後続のJSON dumpだけがno_logで隠される)。`ansible.builtin.fail`・`ansible.builtin.uri`の両方で、rescueを介さない最小構成で再現・確認した。これは**rescueが始まる前に**表示されるため、どのようなrescue側のscrubでも防げない。ただし、この役割の実際の`uri`タスクの失敗メッセージ("Status code was N and not [...]: HTTP Error N: <reason>")はAuthorizationヘッダ値もレスポンス本文も含まないことを同じ実測で確認しており、**現状のtask構成でこの経路が実際にtokenを漏らすことはない**(role既存ヘッダコメントの「通常想定しにくいが万一」という記述と整合する)。テストはこの事実を踏まえ、「rescue以降(このroleのコードが制御できる範囲)でsentinelが再度現れないこと」をassertし、rescue開始前のバナー自体は対象外とした — この境界と理由をtest自身のdocstringに明記した。

### 4.7 ansy向けreport_dirの検証(2026-08-09、3回目査読・Tester実機`_022`§1への対応)

`include_role: tasks_from: noop, public: true`(ネットワーク到達なし)で、`semaphore_target=quory`(既定)/`ansy`双方の`semaphore_templates_report_dir`/`semaphore_schedules_report_dir`の解決値を確認した — quoryは従来どおり`/home/yoshi/homelab-ansible/reports/...`のまま、ansyは新しい`/home/ann/homelab-reports/...`。

`ann`が実際にこの新しいpathを書き込めることは、`ansible-playbook`を使わない素のシェル操作(`sudo -n -u ann mkdir -p .../semaphore-schedules && sudo -n -u ann test -w ... && sudo -n -u ann bash -c 'echo test > ...' && sudo -n -u ann rm -rf ...`)で実測した(このセッションがansy自身の上で`yoshi`として動いており、`ann`は同じマシンのローカルUnixユーザーであるため可能だった)。

**行って無効化した誤った検証方法**: 当初、実際のschedule roleをmockサーバ相手に`sudo -u ann ansible-playbook ...`として動かし、report書き込みまでエンドツーエンドで確認しようとしたが、`ann`がこの作業ツリー(`/home/yoshi/homelab-ansible`、および親の`/home/yoshi`)自体を辿れない(`sudo -n -u ann test -x /home/yoshi` が失敗)ことが分かり、この試みは無効だった。**これはこの検証手法自体の限界であり、私の変更した`report_dir`とは無関係** — `ann`がこのcwd配下にアクセスできないという事実は、Semaphoreの実行が別のcheckout場所を使っていることを示唆するが、その場所は未確認のままCoordinator/Testerへ委ねる。テスト後、`/home/ann/homelab-reports`は削除済み(状態を残していない)。

### 4.8 reserved-name guardの直接検証(2026-08-09、4回目査読Critical #1への対応)

`schedules_validate_config.yml`単体を、`include_role: tasks_from: noop, public: true`(role defaultsのみロード、ネットワーク到達なし)の直後に`include_tasks`で直接実行し、以下を確認した。

- **クリーンな実行**(外部からの事前定義なし): guardは`skipping`(条件不成立)で通過し、以降の型検証・正規化も通常どおり動く。role defaultsが持つ6変数だけが検出され、それ以外は0件であることを`lookup('varnames', ...)`の出力で直接確認した。
- **攻撃再現1**: `-e '{"semaphore_schedules_report_save_failed": false}'` → guardが`semaphore_schedules_report_save_failed`を名指しして`fail`、rc=2。
- **攻撃再現2**: `-e '{"semaphore_schedules_run_failed": false}'` → 同様にrc=2。
- **攻撃再現3**: `-e '{"_semaphore_schedules_stage1_identity_ok": true}'`(stage1のidentity確認をbypassしようとする、下線始まりの内部専用名)→ 同様にrc=2。パターンが`(_)?semaphore_schedules_`の両方を拾うことを確認した。
- **正当な上書きは通す**: `-e semaphore_schedules_closed_world=true`(allowlist内の6変数の1つ)は guardを通過し、後続の型検証・正規化どおりに動作する。

`roles/semaphore_templates/tests/task_flow/fixture_pattern.yml`にも同じ設計のguardを追加し、scenario Eとして同じ攻撃パターン(schedule処理は成功・report-onlyのUNREACHABLE・report失敗factのnative false固定)を再現、guard自身のメッセージがblock/report-writeより先に出て停止することを確認した(§4.6参照)。

## 5. 発見していた問題(解決済み) — filter plugin `_strict_equal()` とAnsible-core 2.20のData Taggingの衝突

**初回実装時にブロッキングとして報告した欠陥。もう一方のImplementerがfilter plugin側(`_strict_equal()`)を修正し、§4.5の統合実行で解決を確認した。** 経緯を残す。

`_strict_equal()`の初版は`type(a) is type(b) and a == b`という厳密比較を全型に適用していたため、YAML(catalog)由来の文字列(`_AnsibleTaggedStr`)とAPI JSON由来の文字列(素の`str`)が、内容が完全一致していても型不一致で「変更あり」と誤検出していた(2026-08-09、ローカルdecoy + mock APIサーバで実測・特定)。影響はAC5(冪等性)とR16-2(書き込み直後検証)のすべてに及び、apply系のACをすべて塞ぐ実害だった。

修正後の`_strict_equal()`は、数値種別(`bool`/`int`/`float`、`_numeric_kind`ヘルパーでisinstanceベースに判定)だけを型厳密にし、それ以外(str/dict/listを含む)はPythonの`==`(再帰的にMapping/list-likeへ適用)に委ねる設計になっている。§4.5で、この修正後の版に対しstage1の3件書き込み・2回目実行での冪等性・stage2の有効化と再冪等性を実測し、いずれも期待どおりであることを確認した。

## 6. 到達していないこと(確認)

- Semaphore API(ansy/quoryとも)への到達なし。自己検証で使ったmock APIサーバはループバック限定で、実ホスト・実IPには一切到達していない。
- 実ホストへのansible実行なし(`--check`を含め、`hosts: quory`/`hosts: ansy`向けの実行はしていない。mock実行はすべて`hosts: localhost, connection: local`)。
- `roles/semaphore_templates/filter_plugins/semaphore_schedules.py`と`scripts/tests/semaphore_schedules/`は無改変(現物を読み、契約を確認しただけ。§4.5の統合実行はもう一方のImplementerが着地させた版に対して行った)。
- 上記デリバラブルパス以外のリポジトリファイルは変更していない。
- token値はコンソール出力・レポート・本記録のいずれにも現れていない(全uriタスクに`no_log: true`を付与、既存の`main.yml`rescueのtoken scrub機構をschedule系にも共有)。
- `git add`/`git commit`/`git push`は行っていない。

## 7. 未解決事項

1. AC7〜AC10・AC13・AC16・AC18〜AC23個別など、§4.5で扱っていない個別fixtureでの実地検証は行っていない(mockでの確認は代表的な経路に留めた) — Testerが本来の役割として行う範囲。
2. 非管理フィールドが実際に壊れたときの`semaphore_schedules_nonmanaged_diff`側の`fail`発火そのものは、mockのPUTハンドラが単純上書きのため作り込んでおらず未確認 — 呼び出しが正しく配線され、不一致0件のときに正しく通過することは確認済み。
3. 先行Implementerの申し送り(`2026-08-09_015_implement_filters.md` §9)のうち、`create_payload`がPOST時にAPIが必須とする他のフィールド(`repository_id`等)を含めるべきかは未確認のまま — 実際にPOSTを打つ側(Tester)が最初に踏むリスクとして残る。
4. ansy向けtoken配置(査読High #4の環境側対応)はCoordinator調整中で、完了まではansyでのtoken読み取りがfail-closedする(意図した状態)。
5. **§4.6で発見した、ansible-core 2.20.1の`[ERROR]:`バナーが`no_log: true`を尊重しない挙動。** 現状のtask構成では実害が無いことを確認済みだが、これは`main.yml`の元々のtemplate側rescue(自分の変更対象外、2026-08-04時点で「実測確認済み」とコメントされている箇所)にも等しく当てはまる、rescueでは原理的に防げない特性であり、この案件のスコープを超える。Coordinatorが認識しておくべき事実として記録する — 対応の要否・対象は本件の範囲外の判断。
6. ~~残存する複合シナリオのリスク~~ **【解決済み、4回目査読への対応】** 3回目査読時点で残っていた「UNREACHABLEなreport保存」+「extra-varsでreport_save_failedを偽装」の複合は、4回目査読で実際に指摘・再現され(Critical #1)、§3「4回目査読Critical #1」「§4.8」のreserved-name guardで解決した。値の真偽値ではなく名前の事前定義自体を拒否する設計のため、この複合に限らずschedule処理の内部状態名全体を対象にしている。
7. ansy実行環境そのもの(Semaphore/`ann`が実際にどのcheckoutパスから実行するか)は未確認のまま(§4.7参照)。`ann`は`/home/yoshi`配下を辿れないため、この作業ツリーとは別の場所のはずだが、その場所・そこでの`ansible.cfg`/`roles_path`解決は未確認。
