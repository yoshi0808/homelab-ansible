# テスト結果: 書き込み経路の再検証(PUT / POST)

対象: `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md`(AC1〜AC23)、`_025_closeout.md`

**目的:** `_022`(SAFE 3件時点の検証)の後に5ラウンドの修正が入った現在のコードで、変更(PUT)・新規作成(POST)の2経路を実 API に対して再度通す。`_022`/`_025`の主張を現物で確かめずに引き継がない。

対象コマンド: `ansible-playbook playbooks/semaphore_templates_setup.yml -e semaphore_target=ansy`(必要に応じ `--check`)。commit `01a6f8e`(closed-world 化 + guard 修正後の HEAD)時点のコードで実施。

## 0. 実行環境

- ansy 上(`hostname`=ansy、`whoami`=yoshi)から `ansible-playbook` を実行。SSH接続先は `ansy.internal`、接続ユーザーは `ann`。
- `-e reports_base_dir=<scratchpad>/semtest-reports` を全実行に付与(`/home/yoshi/homelab-ansible/reports` へ `ann` が書けない既知の環境不具合。`_022` §1 と同一事象、再確認のみ行い repo・ansy の権限設定は変更していない)。
- 書き込みを伴う実行には `-e skip_notifications=true` を付与。
- API の直接読み取り・probe には自作 Python ヘルパー(`urllib`、`Authorization` ヘッダをトークンとして送るのみで出力しない。`-v`/`-i`/`--trace` 相当の機能は無い)を使用。scratchpad(`/tmp/claude-1000/.../scratchpad/`)配下にのみ保存し、リポジトリへは置いていない。
- DB read-only 照会は `sqlite3 /var/lib/semaphore/semaphore.db`(所有者 `yoshi:yoshi`、`SELECT` のみ実行)。
- ベースライン(実測、開始時点): project id=3、19件、id集合 `{8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26}`、全件 `active: false`、`schedule_timezone: Asia/Tokyo`、version `2.18.4-7ca373d-1779131064`。全19件の個別 GET を `baseline_detail/<id>.json` として保存し突合対象にした。カタログ側は `closed_world: true`(19件、管理外は前提として0件)。

## 1. 変更(stage 1 の PUT)の再検証

**対象: id21「SAFE: Time sync check」。**

1. 直接 API PUT で `cron_format` をカタログ値 `50 5 * * *` から `55 5 * * *` へ変更(probe)。
2. `--check` 実行 → rc=0、サマリ「第1段階 更新: 1件(書込=0件)」。実行後 GET で `cron_format` は probe 値のまま(未書込)であることを確認。
3. `--check` なしで apply → rc=0、サマリ「第1段階 更新: 1件(書込=1件)」。
4. apply 後の GET を `baseline_detail/21.json` と突合 → **完全一致**(`cron_format` がカタログ値へ復帰し、`id`/`project_id`/`template_id`/`active`/`type`/`delete_after_run`/`repository_id`/`task_params` を含む全フィールドが一致)。
5. 他18件についても apply 前後で個別 GET を突合し、**全件がベースラインと完全一致**(影響なし)を確認した。

**結果: PASS。** AC4/AC17(a)の主張を現行コードで再現できた。`_022` は SAFE 3件時点(5ラウンド前)の検証だったが、現在のコードでも同じ挙動が成立する。

## 2. 新規作成(POST)の再検証

**この経路は closeout(`_025`)時点で「一度も通っていない」とされていたが、`_022` の AC3/AC19(SAFE 3件段階)では実際に POST を発行し PASS していた。** 矛盾があるため、現在のコードで改めて実施した。closeout の「一度も通っていない」は本番(quory)側の事実であり、ansy 側の過去の検証結果と混同すべきでない旨、findings として下記4節に記録する。

**対象: id23「SEMI-SAFE:Ubuntu vm full upgrade(dry_run=true)」**(`task_params` が非空 `{"dry_run":"true"}` を持つエントリを選定)。

1. 直接 API `DELETE /project/3/schedules/23` → 19件→18件(id集合から23が消える)。
2. `--check` 実行 → rc=0、サマリ「新規作成: 1件(作成=0件)」。実行後 GET で件数18件のまま(書込なし)を確認。
3. `--check` なしで apply(`allow_activation` は既定 `false` のまま)→ rc=0、サマリ「新規作成: 1件(作成=1件、うち有効化待ち=1件)」。
4. 新規 id=**29** が作成された(元の23には戻らない。id はSemaphore採番のため許容範囲どおり)。GET で確認:
   - `name` = `"SEMI-SAFE:Ubuntu vm full upgrade(dry_run=true)"`(カタログ値と一致)
   - `template_id` = 68(削除前の id23 と同じ template へ正しく名前解決)
   - `cron_format` = `"15 18 2 * *"`(カタログ値と一致)
   - **`active` = `false`**(カタログ値は `true` だが、R13 どおり常に無効で作成)
   - `task_params` = `{"environment": "{\"dry_run\":\"true\"}"}`(カタログ値と完全一致)

**結果: PASS。** 未確認事項だった「新規作成時の必須フィールドが管理5項目 + `project_id` で足りるか」への答え: **足りる。POST は失敗せず、HTTP成功で意図どおりのオブジェクトが作られた。**

## 3. 削除後の復元(有効化に何が要るか)

id29(上記で復元された schedule)を使い、有効化条件を実地で確認した。

1. 復元直後の GET で `active: false` を確認済み(2節)。
2. `-e semaphore_schedules_allow_activation=true` を付けて `--check` 実行(**API を直接叩いての有効化は行わず、`--check` で書込ゼロのまま挙動だけを観測**)→ rc=0、サマリに「有効化待ち: 19件」「有効化許可: False」、理由に **「接続先 URL 'https://ansy.internal:3000/api' が canonical な本番 URL 'https://quory.internal:3000/api' と一致しない(R15 allowlist)」**が出力された。
3. `--check` のため書込は発生しておらず、`active` は `false` のまま。

**観測: 復元後の schedule は無効(`false`)で戻る。有効化には R12 の4条件(closed-world・管理外0件・実行ごとの明示許可・canonical URL 一致)がすべて要る。ansy では4条件目(canonical URL 一致)が構造的に満たせないため、`allow_activation=true` を渡しても有効化されない。** これは `_025` closeout §2 の記述(「ansyへapplyすると19件が有効化される」という事故想定に対して、実物で止まることを確認済み)と整合する再現であり、今回は削除→復元した schedule(id29)個別に対しても同じ歯止めが効くことを確認した。

**結果: PASS(観測どおり)。** 依頼にある「有効化するには何が要るかを実際の挙動として記録する」を満たした。

## 4. `task_params` の PUT が作る孤児行(DB read-only 照会)

**依頼の想定(requirement 6.5/R8 の記述: 「PUT は既存行を更新せず新しい行を作り、古い行を孤児にする」)と異なる結果を観測した。** 事実をそのまま記録する。

- 開始時点: `project__task_params` 総数22行、孤児(どの schedule からも参照されない行)3件(`id=7,26,27`。内容から見て過去のセッションの実験由来と推定され、私が作ったものではない)。
- **1節の PUT(id21、`cron_format` のみ差分、`task_params` 内容は不変)**: apply 前後で `project__task_params` の総数・孤児件数は変化なし(id21 の `task_params_id` は `20` のまま)。
- **`task_params` 自体に差分を作った追加実験**(id25「SAFE:Recovery monitoring check」の `task_params.environment` を probe で `"{}"` → `"{\"dry_run\":\"true\"}"` へ直接 API PUT、その後 apply でカタログ値 `"{}"` へ復帰): **両方の PUT とも、id25 の `task_params_id`(`24`)は変わらず、既存行が上書きされた。** 総数・孤児件数とも変化なし。
- **2節の POST(削除→新規作成)**: 新規行が1件作られた(`task_params_id=30`)。これは id29 から正しく参照されており孤児ではない。総数22→変化なし(削除された id23 の旧 `task_params` 行が孤児化する形では現れていない — DELETE で `task_params` 行が連鎖削除された可能性があるが、削除前の `task_params_id` を記録していないため未確認)。
- **冪等再実行**(全19件が catalog と一致する状態での再 apply): 総数・孤児件数とも変化なし(0書込)。

**結論(実測): 今回の一連の PUT(cron のみ差分・`task_params` 自体の差分の両方)では孤児行が新たに増えなかった。** `project__task_params` は `task_params_id` が既に非 NULL の schedule に対しては、内容が変わっても **同じ行を上書き**しており、新しい行を作っていない。**新しい行が作られたのは POST(新規作成)のときだけ**で、それは正しく参照されている(孤児ではない)。

**この結果は requirement 6.5/OQ8/R8 コメントが記す「差分のある PUT は新しい行を作り、古い行を孤児化する」という記述と食い違う。** 可能性としては、①元の測定時に対象 schedule の `task_params_id` が NULL だった(初回設定)のに対し、今回の対象は全件が既に非 NULL だった、②元の測定と今回とで Semaphore 側の挙動条件が異なる、のいずれかだが、**この差の原因は特定していない(未確認のまま Coordinator へ返す)**。孤児3件(id 7/26/27)は今回のどの操作でも増えておらず、由来は過去のセッションの実験と推定するに留まる(自分で作ったものではないため削除していない)。

## 5. ansy を戻したことの独立確認

全テスト終了後、`GET /project/3/schedules` と全19件の個別 GET を実施し、開始時に記録したベースライン(`baseline_detail/*.json`)と突合した。

- 件数: 19件(変化なし)。
- id集合: `{8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,24,25,26,29}`。**id23 だけが id29 へ変わっている**(2節の DELETE→POST 経路であり、依頼どおり id は元へ戻さず新しい id として記録)。他18件の id は不変。
- **id21・id25・id29 を除く16件**: `baseline_detail/<id>.json` との `diff` が空(全フィールド完全一致)。
- **id21・id25**: probe による一時変更後、apply で復帰し、`baseline_detail` と完全一致。
- **id29**: 新規作成だが、カタログ値(`name`/`template_id`/`cron_format`/`task_params`)は削除前の id23 のカタログ値と一致し、`active` は `false`(ベースラインの id23 も `false` だったので一致)。
- 全19件が `active: false`(有効化していない)。
- カタログとの差分: 最終 `--check` は既に1節末で `無変更: 19件`(2節・3節の作業後に改めて `--check` を実行し確認済み。以下「6. 最終状態の直接確認」参照)。
- `git status` はクリーン(リポジトリ内ファイルは1件も変更していない)。

## 6. 最終状態の直接確認(このファイル作成前の最後の実測)

```
mode : check (適用なし)
phase : closed-world
新規作成 : 0 件 / 第1段階 更新 : 0 件(書込=0件) / 無変更 : 19 件 / 管理外(削除しない) : 0 件
有効化待ち : 19 件(有効化済み=0件) / 有効化許可 : False
```

**カタログとの差分0件、書込0件、有効化0件でベースラインへ戻ったことを独立に確認した。**

## 7. 秘密情報・通知の確認

- scratchpad 配下の全ファイル(ヘルパースクリプト、probe/final JSON、`semtest-reports/`)を token 文字列で `grep` し、一致0件を確認した。
- `semtest-reports/` 配下を `slack` で大文字小文字無視 grep し、0件。
- API 直接確認はヘッダ・トレースを出力しない自作ヘルパーのみを使用し、`curl -v`/`-i`/`--trace` は使用していない。

## 8. 実装の不具合として Coordinator へ返すもの

- **§0 の `reports_base_dir` 権限問題(再確認)**: `_022` で報告済みの環境不具合(`ann` が `/home/yoshi/homelab-ansible/reports` へ書けない)が、現在のコードでも解消されていないことを確認した。新規の指摘ではない。
- **`_025` closeout の「新規作成の経路は一度も通っていない」という記述と、`_022` の AC3/AC19(実際に POST を発行し PASS)との整合性**: 両方の記録を読む限り矛盾はない — closeout は本番(quory)側で POST が発火していないことを述べており、`_022`/本記録は ansy 側の検証を述べている。ただし closeout 本文はこの区別を明記しておらず、読み手が「ansy でも一度も POST していない」と誤読しうる。**記録の書き方の問題であり、実装の不具合ではない**が、Coordinator の判断のために明記する。
- **孤児行の実測が requirement 6.5/OQ8/R8 の記述と食い違う**(4節)。実装のバグではなく DB挙動の観測結果の相違であり、**R8 の設計判断(get-then-merge-then-send で全フィールドを送り返す)自体の正しさには影響しない**(4節の全ケースで `task_params` の内容自体はカタログ値と正しく一致していた)。ただし、6.5節・OQ8・R8コメントの記述を「孤児行が新しいPUTのたびに増える」という前提で運用判断(掃除の要否など)に使う場合は、この食い違いを踏まえて再検証することを勧める。
- 実装コード自体(filter plugin・task層)には、今回の PUT/POST/DB照会の範囲で新規の不具合を見つけていない。

## 9. 残存リスク

- **孤児行の生成条件が未確定(4節)。** `task_params_id` が NULL の状態(真の初回 PUT)からの遷移は今回試していない(全対象が既に非 NULL だったため)。将来 20件目以降で「元々 `task_params` を持たない template」を対象にした場合の挙動は未確認。
- **AC16/AC20/AC22/AC23(タイミング精度を要する競合検出)は今回も未検証。** `_022` §5 の理由(Tester はフック・sleep を挿せない、外部からのタイミング制御手段が無い)がそのまま当てはまる。今回の3検証はいずれも競合のない単線の経路であり、この限界は変わっていない。
- **id23→id29 の id 変化は本番(quory)には影響しない**(quory の19件はすべて既存で、削除していない)が、**「本番で実際に schedule が消えた」場合の復元では新しい id になる**ことは運用上の事実として残る。カタログの `name` は不変(R2)なので同定は壊れないが、Semaphore UI 側で id を参照する既存のブックマーク等があれば影響する可能性がある(未確認、運用側の観点)。
- **DB への書き込み(直接 API PUT/POST/DELETE)は Semaphore 自身の機構で行っており、リポジトリ・ansy の設定ファイルは変更していない。** ただし DB の内容(schedule 定義そのもの)は5節のとおりベースラインへ戻したが、`task_params` テーブルの孤児行(7,26,27、私が作ったものではない)は削除していない — 依頼の範囲(reconcile の書き込み経路の検証)を超える清掃行為であり、行うかどうかは運用判断としてCoordinatorへ委ねる。

## Next step files

- `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_001_requirement.md`
- `docs/ai/reviews/semaphore_schedules_as_code/2026-08-10_025_closeout.md`
- `docs/ai/reviews/semaphore_schedules_as_code/2026-08-09_022_test_result.md`
