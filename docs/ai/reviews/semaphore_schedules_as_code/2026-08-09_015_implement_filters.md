# implement: semaphore_schedules フィルタプラグインと単体テスト

作成日: 2026-08-09 / 作成: Implementer(filter plugin + 単体テストのみ担当)

## 1. 担当範囲

`docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md` の確定済みインターフェース契約に基づき、純ロジック(filter plugin)と単体テストのみを実装した。Ansible の task 側(`roles/semaphore_templates/tasks/*.yml`、`defaults/main.yml` へのカタログ追加)は対象外で、一切触れていない。

## 2. 成果物

| パス | 内容 |
|---|---|
| `roles/semaphore_templates/filter_plugins/semaphore_schedules.py`(新規) | 契約の8関数 + 独立レビュー(`2026-08-09_017_review_implementation.md`)High #2 で追加指示された `semaphore_schedules_nonmanaged_diff` の計9関数を実装し、すべて `FilterModule` へ登録 |
| `scripts/tests/semaphore_schedules/`(新規) | `_path_setup.py` / `_fixtures.py` / `run-tests.py` / `test_cron.py` / `test_preflight.py` / `test_desired_and_diff.py` / `test_payload_and_verify.py` / `test_activation_gate.py` / `test_strict_equal.py` / `test_nonmanaged_diff.py`。計92テスト |
| 本ファイル | implement記録 |

## 3. 契約の充足状況

8関数を requirement の表のとおりの引数順・戻り値キーで実装し、独立レビュー High #2 の指示で `semaphore_schedules_nonmanaged_diff` を1つ追加した(引数・戻り値キーは元の8関数とも無変更)。

- **`semaphore_schedules_preflight`**: R9の①〜⑦を、互いに独立したループとして実装(1つの検査の失敗が他の検査を止めない)。⑥はフェーズで分岐(移行期間=カタログ名がAPI側に実在するか、closed-world=`unmanaged`が0件か)。`unmanaged`はフェーズに関わらず常に計算し、closed-worldのときだけそれを`errors`へも上げる。
- **`semaphore_schedules_desired`**: R8-2のとおり、`name`/`cron_format`/`task_params`は常にカタログ値、`template_id`は引数の解決済みid。`active`はstage別 — stage1は新規なら`False`(R13)、既存はカタログ`False`なら即時無効化、それ以外は観測値を保持(有効化しない)。stage2は常に`True`(R12の再確認は呼び出し側の責務であり、この関数はそれを検査しない、という契約の読み方をコード上のdocstringに明記した)。
- **`semaphore_schedules_diff`**: `stage1`は「管理4項目の差分、または即時無効化」を`before`(単一GET由来)と`after`(stage1のdesired)の比較だけで導出できた — desiredの設計自体が有効化を含まないため、別枝を書かずに済んでいる。`pending_activation`は`stage1`/`unchanged`と独立な集合(両方に同時に載るケースをテストで確認済み)。
- **`semaphore_schedules_payload`**: 単一GETの`dict()`浅いコピーへ管理5項目だけ上書き。非管理フィールドは元オブジェクトの参照のまま(変異なし)。
- **`semaphore_schedules_create_payload`**: `desired`の5項目 + `project_id`。
- **`semaphore_schedules_verify`** / **`semaphore_schedules_stage2_precheck`**: 管理5項目を厳密一致で比較。**非管理フィールドは意図的にこの2関数の対象外**(AC4/AC17の非管理フィールド保持確認は`semaphore_schedules_nonmanaged_diff`が担う。下記参照)。
- **`semaphore_schedules_nonmanaged_diff`(新規、契約追加)**: `(before_raw, after_raw)` → 管理5項目**以外**で値が変わった/追加・消失したフィールド名のlist。比較は`verify`と同じ`_strict_equal`規律(型まで厳密)。PUT/POST直前・直後それぞれの単一GET rawをそのまま渡す想定で、task側からの呼び出し配線はもう一方のImplementerが行う。
- **`semaphore_schedules_activation_gate`**: R12の4条件+R15のURL allowlist+R16の集合比較を、5つとも独立に評価して`reasons`へ積む(短絡させない)。`allowed`は`reasons`が空のときだけ`True`。**`allow_flag`/`closed_world`は`isinstance(x, bool)`で型そのものを検査し、`bool`でなければ(文字列`"false"`/`"true"`、数値`0`/`1`、`None`等)真偽値としての評価を一切行わず、それ自体を不許可の理由にする**(下記参照)。

### `_strict_equal()`: 完全一致の判定方法(2026-08-09 差し戻しで修正)

R16-2「正規化された値…を一致として扱わない」を満たすため、`diff`のstage1判定・`verify`・`stage2_precheck`の3か所すべてで使う比較を素の`==`ではなく専用の`_strict_equal()`に通している。動機は、`bool`が`int`のサブクラスであるため素の`==`では `active: 1` と `active: True` が「一致」してしまうこと(AC21が検出を要求する「HTTP成功だが値が正規化/破棄された」ケースの一種)。

**最初の実装は `type(a) is type(b)` を全ての値へ課しており、これが壊れていた。** Coordinatorがansible-core 2.20.1に対して実測したところ、カタログ由来(YAML経由)の値は `_AnsibleTaggedStr`、`from_json`経由(API応答相当)の値は素の`str`というように、**同じ値・同じ意味でもJinjaを通ると型だけが変わる**ことが分かった(`_AnsibleLazyTemplateDict`も同様)。`type(a) is type(b)` はこの組を毎回不一致と誤判定し、`diff`のstage1・`verify`・`stage2_precheck`のすべてで実際には差分の無いスケジュールを「変更あり」「不一致」と報告してしまっていた。

**現在の実装は、数値(`bool`/`int`/`float`)だけ種別(`_numeric_kind`、isinstanceベース)の一致を要求し、それ以外の型(str/dict/list等)は素の`==`に委ねる**(dict/listは`_strict_equal`で再帰し、内部の数値leafも同じ規律で見る)。これにより、`1`と`True`の不一致は維持したまま、`_AnsibleTaggedStr`と素の`str`のような「同じ値の別クラス」を一致と判定できる。`scripts/tests/semaphore_schedules/test_strict_equal.py`で、str/dictのサブクラスによる再現(`_StrSubclass`/`_DictSubclass`、Ansibleをimportしない自前のスタブ)と、`diff`/`verify`/`stage2_precheck`それぞれを通した回帰テストを追加した。

### `semaphore_schedules_activation_gate()`: `allow_flag`/`closed_world`の型検証(2026-08-09 review Critical #1で修正)

修正前は `if not closed_world:` / `if not allow_flag:` という素の真偽評価だった。`ansible-playbook -e key=value` の値は常に文字列であるため、`-e semaphore_schedules_allow_activation=false` は非空文字列 `"false"` としてこの関数へ渡り、`if not "false"` は `False`(=否定条件を満たさない)になる — **意図と逆に「許可された」ものとして扱われる。** Coordinatorが実測で`allow_flag="false" closed_world="true"` → `allowed: True` を再現した。

修正後は、両引数へ `isinstance(x, bool)` を最初に課す。**`bool` 以外(文字列・数値・`None` 等)が来た場合は真偽値としての評価を一切行わず、それ自体を独立した不許可理由として`reasons`へ積む**(「型が違う」と「合法的にまだ許可されていない」を別の理由文言にして、呼び出し側が設定ミスを判別できるようにした — 緩めて通す方向では解決していない)。他4条件と同様、型エラーも短絡させず独立に評価する。`test_activation_gate.py::ActivationGateNonBoolTypeTests`にCoordinatorの実測ケースそのものと、数値`0`/`1`・`None`のケースを回帰テストとして追加した。**task側の入口でも別途型検証を入れるようもう一方のImplementerへ指示済み(Coordinator)** — この関数の検査は最後の砦であり、入口検証の代替ではない。

## 4. cron 妥当性検査の設計判断

requirementが明記するとおり、対象版(Semaphore 2.18.4)が実際に受理するgrammarは未実測(実測はTesterの役)。本実装は標準的な5フィールドcron(`*` / `N` / `N-M` / カンマリスト / `/step`、各フィールドの値域チェック)を受理し、パースできない・値域外のトークンは無条件でinvalid判定する(「判定できないものはerror側へ倒す」)。requirementが挙げた稼働中19件すべてを valid fixture として、既知の不正形(フィールド数違い・値域外・非数値トークン・名前付き曜日)を invalid fixture として `scripts/tests/semaphore_schedules/_fixtures.py` に固定した。**grammar自体の実測確定はtest_planへ引き継ぐ**(requirement §9の指示どおり)。

## 5. task_params の公開安全性検査(R9⑦)の設計判断

**旧実装(denylist)の欠陥(2026-08-09 review High #3で修正)。** 最初の実装は「秘密情報らしいキー名/値pattern・IPv4」に**一致したら拒否**するdenylist型で、一致しなければ無条件で通していた。これはR9⑦「判定できないときは停止する」の逆で、レビューは `environment='{"opaque":"not-classifiable-value"}'` のような**分類不能な値がpatternに一致しないという理由だけで素通りする**ことをローカル再現した。この修正でallowlist型(未知は拒否)へ切り替えた。

**allowlistがゴールを塞いだ欠陥(2026-08-09 同日、再度差し戻し)。** allowlist化した直後の版は、`task_params`のトップレベルキーを`environment`のみ・`environment`内の値をすべて`bool`/`int`/`float`(ネイティブ型)のみ許可していた。これはrequirement 6.5に書かれた3キー(`force_renew`/`dry_run`/`debug_level`)を書き写しただけで、**実データを1件も見ずに書いた仮説**だった。Coordinatorがansyの稼働中19件全件を単一GETで取得しこのpreflightへ通したところ、**19件中3件が誤って拒否された** — case のゴールである「19件すべてをカタログへ載せてclosed-worldへ到達する」を、この実装自身が塞いでいた。

**実測で判明し、requirement 6.5 に書かれていなかった事実(ここに記録する)。**

1. **`params` は実在するトップレベルキーである。** 19件中1件が使っている。6.5は「APIが受理しうる」としか書いておらず、実データで使われていることは未記録だった。
2. **`environment`(JSON文字列)をデコードした中の値は、`force_renew`/`dry_run`のような真偽値的なキーでも、ネイティブなJSON boolean ではなく文字列 `"true"`/`"false"` として格納されている。** 一方 `params`(こちらはJSON文字列ではなく、raw object上ですでにネイティブなdictとして格納されている)側の同名キーはネイティブ型(`4`、`false`)である。**同じ意味の値が、`environment`経由かどうかで型が変わる** — `environment`がSemaphoreの環境変数(OS環境変数はすべて文字列)に相当する保存形式であることが理由と推測されるが、Semaphore側の実装根拠までは確認していない。

実測された19件のtask_paramsは次の4形のみだった(`scripts/tests/semaphore_schedules/_fixtures.py`の`REAL_TASK_PARAMS_FIXTURES`に固定済み)。

```
16件  {"environment": "{}"}
 1件  {"environment": "{\"force_renew\":\"false\"}"}
 1件  {"environment": "{\"dry_run\":\"true\"}"}
 1件  {"environment": "{\"dry_run\":\"true\"}", "params": {"debug_level": 4, "dry_run": false}}
```

**現在の実装。** allowlistの形自体は変えず(未知は拒否のまま)、実測に基づいて中身を広げた。

- トップレベルキー: `environment` / `params` の2つ。
- 両方の内側で許可するキー: `force_renew` / `dry_run` / `debug_level` の3つ(変更なし)。
- 値の型: **`params`(ネイティブdict)側は`bool`/`int`/`float`のみ。`environment`(JSON文字列をデコードした側)は、`bool`/`int`/`float`に加えて文字列`"true"`/`"false"`(この2値のみの許可)も受理する。** それ以外の文字列(例: `"yes"`、`"4"`)や`dict`/`list`は、両方とも引き続き拒否。
- allowlistに載らないもの(未知のトップレベルキー、未知の内部キー、上記以外の値の形)はすべて拒否する、という判定方針そのものは変更していない。「未知のキー・未知の形は通さない」を維持したまま、実測済みの4形だけを通す。

**別roleのDLPエンジン(`roles/operator_request_channel/files/oprc/dlp.py`)は引き続きimportしていない** — 判断は変えていない(結合を追加するかは本タスクのスコープ外、requirementもそこまでは要求していない)。**「候補になった値そのものをfindingへ含めない」という同エンジンの規律は本モジュールでも明示的に踏襲している** — エラー文言には field/keyのパス(位置)と拒否理由の種別だけを出し、実際の値は一切含めない。実測された4形すべて(`test_all_4_real_observed_task_params_shapes_produce_no_error`)がエラーにならないこと、`params`側では同じキーでも文字列値が拒否されること(`environment`と`params`で許可される型が違うことの区別)、未知のキー・値・パース不能なJSONが引き続き拒否されること、拒否理由の文言に値そのものが含まれないこと、をそれぞれテストで確認した。

## 6. 自己検証

- `python3 scripts/tests/semaphore_schedules/run-tests.py -v` → **92 tests, OK**(全件成功)。
- ansyの実測19件が実際に持つ4種類の`task_params`形(`REAL_TASK_PARAMS_FIXTURES`)をpreflightへ通し、いずれもエラーにならないことを確認した(`test_all_4_real_observed_task_params_shapes_produce_no_error`)。あわせて`_task_params_public_problems()`を対話的に呼び、Coordinatorが提示した4形すべてが空リストを返すことも個別に確認した。
- `_strict_equal()` が、値が等しければ「YAML経由のstr/dictサブクラス」対「素のstr/dict」を一致と判定し、`bool`対`int`(`True`対`1`)は依然として不一致と判定することを、`_strict_equal`単体・`verify`・`stage2_precheck`・`diff`のstage1判定それぞれで確認した(`test_strict_equal.py`)。
- `python3 -m py_compile roles/semaphore_templates/filter_plugins/semaphore_schedules.py` → 構文エラー無し。
- `roles/semaphore_templates/filter_plugins/semaphore_schedules.py` の `import` 文は `collections.abc` / `json` / `re` / `urllib.parse` のみ(stdlib)。`ansible` を一切importしていないことを目視確認済み。
- `FilterModule().filters()` のキー集合が契約の8関数 + `semaphore_schedules_nonmanaged_diff` の計9関数名と完全一致することをPythonで実行確認済み。
- `task_params` の型保持: `environment` の値がJSON文字列のまま `desired` / `payload` / `diff` を往復すること(`isinstance(..., str)` と値の完全一致)を明示的にテストした(`test_desired_and_diff.py::test_task_params_environment_stays_a_json_string_not_reparsed`、`test_payload_and_verify.py::test_task_params_environment_stays_a_json_string_through_payload`)。
- `payload`が単一GETの全フィールドを含み非管理フィールドが観測値のまま残ることをテストで確認(`test_payload_and_verify.py::PayloadTests`)。
- `nonmanaged_diff`が管理5項目の変化を無視しつつ、非管理フィールドの変更・追加・消失を検出し、`verify`と同じ`_strict_equal`規律(`1`と`True`を別扱い)で比較することをテストで確認した(`test_nonmanaged_diff.py`)。
- `activation_gate`の①〜⑤それぞれの不許可と、全条件が揃った1通りだけが許可になることに加え、**`allow_flag`/`closed_world`が`bool`型でない場合(文字列`"false"`/`"true"`、数値`0`/`1`、`None`)にCoordinatorの実測ケースを含めて不許可になり、その理由が「型エラー」と「正当な不許可」とで異なる文言になる**ことをテストで確認した(`test_activation_gate.py::ActivationGateNonBoolTypeTests`)。
- `preflight`の7検査それぞれが、他の検査がすべて通っている状態で単独でerrorを出すことをテストで確認(`test_preflight.py::PreflightIsolationTests`、各テストで`len(errors)==1`を明示的に検証)。
- `task_params`のR9⑦検査が、allowlistに無い未知キー・未知の値型・パース不能なJSONをすべて拒否し(旧denylist実装がfail-openしていた`environment='{"opaque":"not-classifiable-value"}'`を含む)、かつ**その拒否理由の文言に候補値そのものが一切含まれない**ことをテストで確認した(`test_preflight.py::PreflightIsolationTests`の`task_params_*`系、それぞれ`assertNotIn`で値の非混入も検証)。

## 7. 到達していないこと(確認)

- Semaphore API(ansy/quory)への到達なし。ネットワーク呼び出しを一切行わないコードのみ。
- 実ホストへのansible実行なし(そもそも本実装はplaybook/task層を含まない)。
- 上記成果物3パス以外のリポジトリファイルを変更していない(`roles/semaphore_templates/`の既存ファイル、`defaults/main.yml`を含め無改変)。
- `git add` / `git commit` / `git push` は行っていない。

## 8. `.gitignore` の追跡対象問題(解決済み)

当初、`.gitignore` の `scripts/tests/*` allowlist(既存の否定パターンは `!scripts/tests/fixtures/` と `!scripts/tests/operator_request_channel/` の2つのみ)により、新規の `scripts/tests/semaphore_schedules/` が追跡対象にならないことをCoordinatorへエスカレーションした。`.gitignore` は本タスクの成果物3パスに含まれないため自分では変更していない。**この後、`.gitignore` に `!scripts/tests/semaphore_schedules/` が追加され(自分以外の変更)、現在は `git status` で当該ディレクトリが untracked として正しく見えることを確認した。** 対応不要。

## 9. 未解決事項 — 後続 Implementer(task側)への申し送り

- `semaphore_schedules_desired` の stage=2 は「呼び出し側がR12を再確認済みであること」を前提に無条件で `active: True` を返す設計にした。task側の実装で、R12再確認と `activation_gate` 呼び出しを経ていない経路からstage=2の `desired` を呼ばないこと。
- `create_payload` は R1/R8-2 の5項目 + `project_id` のみを組み立てる。単一GETに現れる他のフィールド(`repository_id`/`delete_after_run`/`type`等)をPOSTに含める必要があるかどうかは、実測(OQ7、6.5節)で確認されていない。POST時にAPIが必須とするフィールドが他にもある可能性があり、これは実際にPOSTを打つ側(Tester)が最初に踏むリスクとして残る。
- **新規 `semaphore_schedules_nonmanaged_diff(before_raw, after_raw)` の配線が必要。** AC4/AC17を満たすには、stage1/stage2いずれのPUT/POSTでも「直前の単一GET raw」と「直後の単一GET raw」の両方を保持し、この関数へ渡して結果が空リストであることを確認するtaskをtask側へ追加する必要がある(自分は追加していない — task層は対象外)。
- `semaphore_schedules_activation_gate` の`allow_flag`/`closed_world`型検証はこの関数内では最後の砦であり、**task側の入口(`-e`から受け取った値を`| bool`で正規化する等)でも別途の型検証が必要。Coordinator経由でもう一方のImplementerへ指示済み。**
