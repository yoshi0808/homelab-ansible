# Operator Request Channel MVP — 配備後修正の差分レビュー

作成日: 2026-08-08 / Reviewer(subagent、`_006_review.md`とは別体)
対象: commit `ce68005` 以降の**未commit差分**(`git status --short`実測)

```
 M .claude/settings.json
 M docs/ai/reviews/operator_request_channel/2026-08-08_002_plan.md
 M docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md
 M roles/operator_request_channel/defaults/main.yml
 M roles/operator_request_channel/files/bin/operator-channel
 M roles/operator_request_channel/files/bin/operator-channel-client
 M roles/operator_request_channel/files/bin/oprc-receive
 M scripts/tests/operator_request_channel/test_entrypoint_operator_channel.py
 M scripts/tests/operator_request_channel/test_entrypoint_operator_channel_client.py
 M scripts/tests/operator_request_channel/test_entrypoint_oprc_receive.py
?? docs/ai/reviews/operator_request_channel/2026-08-08_010_deploy_verification.md
?? scripts/tests/operator_request_channel/test_capacity_no_content_read.py
```

commit `92e4e90`(`docs/ai/roles/operator.md` / `docs/ai/context/operations/operator-request-channel.md` の日常操作追記)は既にcommit済みであり、`_010_deploy_verification.md`が発端の修正と無関係(Operatorの通常運用手順の追記)のため、本レビューの対象から除外した。`git diff ce68005`はこの既commit分も含んで見えるが、本レビューは`git status --short`が示す未commit差分のみを対象とする。

requirement: `2026-08-08_001_requirement.md`
plan: `2026-08-08_002_plan.md`(§2.3が今回改訂された)
発端: `2026-08-08_010_deploy_verification.md`(item 1 FAIL、item 2 traceback漏出の実測)

## Code Review: Operator Request Channel MVP(配備後修正)

### Summary

配備後検証が実測した2件の実バグ(inbox ACL不足による`submit`の`PermissionError`確定クラッシュ、未捕捉例外の生traceback漏出)を、それぞれ (1) `inbox`ディレクトリの`dev-investigate`権限を`wx`→`rwx`へ拡張、(2) 3エントリポイント共通の`main()`/`_dispatch()`分離+`try/except Exception`による定型`error:`化、で是正している。**両修正とも、要求仕様が禁止する能力の追加には当たらない**ことをコード・ACL設計・テストの3方向から確認した。ディレクトリ`r`が新たに許すのはファイル列挙(`os.listdir`)とサイズ取得(`os.path.getsize`)のみであり、それ自体が他identityの書いたmessage本文ファイルへの`open()`を許すものではないこと(default ACLに`dev-investigate`向けreadエントリが無いこと)をコードで確認した。**ただし`inbox`のmessageファイルは`dev-investigate`自身が呼び出しプロセスの権限で作成するため(`_atomic_create`がEUIDでファイルを作る)、所有者は常に`dev-investigate`になり、mode`0440`の所有者readビットにより`dev-investigate`は自分が提出したOPREQ自身をACLの与え方とは無関係に読める。** `inbox`には提出主体である`dev-investigate`自身が書いたOPREQしか存在しない(requirement §4.2の実行入口制約により他identityはここへ書けない)ため、この所有者読み取りは「自分が書いた内容を読み返せる」以上のものにはならず、他者の本文への新たな越境読み取りは発生しないことを確認した。例外ハンドラは`SystemExit`(既存の`denied:`/`error:`経路)を捕捉対象から明示的に除外しており、`StoreCapacityExceeded`等の想定内例外は依然として個別`except`で先に捕捉されるため、fail-closedの拒否経路への影響はない。新設テストは実際にモックで例外を注入し、生tracebackやマーカー文字列が出力に混入しないことを確認する構成になっており、意味のある回帰検知になっている(実行して303件PASSを確認した)。plan §2.3の記述改訂は、当初「提出側は自分の提出物を読めない」としていた誤った主張を「他identityの本文を読めない、が提出側は元々読めていた」という実態に訂正しており、事実に即した記述になっている。

Critical / Blockingな指摘は無い。Suggestion 2件を報告する。

### Critical Issues

なし。

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `roles/operator_request_channel/files/bin/oprc-receive` / `operator-channel` / `operator-channel-client` | 各ファイルの`main()`(292-320行目付近) | 同一の`try: _dispatch(argv) except Exception as exc: print("error: unexpected internal failure ({})".format(type(exc).__name__), ...); sys.exit(1)`が3ファイルへ一字一句同じ形で複製されている。DLP/schema/store等の中核ロジックは`oprc/`パッケージへ集約する設計原則(plan §3.1、requirement §9.1の「4箇所で同一実装」)を持つ一方、このcatch-allラッパー自体は各エントリポイントの生ファイルに直接書かれているため、将来一方のファイルだけ修正されて挙動が割れる(例えば`type(exc).__name__`の代わりに`str(exc)`を混ぜてしまう)余地が構造的に残る。3箇所ともセキュリティ上の性質(traceback非漏出)を担う同一コードであり、`oprc/`側に`safe_main(dispatch_fn)`のような1つの共通関数を置いて3つのエントリポイントから呼ぶ形にすれば、複製ではなく参照になり、今回のような"配備後に気づく"種類のドリフトを構造的に防げる。ブロッキングではないが、次回この経路に手を入れる際の負債として記録する。 | maintainability / duplication |
| 2 | `roles/operator_request_channel/files/oprc/store.py` `count_and_size()`(156-176行目、今回のdiff対象外だが今回の修正が依拠する前提) | 156 | 今回の是正は「`count_and_size()`が`open()`を呼ばない」という**現状のコードの性質**に依存して、ACLを`rwx`まで広げる判断をしている(`test_capacity_no_content_read.py`のdocstringも明記)。しかしこの前提を守る歯止めはテスト(モックで`open()`をguardする)だけであり、将来誰かが`count_and_size()`へ「メッセージ内の`type`別に集計する」等の理由で`json.load`を足すと、ACLを広げた判断の根拠が静かに崩れる。`test_capacity_no_content_read.py`はこの前提が壊れたときに落ちる回帰テストとして機能するため実質的な歯止めにはなっているが、`store.py`側のdocstringに「この関数はメッセージ本文をopenしてはならない(ACL設計がこれに依存している、plan §2.3参照)」という逆方向の注記が無い。次にこの関数を触る人がテストの意図に気づけるよう、`count_and_size()`自身のdocstringへ一言残すことを推奨する。 | maintainability / documentation |

### What Looks Good

- **ACL拡張の範囲**(plan §2.3 / requirement §8・§10.3・§12.3): `inbox`の`dev-investigate`権限は`wx`→`rwx`のみで、既存の3 ACL・`systemd-journal`グループ・鍵・`authorized_keys`・forced command pathには一切触れていない(diffで確認)。ディレクトリACLの`r`が許すのは`os.listdir`と`os.path.getsize`(`stat`相当)であり、`_MESSAGE_FILE_MODE = 0o440`(owner:r--, group:r--, other:---)かつ`inbox`のdefault ACLに`dev-investigate`向けreadエントリが無いため、他identityが書いたファイル本文への`open()`は依然として拒否される、という設計をコードで確認した。`inbox`へ書き込めるのはrequirement §4.2の実行入口制約により`dev-investigate`自身(coordinator identity)だけであるため、「列挙できるようになった」ことによる新たな越境読み取りは発生しない。plan §2.3が当初書いていた「提出側は自分の提出物を読めない」という主張は、`_atomic_create`が呼び出しプロセスのEUIDでファイルを作る以上ACL設計によらず成り立たない誤りであり、今回の改訂はこれを「他者の本文は読めない」という成立する主張へ正しく訂正している。
- **上限検査の実効性**(plan §2.4): `store.check_capacity()`は`count_and_size()`(`os.listdir`+`os.path.getsize`のみでメッセージ内容を読まない)を経由して件数・総容量の両方を判定し続けており、ACLで権限が通っただけで検査自体が空振りになっていないことを、新設`test_capacity_no_content_read.py`の`test_check_capacity_still_enforces_message_count_limit`/`_total_bytes_limit`が実際に`StoreCapacityExceeded`を送出させて確認している。上限到達時に`denied:`(`cmd_submit`の`except store.StoreCapacityExceeded`)で拒否する経路も変更されていない。
- **例外ハンドラの境界**(requirement §9.4・§16): 3エントリポイントとも`except Exception`のみを捕捉し`SystemExit`(`_deny()`/`_error()`が使う)は素通りさせる設計になっており、`cmd_submit()`内の`StoreCapacityExceeded`・`WireError`・`ValidationError`・`ScanTimeout`等はいずれも個別の`try/except`で先に`_deny`/`_error`へ変換されてから`SystemExit`として送出されるため、新設catch-allより先に処理が終わる。出力するのは`type(exc).__name__`のみで、`str(exc)`・引数・スタックフレームは一切出力しない。既存の`denied:`系拒否パス(DLP拒否・schema拒否・容量拒否・時刻同期拒否)はいずれも変更されておらず、「握りつぶしによって失敗が成功に見える」経路は無い(`main()`は例外時に必ず非ゼロで`sys.exit(1)`する)。
- **中途半端なmessageの非可視化**(requirement §16): `cmd_submit()`のJSON出力は全ストレージ操作(容量チェック・`write_accepted`)成功後の最後の1行のみで、途中で例外が起きても`print()`前に処理が止まるため、catch-allが介入する状況でも部分的なJSONがstdoutへ出ることはない。
- **テストの実効性**: 新設`UncaughtExceptionSafetyTests`(3ファイル×各2〜4件)は`store.append_event`/`canonical.content_hash`/`store.check_capacity`/`store.read_message`等を`mock.patch`で実際に例外を投げさせ、注入したマーカー文字列と`"Traceback"`が出力に含まれないことを確認する構成であり、`_entrypoint_helpers.run_main()`が`SystemExit`しか捕捉しないため、is修正を外せば例外がテストランナーまで伝播して確実に失敗する(自明に真な主張ではない)ことをコードで確認した。`test_systemexit_from_deny_is_not_swallowed_by_the_catch_all`が、catch-allが既存の`denied:`経路を誤って飲み込んでいないことも別途確認している。`test_capacity_no_content_read.py`は第2のOS uidが無いというこのセッションの制約を明記した上で、「コードが本文readに依存しない」という設計レベルの性質を検証する現実的な代替になっている。
- **plan §2.3の記述の安全性**(この節は過去に一度誤った主張をして訂正された経緯がある): 改訂後の文面は「他のidentityの本文を読めない、であって提出側が自分の提出物を読めないではない」と明示し、根拠(`_atomic_create`のEUID挙動、default ACLの範囲)を示した上で、「Coordinatorが最初に行った実測はroot所有のファイルで測っており、配備の実態と条件が違っていた」という誤りの原因まで記録している。読み手に誤った安全性を信じさせる表現は無い。
- **実行して確認**: `python3 scripts/tests/operator_request_channel/run-tests.py`を実行し、303件全てPASSであることを実測確認した(implement記録の主張と一致)。
- **`.claude/settings.json`の追加エントリ**: `playbooks/operator_request_channel_client_setup.yml`を`hosts: ansy`のみで構成していることをファイル本文で確認し、エントリの記述内容(単一play・ansyのみ・他ホストへ到達しない)と一致することを確認した。既存の承認済み"ansyクラス"の範囲内であり、新しい到達能力の追加ではない。

### Verdict

Approve — Suggestion 2件はいずれもブロッキングではなく、次回この経路へ手を入れる際の負債記録として推奨する。

---

## 確認したこと(手段)

- `docs/ai/core.md`、`docs/ai/roles/reviewer.md`を読んだ。
- `docs/ai/reviews/operator_request_channel/2026-08-08_001_requirement.md`(全文)、`_002_plan.md`(全文)、`_010_deploy_verification.md`(全文)、`_006_review.md`(先行差分レビュー、現物確認の起点として)を読んだ。
- `git log --oneline -5`・`git status --short`・`git diff`(追跡ファイル)で対象を確定し、`92e4e90`が本修正と無関係な既commit分であることを`git show --stat 92e4e90`で確認した上でスコープから除外した。
- `git diff -- roles/operator_request_channel/defaults/main.yml`で、`inbox`のACL変更が`wx`→`rwx`の1点のみであることを確認した。
- `git diff -- roles/operator_request_channel/files/bin/{oprc-receive,operator-channel,operator-channel-client}`で、3ファイルとも同一構造の`main()`/`_dispatch()`分離であることを確認した。
- `roles/operator_request_channel/files/oprc/store.py`を`Read`し、`count_and_size()`・`check_capacity()`・`_MESSAGE_FILE_MODE`・`_atomic_create`を確認し、ACL拡張が「列挙のみ許可・本文readは許可しない」という主張と整合することをコードで検証した(この点はdiff対象外だが、ACL変更の妥当性を判断するために現物を読んだ)。
- `roles/operator_request_channel/files/bin/oprc-receive`の`cmd_submit()`全体を読み、`StoreCapacityExceeded`等の想定内例外がいずれも新設catch-allより先に個別`except`で捕捉され`_deny`/`_error`(`SystemExit`)へ変換されること、成功時の`print()`が全処理完了後の1回のみであることを確認した。
- `git diff -- scripts/tests/operator_request_channel/test_entrypoint_{operator_channel,operator_channel_client,oprc_receive}.py`および新設`test_capacity_no_content_read.py`を`Read`し、モックによる例外注入とマーカー文字列非混入の確認方法、および`_entrypoint_helpers.run_main()`が`SystemExit`以外を捕捉しない(=catch-allを外せばテストが失敗する)ことをコードで確認した。
- `python3 scripts/tests/operator_request_channel/run-tests.py`を実行し、303件全てPASSであることを実測した(実ホストへは接続していない、リポジトリ内のtempdir spoolのみを使用)。
- `roles/operator_request_channel/files/oprc/lifecycle.py`の`cmd_submit`関連経路(`write_rejection`/`write_accepted`)を読み、quarantine-metadataの書き込みが`os.listdir`を要しないことを確認し、今回のACL変更が`quarantine-metadata`/`outbox`/`events`のACL(いずれも変更なし)に波及していないことを`git diff`で確認した。
- `git diff -- docs/ai/reviews/operator_request_channel/2026-08-08_002_plan.md`と`_005_implement_channel.md`を読み、plan §2.3の記述改訂内容・実装記録の自己検証記述を、上記のコード確認結果と突き合わせた。
- `git diff -- .claude/settings.json`を読み、追加エントリが参照する`playbooks/operator_request_channel_client_setup.yml`本文を`Read`して`hosts: ansy`のみであることを確認した。
- `roles/operator_request_channel/templates/config.json.j2`・`defaults/main.yml`・`files/bin/operator-channel`で`max_clock_offset_seconds`の配線(review `_006`のSuggestion 1是正、本diffの対象外だが整合性確認のため参照)を確認した。
- `docs/ai/context/operations/operator-request-channel.md`を`grep`し、ACLの具体値(`wx`/`rwx`)を複製していないこと(plan/roleを正本として実値を書かない設計)を確認した。

## 未解決事項

- Suggestion 1(catch-all3重複)・Suggestion 2(`count_and_size()`のdocstring不足)はいずれもCoordinator/Implementerが是正するか、既知の負債として記録するかの判断が必要。ブロッキングではない。
- `_010_deploy_verification.md`が未判定のまま残した項目(item 3-7、22、23、25、26のquory側)は本レビューの対象外(配備・Operatorセッション起動を要するため)。今回の差分はitem 1・2の是正のみを範囲とする。
- quory実機での本fix適用後の再検証(配備後検証のやり直し)はTester/Operatorの工程であり、本レビューでは実施していない(Reviewerは実ホストへansibleを実行しない)。

---

# 増分レビュー(2026-08-08、quory側Operatorレビューを受けた`run_entrypoint()`統合)

対象: 上記レビューの後にさらに増えた差分のみ(`git diff ce68005`のうち、上記で既にレビュー済みの`inbox` ACL `wx`→`rwx`とplan §2.3改訂を除く)。

```
 M roles/operator_request_channel/files/oprc/lifecycle.py   (run_entrypoint() 新設)
 M roles/operator_request_channel/files/oprc/store.py       (count_and_size() docstringへ不変条件を明記)
 M roles/operator_request_channel/files/bin/oprc-receive            (main()がlifecycle.run_entrypoint()経由に)
 M roles/operator_request_channel/files/bin/operator-channel        (同上)
 M roles/operator_request_channel/files/bin/operator-channel-client (同上)
 M scripts/tests/operator_request_channel/test_entrypoint_operator_channel.py
 M scripts/tests/operator_request_channel/test_entrypoint_operator_channel_client.py
 M scripts/tests/operator_request_channel/test_entrypoint_oprc_receive.py
 M docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md
```

私自身が前回Suggestion 1として挙げた「3入口への複製」が、quory側Operatorのレビューを受けて`oprc/lifecycle.py`の`run_entrypoint(dispatch, argv)`という単一関数へ統合された。以下はこの統合が正しく実装されているかの検証結果である。

## Code Review: run_entrypoint()統合と関連是正

### Summary

3つのエントリポイントの`main()`はいずれも`lifecycle.run_entrypoint(_dispatch, argv)`を呼ぶだけの形に統一され、例外の捕捉・`error:`整形・非ゼロ終了は`oprc/lifecycle.py`の1箇所に集約された。Operator提示の契約(`PermissionError`/`OSError`の捕捉、traceback非出力、例外メッセージ非出力、payload/path/検出値非出力、`denied:`/`error:`以外を返さない、想定外例外でもfail closed)をコードで1点ずつ確認し、いずれも満たしていることを確認した。`SystemExit`(`_deny()`/`_error()`が使う)は`Exception`のサブクラスではないため引き続き捕捉対象外であり、`StoreCapacityExceeded`等の想定内例外は各`cmd_*`関数内の個別`try/except`が`run_entrypoint()`より先に処理してから`SystemExit`として送出するため、共通化によって「失敗が成功に見える」経路や「想定内拒否が想定外扱いに落ちる」経路は生まれていない。`oprc/lifecycle.py`への配置は、TTL/期限切れ処理という既存の関心事とは別種ではあるが、循環importは無く(`lifecycle.py`は`ids`/`store`のみをimportし、他モジュールから`lifecycle`への依存は無い)、3エントリポイントが元々`lifecycle`をimport済みだったため新規依存の追加も最小限で済んでいる。新設テスト`test_uses_the_shared_run_entrypoint_safety_net`(3ファイルに1件ずつ)は`lifecycle.run_entrypoint`をモックし`main()`が実際にそれを`_dispatch`を引数として呼ぶことを確認しており、個別`try/except`の復活を機械的に検出できる。さらに、前回レビューでは無かった観点として、例外の**メッセージ本体**(`str(exc)`)へ疑似secretを直接埋め込むテスト(`test_exception_message_body_containing_a_pseudo_secret_is_not_leaked`等、3ファイル×2件=6件)が新設されており、クラス名だけを見て通ってしまう作りにはなっていないことを確認した。「dev-investigateはinboxの本文を読めない」という成立しない主張は、`lifecycle.py`のモジュールdocstring・`oprc-receive`のコメント・`defaults/main.yml`のACLコメント・実装記録から一貫して除去され、正しい性質(他identityの書いた本文は読めないが、自分が書いた本文は所有者権限で読める)に置き換わっていることを`grep`で確認した。ただし1箇所、同じファイル内の別関数(`mark_expired_if_needed()`)のdocstringに、同じ誤りを異なる言い回しで残した箇所を見つけた(下記Suggestion 3)。

### Critical Issues

なし。

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 3 | `roles/operator_request_channel/files/oprc/lifecycle.py` | 219-222(`mark_expired_if_needed()`のdocstring、今回のdiff対象外) | `"Callers without message-file read access must use read_state_from_events() instead and cannot mark expiry themselves"`という一文が残っている。これは今回訂正された「dev-investigateはinbox本文を読めない」という主張と同じ誤りを、「読めない(cannot read)」という語を使わずに"without ... read access"という言い回しで表現しており、`grep -n "読めない\|cannot read"`のような単純な走査では検出できない。実際には`dev-investigate`は自分が書いたinboxのmessageファイルを所有者権限(mode`0440`の所有者readビット)で読めるため、「read accessが無いcaller」という前提そのものが成り立たない。`read_state_from_events()`を使う本当の理由は、モジュールdocstring(今回訂正済み)が説明するとおり「状態の判定に本文が要らないから」という設計上の選択であり、readアクセスの有無で分岐しているわけではない。実装記録`_005_implement_channel.md`は「本記録全体を走査し…残っていないことを確認した」としているが、この一文は見落とされている。ブロッキングではない(誤解を招く箇所であって、動作には影響しない)が、今回の後始末の対象として本来含まれるべき1箇所であり、次の編集機会に同じ訂正(read accessの有無ではなく設計上の選択である旨)を適用することを推奨する。 | correctness / documentation |

### What Looks Good

- **契約の充足**(Operator提示の6項目): `run_entrypoint()`のdocstringと実装(`try: dispatch(argv) except Exception as exc: print("error: unexpected internal failure ({})".format(type(exc).__name__), file=sys.stderr); sys.exit(1)`)を読み、(1)`PermissionError`/`OSError`は`Exception`のサブクラスとして`except Exception`に含まれる、(2)traceback出力用のAPI(`traceback.print_exc()`等)を一切呼んでいない、(3)`str(exc)`ではなく`type(exc).__name__`のみを出力する、(4)この関数自身はpayload/path/検出値のいずれにも触れず`dispatch()`が投げた例外オブジェクトしか受け取らない、(5)出力は`error: unexpected internal failure (...)`の1行と非ゼロ終了のみ、(6)`SystemExit`は`Exception`のサブクラスでないため捕捉対象外で既存の`denied:`/`error:`経路を素通りする、の6点すべてをコードで確認した。
- **想定内例外が握りつぶされていないこと**: `oprc-receive`の`cmd_submit()`を再度読み、`WireError`・`ValidationError`(server_assigned_field/validate)・`LifecycleError`(ttl)・`ScanTimeout`・`StoreCapacityExceeded`・`StoreConflict`がいずれも個別の`try/except`で`_deny()`/`_error()`(`SystemExit`)へ変換されてから`_dispatch()`を抜けることを確認した。これらは`run_entrypoint()`の`except Exception`に到達する前に`SystemExit`として送出されるため、共通化によって拒否理由が`"unexpected internal failure"`という汎用文言へ丸められる退行は無い。`test_systemexit_from_deny_is_not_swallowed_by_the_catch_all`(3ファイルとも)がこれを実測確認している。
- **循環importと配置の妥当性**: `lifecycle.py`の`import`文(`contextlib`/`fcntl`/`json`/`os`/`sys`/`datetime`/`typing`/`from . import ids, store`)を確認し、`lifecycle`へ依存する側(3エントリポイントおよびテスト)からの一方向depであることを確認した。`ids.py`・`store.py`のいずれも`lifecycle`をimportしていないため循環は無い。`run_entrypoint()`がTTL/期限切れという`lifecycle.py`本来の関心事と異なる種類の関数であることは事実だが、3エントリポイントが元々`lifecycle`をimport済みだった(`write_rejection`/`write_accepted`等で使用)ため新規依存追加が不要という利点があり、機能的な問題は無い。
- **テストの実効性 — 共通化の検出**: `test_uses_the_shared_run_entrypoint_safety_net`(3ファイル)は`mock.patch.object(lifecycle, "run_entrypoint")`で`run_entrypoint`自体を差し替え、`main()`実行後に`mock_run.assert_called_once()`と`self.assertIs(args[0], self.module._dispatch)`を確認する構成であり、`main()`が個別`try/except`へ差し戻された場合(`run_entrypoint`を呼ばなくなった場合)は`assert_called_once()`が失敗するため、複製の再発を機械的に検出できることをコードで確認した。
- **テストの実効性 — メッセージ本体への疑似secret**: 前回レビューで指摘した「クラス名だけを見て通ってしまう作りになっていないか」という懸念に対応する`test_exception_message_body_containing_a_pseudo_secret_is_not_leaked`/`test_permission_error_message_body_containing_a_pseudo_secret_is_not_leaked`(3ファイル×2件)は、`_fixtures.password_keyvalue_text()`/`_fixtures.slack_bot_token()`(いずれも実行時に断片から生成、完成形をrepoへ保存しない)を例外の**メッセージ引数**(`str(exc)`に現れる部分)へ直接埋め込み、`combined`(stdout+stderr)にその文字列が含まれないことをアサートしている。`run_entrypoint()`が`type(exc).__name__`のみを出力する実装であるため、この設計なら確実に検出できる構成になっている。
- **「読めない」記述の後始末(1件を除き完了)**: `grep -rn "読めない\|cannot read" roles/operator_request_channel/`で走査し、残る言及がすべて「他identityが書いた本文は読めない」という成立する主張、または`config.py`/`dlp.py`のファイルI/O失敗メッセージ(無関係)であることを確認した。Suggestion 3の1件は"without ... access"という別の言い回しのため、この機械的な走査でも実装記録の走査でも検出されなかったものである。
- **実行して確認**: `python3 scripts/tests/operator_request_channel/run-tests.py`を実行し、312件全てPASSであることを実測した(実装記録の主張と一致)。

### Verdict

Approve — Suggestion 3(既存ドキュメント文言の残存、ブロッキングではない)を除き、Operator指摘の是正はすべて実装・検証されている。今回の増分によって判定が変わる理由は無い。

## 確認したこと(手段、増分レビュー分)

- `git status --short`で増分の対象ファイルを確定した。
- `git diff -- roles/operator_request_channel/files/oprc/lifecycle.py`で`run_entrypoint()`の全文と、モジュールdocstring改訂部分を読んだ。
- `git diff -- roles/operator_request_channel/files/oprc/store.py`で`count_and_size()`docstringへの不変条件追記を読んだ。
- `git diff -- roles/operator_request_channel/files/bin/{oprc-receive,operator-channel,operator-channel-client}`で3ファイルとも`main()`が`lifecycle.run_entrypoint(_dispatch, argv)`のみを呼ぶ形になっていることを確認し、`operator-channel-client`が新たに`lifecycle`をimportしたことも確認した。
- `roles/operator_request_channel/files/bin/oprc-receive`の`cmd_submit()`全体を再読し、`run_entrypoint()`の`except Exception`より先にどの例外がどこで`SystemExit`化されるかを再確認した。
- `roles/operator_request_channel/files/oprc/lifecycle.py`の先頭import群(`contextlib`/`fcntl`/`json`/`os`/`sys`/`datetime`/`typing`/`from . import ids, store`)を読み、循環importが無いことを確認した。`ids.py`・`store.py`をそれぞれ`grep`し、`lifecycle`をimportしていないことを確認した。
- `git diff -- scripts/tests/operator_request_channel/test_entrypoint_{operator_channel,operator_channel_client,oprc_receive}.py`を読み、新設`test_uses_the_shared_run_entrypoint_safety_net`と例外メッセージ本体への疑似secret埋め込みテスト(6件)の構成を確認した。
- `roles/operator_request_channel/files/oprc/_fixtures.py`相当(`scripts/tests/operator_request_channel/_fixtures.py`)の`password_keyvalue_text()`/`slack_bot_token()`を読み、完成形の秘密文字列がrepoに保存されず実行時に断片から生成されることを確認した。
- `grep -rn "本文を読めない\|読めない\|cannot read" roles/operator_request_channel/`を実行し、残存箇所すべてを目視で分類した(その過程で`mark_expired_if_needed()`のdocstringの"without ... access"という言い回しを別途`grep`で見つけた)。
- `roles/operator_request_channel/tasks/server.yml`をgrepし、同種の記述が無いことを確認した。
- `git diff -- docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md`を読み、改訂内容(§3の書き直し、是正②の追加是正、Operator指摘への追加テストの記述)がコードと一致することを確認した。
- `python3 scripts/tests/operator_request_channel/run-tests.py`を実行し、312件全てPASSであることを実測した(実ホストへは接続していない)。

## 未解決事項(増分レビュー分)

- Suggestion 3(`mark_expired_if_needed()`docstringの残存言及)は、Coordinator/Implementerが是正するか既知の軽微な負債として記録するかの判断が必要。ブロッキングではない。
- 上記「未解決事項」節(前回レビュー分)の内容は変わらず有効。quory実機での再検証は本レビューの対象外。
