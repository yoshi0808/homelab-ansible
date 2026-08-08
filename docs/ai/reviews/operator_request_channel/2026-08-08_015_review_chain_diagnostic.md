# Code Review: Operator Request Channel — 診断出力の連鎖化(改訂6、`_root_cause` → `_exception_chain`)

作成: 2026-08-09 / Reviewer(subagent)
対象diff: `git diff HEAD`(未commit、HEAD=`b69948c`)。対象ファイル5本(`roles/operator_request_channel/files/oprc/lifecycle.py`、`scripts/tests/operator_request_channel/test_lifecycle.py`・`test_entrypoint_operator_channel.py`・`test_entrypoint_operator_channel_client.py`・`test_entrypoint_oprc_receive.py`)と記録側`docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md`(改訂6追記2行)。requirement `2026-08-08_001_requirement.md` §9.4・§16、直前レビュー`2026-08-08_013_review_event_mode.md`を参照した。`docs/ai/status.md`はCoordinator担当のためレビュー対象外。

### Summary

`_root_cause()`(連鎖の最深部1つだけを返す)を`_exception_chain()`(連鎖の全リンクを外側から内側まで返す)へ置き換えた本体修正は正しい。`store.append_event()`の`except FileExistsError:`(正常な制御フロー)内で発生した実際の失敗が、旧実装では無害な`FileExistsError`自身に隠されて報告されない、という構造的欠陥を独立に再現し、新実装がそれを解消することを確認した。値の非開示(`str(exc)`・path・payload不読み出し)も維持されている。ただし、**実装記録`_005`の改訂6見出しは「該当節(§3・§6・§8)を更新した」と明記しているが、実際には見出し段落(2行)が追加されただけで、§3・§6・§8本文は`_root_cause()`を現行実装であるかのように記述したまま**であり、記録の整合に欠陥がある。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md` | 21(改訂6見出し)、259-267(§3「未捕捉例外の観測性改善」)、340(§6)、396-397(§8項目12) | 改訂6見出しは「該当節(§3・§6・§8)を更新した」と主張するが、`git diff HEAD -- docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md`は見出し段落2行の追加のみで、他に変更が無い。結果として、§3(259-267行)は今も`_root_cause(exc)`を「`__cause__`/`__context__`を辿って連鎖の最深部を返す」現行実装であるかのように記述し、`_exception_chain()`・全リンク方式には一切触れていない。§6(340行)の自己検証記述も同様に`_root_cause`ベースの確認内容のままで、改訂6で追加された`DescribeFailureExceptionChainTests`(`test_lifecycle.py`)や3エントリポイントの`test_intermediate_exception_inside_a_control_flow_except_handler_is_not_hidden`(このReviewerが独立に検証した回帰テスト、下記参照)への言及が無い。§8項目12も同様(umask是正の記述のみで、改訂6の内容が無い)。この案件は既に3回(§4.1のACL理由づけ、plan §2.3の`os.open()`/umask記述、この改訂6)同種の「見出しは更新を宣言するが本文が追随しない」パターンを繰り返している。次にこの記録を読む者(次のsubagent・Auditor)は、現在の診断出力が「外側クラス名+根本原因クラス名(異なる場合のみ)+errno」という旧設計のままだと誤解する。 | Critical |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `scripts/tests/operator_request_channel/test_entrypoint_operator_channel.py` | 313(`test_root_cause_class_name_and_errno_survive_a_wrapped_exception`)、同名テストが他2エントリポイントtestにも存在 | このテスト名・docstringは「root cause」という単一値を確認する体で書かれているが、実装は既に全リンク方式(`_exception_chain`)へ変わっており、このテストがまだ成功しているのはチェーンが2リンクしかない偶然の一致による(全リンク出力にはouter/rootの両方が必然的に含まれる)。関数改名時にテスト名・docstringが追随しておらず、次に読む人へ旧設計を示唆する。実害はないため、記録の整合(Critical 1)ほど優先度は高くないが、改名または「(root=…のみでなく全リンクが出ることを含む)」注記の追加を推奨する。 | document-norm |

### What Looks Good

- `_exception_chain()`/`_describe_failure()`の本体実装(`lifecycle.py`)は、観測された現象(quory実機での`error: unexpected internal failure (StoreError, root=FileExistsError, errno=17)`)を正確に説明する設計になっている。`store.append_event()`の`except FileExistsError:`ブロック内でさらに`os.open(path, O_WRONLY|O_APPEND)`が失敗すると、新しい例外の`__context__`が(Pythonの暗黙連鎖により)経由済みの`FileExistsError`を指す、という因果を自分でコードから追い、この構造が確かに存在することを確認した。
- **診断の充足を自分で再現して確認した**: `lifecycle.py`を改訂6適用前のHEAD版(`_root_cause()`使用)へ一時的に差し替え(scratchpadへバックアップの上、`git show HEAD:...`から復元)、`python3 scripts/tests/operator_request_channel/run-tests.py`を実行したところ、新設テスト6件(`test_lifecycle.py`の`DescribeFailureExceptionChainTests`3件が`AttributeError: module 'oprc.lifecycle' has no attribute '_exception_chain'`、3エントリポイントの`test_intermediate_exception_inside_a_control_flow_except_handler_is_not_hidden`が`AssertionError: 'PermissionError' not found in 'error: unexpected internal failure (StoreError, root=FileExistsError, errno=17)\n'`)が失敗することを確認した——この失敗メッセージは実機観測値と文字どおり一致する。その後ファイルを現行版へ復元し、`git diff --stat`が元のdiff(152行変更)と一致すること、offline test 334件全PASSを再確認した。**修正を戻すと落ちる**ことを自分の手で立証した。
- 値の非漏洩: `_describe_failure()`はチェーン各リンクの`type(link).__name__`と(intの場合のみ)`errno`だけを組み立て、`str(exc)`・`.filename`/`.filename2`を一切読まない。3エントリポイントの新設テストが、注入した疑似メッセージ本文(`"Permission denied"`・`"File exists"`・`"cannot open event log"`/`"ssh failed"`)がstdout/stderrいずれにも現れないことを検証しており、コードとテストの両方で確認した。
- 出力の有界性: `_MAX_CHAIN_LENGTH=8`・`_MAX_DESCRIPTION_LENGTH=500`により、循環連鎖・長大連鎖・長いクラス名のいずれでも出力が無制限に伸びない。`test_cycle_does_not_hang`・`test_chain_length_is_capped`・`test_description_string_length_is_capped`で個別に検証されており、テストの主張とアサーションを読み、実装(`while`ループの停止条件、文字列truncateの位置)と一致することを確認した。
- テストの強度: `test_lifecycle.py`の新設6件は実装の写経ではなく、`__cause__`優先(`test_explicit_cause_is_preferred_over_implicit_context`)、循環耐性、長さ上限、`OSError`以外のリンクに`errno`が付かないこと(`test_non_oserror_links_carry_no_errno`)など、実装が満たすべき性質を個別に検査している。3エントリポイントの回帰テストは実装のコピーではなく、`store.append_event()`が実際に踏んだ形(`except FileExistsError:`内で別例外が起きる)を`_run_ssh`・`store.append_event`・`store.check_capacity`いずれの差し替えでも再現しており、3ファイルへの複製は同一の共有関数(`run_entrypoint`)を3つの入口それぞれから確認するという既存の慣行(このファイル群の他のテストクラスも同型)と一致する。
- `run_entrypoint()`のdocstring(`_describe_failure`呼び出し部分)は「the caught exception or for any exception in its chain」と、全リンクを対象にした非開示保証へ正しく書き換えられている。

### Verdict

**Request Changes**

Critical 1(記録の整合)が理由。コードとテストの安全性・診断充足そのものには blocking な欠陥は見つからなかった。実装記録`_005`の改訂6見出しが「更新した」と主張する§3・§6・§8本文の追随が実際には行われておらず、旧関数名`_root_cause()`を現行実装として記述したまま残っている。是正は当該3節の本文を`_exception_chain()`/全リンク方式・新設テスト名へ書き換えるだけであり、コード変更は不要。

### 確認した手段(箇条書き)

- `docs/ai/core.md`・`docs/ai/roles/reviewer.md`・案件フォルダの`2026-08-08_001_requirement.md`(§9.4・§16該当箇所)・`2026-08-08_005_implement_channel.md`(全文、offset分割で読了)・`2026-08-08_013_review_event_mode.md`(全文)を読んだ。
- `git diff HEAD`で対象5ファイルおよび記録ファイルの差分を全文読んだ。
- `roles/operator_request_channel/files/oprc/store.py`の`append_event()`(315-399行)を読み、`except FileExistsError:`分岐内の二段目`os.open()`が失敗した場合の例外連鎖(`__context__`)を手でトレースし、報告されていた`root=FileExistsError, errno=17`が生じる機構を自分で再構成した。
- `lifecycle.py`を一時的にHEAD版(`git show HEAD:...`から復元、scratchpadに現行版をバックアップ)へ差し替え、`python3 scripts/tests/operator_request_channel/run-tests.py`を実行して新設6テストが失敗し、失敗メッセージが実機観測値と一致することを確認した。直後に現行版を復元し、`git diff --stat`が元のdiffと一致すること・offline test 334件全PASSを再確認した(実ホスト非接触、ansy上のsandboxのみで完結)。
- `grep -rn "_root_cause\|root="`をrole本体・test・記録ファイルへ適用し、`_root_cause`という文字列が残る箇所を全て洗い出し、コード側(lifecycle.py内のhistoryコメント3箇所)は意図的な説明であり無害、記録側(`_005`本文と`_013`)は改訂6を経ても更新されていないことを確認した。
- `scripts/tests/operator_request_channel/test_lifecycle.py`・3本の`test_entrypoint_*.py`差分を全文読み、アサーションが値非開示(メッセージ本文不在)とチェーン全体の開示(クラス名・errno)の両方を検査していることを確認した。
- `git status --short`で本レビュー対象外のファイル(`docs/ai/status.md`、未追跡の`2026-08-08_014_vertical_test_2.md`)を識別し、いずれも変更・言及していない。

### 未解決事項

- Critical 1の是正(記録本文の書き換え)は実装差分そのものの安全性には影響しないため、コード側のRequest Changesではない。ただしCoordinatorの担当範囲(記録の完成)として残す。
- 本レビューは改訂6のdiffスコープ(`lifecycle.py`の診断出力とその回帰テスト)に限定しており、`accept-request`失敗そのものの原因究明は依頼文の指示どおり対象外(未解決のまま)。vertical testのitem 2〜7(Operator操作の実地確認)は本レビューでも未確認(Testerの担当範囲)。
