# Code Review: Operator Request Channel — 3件目の実バグ修正(`_EVENT_FILE_MODE` / 診断出力拡張)

作成: 2026-08-08 / Reviewer(subagent)
対象diff: `git diff 46231af`(未commit)。requirement `2026-08-08_001_requirement.md`、plan `2026-08-08_002_plan.md` §2.3、vertical test `2026-08-08_012_vertical_test.md` を参照。

### Summary

`store._EVENT_FILE_MODE` を `0o640` → `0o660` に変更した本体修正は、default ACL の `mask` がファイル作成モードのグループビットで決まるという原因分析と整合しており、対象を `events/<id>.jsonl` だけに絞った点(message/quarantine/auditへの拡大なし)も requirement 7.1・§11 の immutable 要件と整合する。診断出力(`_describe_failure`)も §9.4/§16 の「検出値・path非開示」を満たしたまま情報量を増やしており、経路も監査されている。

ただし、**修正そのものが本番で実際に効くかどうかを担保する手段が抜けている**。`_EVENT_FILE_MODE` は `os.open()` の `mode` 引数としてのみ使われ、プロセスの umask でグループの書き込みビットが剥がされうる。requirement §8 は「作成時umaskと最終owner／group／modeを固定する」と明記しているが、この diff にも既存コードにも umask を固定する処理は無い。これは今回直したのと**全く同じ壊れ方**(default ACL がどれだけ与えても、グループビットが立っていない mode でファイルが作られると mask が下がる)を、別の変数(umask)経由で再現しうる。新設した回帰テストは umask を変えずに実行するため、この経路を検知しない。

### Critical Issues

| # | File | Line | Issue | Severity |
|---|---|---|---|---|
| 1 | `roles/operator_request_channel/files/oprc/store.py` | 320(`append_event`)、89(`_EVENT_FILE_MODE = 0o660`) | `os.open(path, os.O_WRONLY \| os.O_CREAT \| os.O_APPEND, _EVENT_FILE_MODE)` の `mode` 引数はカーネルが `mode & ~umask` として適用する。この diff にも周辺コード(`bin/oprc-receive`・`bin/operator-channel`・`bin/operator-channel-client`)にも `os.umask()` を呼ぶ箇所が無い。プロセスの ambient umask がグループ書き込みビットを含む値(例: `022`、`027`)であれば、`0o660` は実際には `0o640` で作成され、**今回「修正した」はずの `mask::r--` による `PermissionError` をそのまま再現する**。requirement §8 は「作成時umaskと最終owner／group／modeを固定する」ことを明示的に要求しており、これは実装されていない。`_MESSAGE_FILE_MODE`(`0o440`)は `_atomic_create()` 内で `os.chmod(tmp_path, mode)` により作成後に明示的に固定しているため umask の影響を受けないが(store.py:175)、`_EVENT_FILE_MODE` と `_AUDIT_FILE_MODE` は `os.open()` の mode 引数一発だけに依存する。`audit.jsonl` は `tasks/server.yml` が事前に `state: touch` で作成しているため `O_CREAT` は既存ファイルに対して no-op となり実害が無いが(`test_event_file_acl_mask.py` の `AuditLogUsesADifferentMechanismAndIsUnaffectedTests` が確認済み)、`events/<id>.jsonl` は Ansible で事前作成されず、初回の `append_event()`(通常は `submitted` イベント、`dev-investigate` 側が採番)がその場で新規作成する経路だけがこの罠に当たる。vertical test (`_012_vertical_test.md` §6・§9)で item 2〜7(Operatorの `accept-request` を含む対話操作)が「未判定」のまま残っているため、**yoshi identity が実際に umask 経由でこの罠へ落ちないことは、まだ一度も実地確認されていない**。これは今回「直った」と報告された `accept-request` の失敗と全く同じ症状で再発しうる回帰であり、requirement §8 の未充足でもある。 | Critical |

### Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `scripts/tests/operator_request_channel/test_event_file_acl_mask.py` | `_create()`(28行目付近)、および3クラス全体 | `_create()` はテスト実行時の ambient umask をそのまま使う。このsandboxの umask は `002`(グループビットに影響しない)であるため、`_EVENT_FILE_MODE` がグループビットを持たない値(例えば旧 `0o640` のまま)に退行しても、umaskがグループビットを侵さない環境ではこのテストは常に成立してしまう ―― 「壊れたときに落ちるか」という観点で見ると、umask由来の退行はこのテストの守備範囲外である。`os.umask(0o022)`(または同等値)を明示してから作成する経路を1ケース追加し、`_EVENT_FILE_MODE` がグループの書き込みビットを保つことをumask存在下でも確認するテストを足すことを推奨する。Critical 1と対になる。 | test-coverage |
| 2 | `docs/ai/reviews/operator_request_channel/2026-08-08_002_plan.md` | §2.3 新設節(「ファイル作成モードは、ディレクトリのACLと同じ強さで効く」) | 表の「`0660` → OK(3/3)」という計測結果は、計測時の umask を明記していない。requirement §8 が「作成時umaskを固定する」ことを求めているにもかかわらず、この節の「規則」は umask に一切触れておらず、mode を `0660` にすることだけで十分であるかのように読める。この節は既に2回訂正されており(root所有ファイルで測っていた誤り→提出側が読めない前提の誤り)、3度目として「umaskの影響を計測に含めていない」ことを明記しないと、読み手(次にこのコードへ触る人)が同じ思い込みを引き継ぐ。 | document-norm |

### What Looks Good

- `_EVENT_FILE_MODE` の変更自体(0o640→0o660)は `group::`/`other::` を広げない。ACLの `mask` だけが上がる、という plan の説明は `test_event_file_acl_mask.py` で実機構(setfacl/getfacl)により裏取りされており、目視ではなく実測されている。
- 対象を `events/<id>.jsonl` だけに絞った判断は正しい。`inbox`/`outbox` のmessageは write-once かつ他identityは読むだけで足りるため `_MESSAGE_FILE_MODE = 0o440`(umaskの影響を受けない `os.chmod` 経由)のままで良く、`quarantine-metadata` も同じ経路。`audit.jsonl` は Ansibleの事前 `touch` により別の作成経路(既存ファイルへの `setfacl -m`)を通るため、この罠を元々受けない。この切り分けを3つのテストクラスで裏取りしている点は良い。
- `_describe_failure()` / `_root_cause()` は要求仕様(§9.4「検出カテゴリ・位置・ルールIDだけを返す」、§16「診断は秘密情報を含めずstderrへ」)を満たしたまま、クラス名の連鎖と `errno` だけを追加している。`.filename`/`.filename2` を意図的に読まないと明記されており、`str(exc)` はどの経路でも出力しない。3つのエントリポイントすべてに対応するテスト(`test_root_cause_class_name_and_errno_survive_a_wrapped_exception`)が、メッセージ本文(`"Permission denied"`、`"cannot open event log"`、`"ssh failed"`)が漏れないことと、クラス名・`errno`が出ることの両方を確認しており、fail closedを緩める経路は見当たらない。`_root_cause()` の循環検出(`seen` に訪問済みidを積む)もロジックを追ったが健全。
- `errno` の値そのものは POSIX の標準的な整数であり、path やペイロードの内容を再構成する材料にならない。これは requirement §9.4・§16 が禁じる「検出値」「path」のいずれにも当たらない。
- offline test 一式(320件)をこのセッションで実行し、全件 `OK` を確認した。

### Verdict

**Request Changes**

Critical 1 が未解消のまま commit へ進むと、requirement §8 の「作成時umaskを固定する」が満たされないまま、環境のumaskに依存して「直したはずの `accept-request` 障害」が別条件で再発しうる。vertical test で `accept-request` を含む Operator操作(item 2〜7)が実地未確認である現状、この経路が本当に閉じているかは検証されていない。

推奨する最小修正: `append_event()`(および同じ経路を使う箇所)で `os.open()` の直後に `os.chmod(fd または path, _EVENT_FILE_MODE)` を明示的に呼ぶ(`_atomic_create()` が message file に対して既にやっている方法と同じ)。または生成直前に `os.umask(0)` して直後に元へ戻す。どちらもumaskの値に依存せず最終modeを固定でき、requirement §8 の文言とも一致する。

### 確認した手段(箇条書き)

- `git diff 46231af`(全体・対象ファイルそれぞれ)を読んだ。`git status --short` で変更対象ファイル一覧を確認した。
- requirement §7〜§9、§16、plan §2.3(diff部分・全文)を読んだ。
- `roles/operator_request_channel/files/oprc/store.py` の `_atomic_create`・`append_event`・`_MESSAGE_FILE_MODE`・`_EVENT_FILE_MODE`・`_AUDIT_FILE_MODE` の使用箇所を `grep` と読解で全て特定した(`os.open`/`os.chmod`/`O_CREAT` の呼び出しをファイル横断で洗った)。
- `roles/operator_request_channel/tasks/server.yml` の audit.jsonl 事前作成(`state: touch`)を確認し、audit経路がumaskの影響を受けない理由を裏取りした。
- `scripts/tests/operator_request_channel/test_event_file_acl_mask.py` を読み、umaskを変更するコードが無いことを `grep -n umask` で確認した(このリポジトリ全体・対象diffファイル全てに対して)。
- `roles/operator_request_channel/files/oprc/lifecycle.py` の `_root_cause`/`_describe_failure`/`run_entrypoint` の差分を読み、循環検出ロジックを手でトレースした。
- 3本のテストファイル差分(`test_entrypoint_*.py`)を読み、アサーションが本文非開示とクラス名/errno開示の両方をカバーしていることを確認した。
- `python3 scripts/tests/operator_request_channel/run-tests.py` をansy上のこのsandboxで実行し、320件全てPASSを確認した(このsandboxのumaskは`002`で、Critical 1が指摘する条件を再現しない環境であることも`umask`コマンドで確認した)。
- vertical test `2026-08-08_012_vertical_test.md` を読み、item 2〜7(Operatorの対話操作、accept-requestを含む)が未判定のままであることを確認した — Critical 1の実地未検証根拠。

### 未解決事項

- Critical 1 が実際に本番(quory)で発現するかどうかは、Operator identity(`yoshi`)がSSH forced command以外の経路(quory上のローカルCLIセッション)から `accept-request` を実行したときの実際のumask値に依存する。この値は開発側(ansy)から観測できない。修正(`os.chmod`または`os.umask`での明示固定)を入れれば umask依存性自体が消えるため、値の特定は不要になる。
- 本レビューは requirement §9.3 のDLP検出網羅性、§14 のドリフト検査、§10 のdispatcher非回帰など、今回のdiffに含まれない既存部分は対象外とした(diffスコープ外のため未確認)。

---

## 増分レビュー(2026-08-08、Critical 1 是正分)

対象: `git diff 46231af -- roles/operator_request_channel/files/oprc/store.py scripts/tests/operator_request_channel/`。前回Approve済みの範囲(`_EVENT_FILE_MODE`の値そのもの、診断出力、plan §2.3の当初追記)は再検査していない。

### Critical 1 の開閉判定: **クローズ**

`store.append_event()` は `O_CREAT|O_EXCL` で新規作成を試み、**自分が作成できた場合にだけ** `os.fchmod(fd, _EVENT_FILE_MODE)` でmodeを明示固定するよう変わった(`store.py:357-390`付近)。`os.fchmod()` はPOSIX上いかなるプロセスumaskの影響も受けない(chmodファミリはumaskの対象外)。これにより `append_event()` は「`os.open()`の`mode`引数がumaskでどう処理されるか」というカーネル依存の疑問そのものを迂回しており、requirement §8「作成時umaskと最終owner／group／modeを固定する」の文言と一致する。既存ファイルへの追記(`FileExistsError`分岐)では`fchmod`を一切呼ばないため、所有者でない側が追記するときに`EPERM`を踏む経路は無い。これは自分で以下のとおり独立に再現・確認した。

### 実装記録の「再現できなかった」という記述について

**現物と一致している。** このReviewer自身がこのsandboxで独立に検証した。

```
default ACL のあるディレクトリ配下で mode 0o660・umask 022 → mask::rw-(切り下げ無し)
default ACL の無いディレクトリ配下で mode 0o660・umask 022 → 実mode 0o640(通常通り切り下げ)
```

(検証手順は下記「確認した手段」に記載。最初に「defaultACL無しのplainディレクトリ」のつもりで作った検証コードが、実際には親の default ACL を継承していたために誤った結果を返したことに自分で気づき、完全に独立なディレクトリで取り直して確認した。)

これは Linux の POSIX ACL実装の仕様と一致する ― 親ディレクトリに default ACL がある場合、新規オブジェクトの ACL(mask含む)は default ACL 側から決まり、umaskは適用されない。**events/はまさにこの「default ACLがある」場合に該当するため、私が前回Critical 1で立てた「`os.open()`のmode引数がumaskで切り下げられてmaskが下がる」という具体的な機構は、少なくともこのカーネル/ファイルシステムでは再現しない。** 前回の指摘の「結論」(umaskに依存しない形にすべき)は妥当だが、「機構」の推測は外れていた可能性が高い。

**この不一致は是正の妥当性を揺るがさない。** 理由は3つ。

1. requirement §8 は「umaskを固定する」ことを措置として要求しており、特定の壊れ方を実証することを条件にしていない。`os.fchmod()`はその要求を無条件に満たす。
2. `os.open()`のmode引数とdefault ACLの相互作用は、(実装記録・plan双方が書いているとおり)ドキュメント化された保証ではなく、quoryの実カーネルはansyから検証できない。「このsandboxでは再現しない」は「quoryでも絶対に起きない」の証明にならない ― 判断の基準を「今回たまたま踏まなかった」に置かず、umask非依存という設計そのものに置いた点は正しい。
3. `os.fchmod()`を使う変更自体に新たなリスクや能力の追加は無く(既存の`_atomic_create()`のcreate-then-chmodパターンと同型)、コストゼロで requirement 文言と一致させている。

**したがって Critical 1 はクローズと判定する。** ただし判定の根拠は「実装記録の推測どおり production の umask がACL maskを壊す」ではなく、「壊すかどうかに関係なく、fchmodにより依存性自体が消えた」ことに置く。

### 新規findings

| # | 種別 | 内容 | Severity |
|---|---|---|---|
| 1 | Suggestion(document-norm) | plan §2.3 の追記(「ただし作成モードを書いただけでは足りない」段落)は「`os.open()`に渡すモードは`mode & ~umask`として適用されるため、呼び出し側のumask次第で結果が変わる」と一般則をそのまま断定的に書いている。しかし同じdiff内のstore.py・テストの「honest note」は、events/のようにdefault ACLがある場合にこの一般則がそのとおり再現するかは実測で確認できなかったと明記しており、plan側の記述はこのニュアンスを欠く。結論(fchmodで固定する)は変わらないため実害は無いが、plan §2.3はこの節だけで既に3回書き直されている箇所であり、次に読む人が「umaskがmaskを壊すことを実測で確認済み」と誤読しないよう、store.pyのコメントと同じ留保(「defaultACL下での再現はこのsandboxでは確認できなかった。だからこそ再現性に依存しない設計にした」)を一言足すことを推奨する。 | Suggestion |

Critical/Blockingな新規findingsは無し。O_EXCL導入による並行性・fail closedの退行も見つからなかった(詳細は次節)。

### 観点別の確認結果

- **`O_EXCL`導入と既存の並行性担保**: 単一`os.write()`の原子性、`_events_file_lock()`(flock)は変更されていない。`append_event()`が直接(ロック無しで)呼ばれるのは新規request_idの最初の"submitted"イベントだけであり(`lifecycle.write_accepted()`)、その時点でrequest_idは他プロセスに未共有のため、`O_EXCL`失敗(=他者が既に作成済み)は原理的にこの経路では起きない。ロック付きで呼ばれる経路(`append_event_locked()`、`mark_expired_if_needed()`)は既存ファイルへの追記であり、`O_EXCL`は常に`FileExistsError`となって`O_APPEND`分岐へ落ちる ― 既存の直列化と矛盾しない。`lifecycle.py`と`store.py`を読み、呼び出しグラフを追ってこれを確認した。
- **失敗が成功に見える経路・fail closedの緩み**: 見つからなかった。`FileExistsError`分岐は正常系(他identityが作成済みのファイルへの正当な追記)であり、それ以外の`OSError`は全て`StoreError`へfail closedする。`fchmod`自体が失敗した場合も`fd`を閉じて`StoreError`を送出しており(store.py該当箇所)、黙って進む経路は無い。fchmod失敗で0バイトの中途半端なeventsファイルが残る可能性はあるが、これは§2.9の「message/eventの不整合はfail closed」が既に捕捉する設計であり、この診断追加固有の新しい穴ではない。
- **`fchmod`が作成時にしか呼ばれないこと**: `AppendToExistingEventFileNeverAttemptsChmodTests`が`os.fchmod`をモックしてcall_countを直接検査しており(submitted→accepted→answeredの3回appendでfchmod呼び出しは1回のみ)、コード(`else`節が`O_EXCL`成功時にしか実行されない構造)とテストの両方で確認した。
- **新規テストの検出力**: `EventFileModeIsUmaskIndependentTests`はumask 022を`setUp`で明示的に立て、`addCleanup(os.umask, old_umask)`で確実に復元している(`setUp`内でumask変更より前に例外を投げうる処理が無いため、登録漏れの窓も無い)。`run-tests.py`をこのテストの前後で実行し、umaskが`0002`のまま変わっていないことを確認した(他テストへの汚染なし)。`test_the_actual_store_event_file_mode_is_not_capped_to_read_only`など既存3テストは`store._EVENT_FILE_MODE`定数を直接参照しており定数の退行を検知する。`test_fchmod_is_called_only_when_creating_not_on_a_later_append`は`os.fchmod`のcall_countを直接見ているため、`fchmod`をappend分岐でも呼ぶよう誰かが壊した場合に確実に落ちる。
- **`test_schema.py`の`password`→`unexpected_field`変更**: `test_additional_property_is_rejected`は`additionalProperties: false`による未知フィールド拒否だけを検査しており、フィールド名の意味内容(DLP検出とは無関係、schema検証層の話)はテストの主張に関与しない。フィールド名を変えても検出ロジック・アサーション・強度は一切変わっていない。

### Verdict

**Approve**(この増分について)。Critical 1はクローズ。新規findingsはSuggestion 1件のみで、ブロッキングではない。

### 確認した手段(箇条書き、増分レビュー分)

- `git diff 46231af -- roles/operator_request_channel/files/oprc/store.py scripts/tests/operator_request_channel/` を全文読んだ。
- `roles/operator_request_channel/files/oprc/lifecycle.py`の`_events_file_lock()`・`append_event_locked()`・`mark_expired_if_needed()`・`write_accepted()`を読み、`append_event()`が呼ばれる全経路(ロック有り/無し)を洗った。
- `scripts/tests/operator_request_channel/test_event_file_acl_mask.py`全文を読み、`EventFileModeIsUmaskIndependentTests`・`AppendToExistingEventFileNeverAttemptsChmodTests`のsetUp/assertionを検証した。
- **「defaultACLのあるディレクトリでumaskがACL maskへ影響するか」を自分のsandbox上で独立に再現実験した**(`setfacl -d`で events/ 相当のdefault ACLを持つディレクトリを作り、umask 022下で`os.open(path, O_CREAT, 0o660)`した結果と、defaultACLが一切無い独立ディレクトリでの同条件を比較)。1回目は「defaultACL無しのplainディレクトリ」のつもりが親の default ACL を継承していたため誤った結果になり、完全に独立な`tempfile.mkdtemp()`で取り直して確認した。
- 元のバグ(`mask::r--`)を`os.open(mode=0o640)`で再現したうえで`os.fchmod(fd, 0o660)`を当て、`mask::rw-`へ復元されることを`getfacl`で確認した(修正機構そのものの効果を、テストコードに頼らず自分の手で end-to-end再現)。
- `python3 scripts/tests/operator_request_channel/run-tests.py`を実行し、324件全てPASSを確認した(前回時点320件、今回+4件)。実行前後で`umask`コマンドの出力が`0002`のまま変わっていないことも確認した。
- `docs/ai/reviews/operator_request_channel/2026-08-08_002_plan.md`のCoordinatorによる追記部分を読んだ。

### 未解決事項(増分分)

- quoryの実カーネル・実ファイルシステムでも「default ACL下でumaskがmaskへ影響しない」という挙動が成立するかは、ansyから検証できない。ただし今回の修正(`os.fchmod`)はこの挙動がどちらに転んでも正しく動作するため、この値の特定は結論を左右しない。
- plan §2.3の記述精度に関するSuggestion 1は、次にこの節を読む人が「umaskがACL maskを壊すことを実測で確認済み」と誤解しないための予防的な指摘であり、是正済み実装の安全性そのものには影響しない。
