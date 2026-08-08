# implement: Operator Request Channel MVP — エントリポイント層・配備

作成: 2026-08-08 / Implementer B(subagent)
requirement: `2026-08-08_001_requirement.md`(正本)
plan: `2026-08-08_002_plan.md`
先行記録: `2026-08-08_004_implement_core.md`(共通ライブラリ層、Implementer A)
対象: plan §3.1 の Step 4(3エントリポイント、dispatcher、Ansible role/playbook、ドリフト検査、Semaphoreカタログ、operator.md、残りのoffline/integration test)

先行記録の主張は、着手前に `roles/operator_request_channel/files/oprc/*.py` と `scripts/tests/operator_request_channel/` の現物を自分で読み、実装記録の表(§3公開シグネチャ・§4関数一覧)と現物が一致することを確認してから引き継いだ。一致しない箇所はなかった。

**改訂(2026-08-08、差し戻し)**: 差分レビュー `2026-08-08_006_review.md` の Suggestion 1・2 を是正した。Critical 1(dispatcher配備手順の欠落)はCoordinatorがplan側で処置済みで本記録の対象外。Suggestion 3(operator.mdの参照先安定化)は今回対応しない。是正内容は該当節(§2・§3・§6・§7・§8)を直接更新し、本節を含め新しい節は追加していない。

**改訂2(2026-08-08、監査差し戻し)**: 監査 `2026-08-08_009_audit.md` 指摘1(クローズを妨げる指摘)を是正した — plan §1 が明記していたquory側Python版のpreflight assertが未実装だった。`roles/operator_request_channel/tasks/common.yml` の先頭へ追加し、該当節(§3・§6)を更新した。指摘2(`.gitignore`変更の記帳漏れ)・指摘3(Phase 3カタログI-1の不変条件注記)はCoordinatorの担当範囲であり本記録の対象外。`docs/ai/roles/operator.md`とその後継 `docs/ai/context/operations/operator-request-channel.md` はCoordinatorが別途書き換えており、いずれもこの改訂では一切触れていない。

---

## 1. 対象パス

| path | 内容 |
|---|---|
| `roles/operator_request_channel/files/oprc/lifecycle.py` | **新規**。エントリポイント層固有の設計判断(TTL上限判定・遅延expired化・イベントログのみでの状態判定・拒否/受理の定型記録・同一request_idへの同時イベント追記の直列化)を集約した共通ライブラリの追加ファイル。Implementer Aの7ファイルは1文字も変更していない |
| `roles/operator_request_channel/files/bin/operator-channel-client` | ansy側client(requirement §5.1) |
| `roles/operator_request_channel/files/bin/oprc-receive` | quory側 forced command 受け口(§5.2)。sourceを`coordinator`に固定 |
| `roles/operator_request_channel/files/bin/operator-channel` | quory側 Operator local CLI(§5.3)。sourceを`operator`に固定 |
| `roles/operator_request_channel/defaults/main.yml` | path・上限値・ACL定義 |
| `roles/operator_request_channel/tasks/{common,client,server,spool_acl_entry}.yml` | 配備task(1role、`tasks_from`で分岐、plan §3.1) |
| `roles/operator_request_channel/templates/config.json.j2` | ansy/quory共通1テンプレート |
| `playbooks/operator_request_channel_client_setup.yml` | `hosts: ansy`、check-mode-native |
| `playbooks/operator_request_channel_server_setup.yml` | `hosts: quory`、check-mode-native |
| `scripts/tests/operator_request_channel/test_lifecycle.py` ほか7本 | エントリポイント層 offline/integration test(下記§6) |
| `docs/ai/reviews/operator_request_channel/2026-08-08_005_implement_channel.md` | 本記録 |

### 既存ファイルへの変更(依頼文の4件のみ)

| path | 変更 |
|---|---|
| `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh` | plan §4の4本の`case` armを追加(+58行、削除0行。既存25本は1文字も変えていない — `git diff --stat`で確認) |
| `roles/deployment_drift_check/defaults/main.yml` | §14の10項目のうち残っていた分(配備物hash・owner/group/mode・sudoers不在・allowlist外拒否probe) |
| `roles/deployment_drift_check/tasks/{collect,evaluate}.yml` | 上記の収集・判定 |
| `roles/semaphore_templates/defaults/main.yml` | server setup templateを1エントリ追加(reconcileは実行していない) |
| `docs/ai/roles/operator.md` | 「Operator local CLI」節を1つ追加(command名・path・操作一覧は複製せず、requirementを参照する1行) |

`roles/deployment_drift_check/tasks/report.yml` は変更していない — 新設3クラスの finding は既存の汎用ロジック(`f.playbook`が空なら「直し方」行を出さない)にそのまま乗るため、report.yml側の変更が不要だった。

**追記(監査指摘1の是正)**: `roles/operator_request_channel/tasks/common.yml` の先頭へ、quory側Python版のpreflight assert(2 task)を追加した。新規ファイルではなく既存の対象パス内の変更のため、上表への行追加はしていない — 詳細は下記§3。

---

## 2. 契約の充足状況

| 契約 | 状況 |
|---|---|
| §10.2 forced commandの禁止事項 | dispatcherの4本は固定argv・`exec`のみで`eval`なし。`oprc-receive`はimport一覧が`oprc.*`+`json`+`sys`だけで、`subprocess`/`os.system`/shell呼び出しが1つも無いことをコード走査テストで確認(`ReachabilityBoundaryTests`) |
| §11 Operator local CLIの制約 | `operator-channel`も同様にコード走査で`subprocess`等の不在を確認。到達できるのは`store.append_event`(状態機械で遷移を強制)と`store.create_message`(上書き不可)だけで、編集・削除機能は実装していない |
| §4.2 origin×typeの許可matrix | `oprc-receive`はsourceを`coordinator`固定で`schema.validate_source_type_allowed`を呼ぶため、ansyからOPRES/DEVREQを送ろうとすると拒否される(§4のtypeチェックとあわせて二重に拒否)。`operator-channel`はsourceを`operator`固定で同じ関数を呼ぶため、Operator側からOPREQは作れない。entry-to-entry roundtripテストで実測済み |
| plan §2.11 時刻同期ゲート | `oprc-receive`のsubmitと`operator-channel`のreply-opres/new-devreqの2経路にだけ`config.assert_time_synced(max_offset_seconds=cfg.get("max_clock_offset_seconds", 60.0))`を呼ぶ。get/list/status/accept/rejectは呼ばない(コード上そもそも呼び出し箇所が無い)。**`max_clock_offset_seconds`は実際に判定へ効く(下記§3参照、review Suggestion 1是正)** |
| ①`expires_at`最大TTL超過の拒否 | `lifecycle.compute_expires_at()`が両entry point(submit、reply-opres/new-devreq)から呼ばれる。境界値(ちょうどmax_ttl_days)は受理、1秒超過で拒否をテスト済み |
| ②TTL超過時の`expired`イベント | 下記§3で設計判断を記録。**同一request_idへの同時書き込みはflockで直列化済み(review Suggestion 2是正)** |
| plan §1 quory Python版のpreflight assert | `roles/operator_request_channel/tasks/common.yml`の先頭で`python3 -c 'import sys; ...; assert sys.version_info >= (3, 9)'`相当を実行し、`rc != 0`ならassertタスクで即座にplayを停止する(下記§3参照、監査指摘1是正)。**`--check`実行時にもスキップされない**(`check_mode: false`を明示) |
| check-mode-native / TS-014 | 両playbookとも配備taskすべてに`when: not ansible_check_mode`。TS-015のblock化が要る相互依存チェーンは無い(dev_investigateと同型)。preflight assert(上記行)は読み取り専用の診断であり`when: not ansible_check_mode`の対象外(`--check`でも常に本実行、TS-014の「read-onlyな診断taskにはcheck_mode: false」と同じ扱い) |
| client setupはansyだけ、server setupはquoryだけ | 両playbookとも`hosts: ansy`/`hosts: quory`の単一ホスト指定(グループでなく個別ホスト名。dev_investigate_setup.ymlと同じ慣行) |

---

## 3. 設計判断: ①TTL上限判定と②`expired`イベントの発行主体

先行記録が「エントリポイント層に残した」と明記していた2件(§6未解決事項2・3)。**2026-08-08の差し戻しで、②の同時実行時の破損(review Suggestion 2)と、①②双方が使う時刻同期ゲートの設定値未配線(review Suggestion 1)を是正した。** 以下、当初実装と是正内容を1つの節にまとめて記す(訂正の経緯を積み上げず、現在の状態を記す)。

### 実装

`oprc/lifecycle.py`(新規、Implementer Aの7ファイルとは別)に集約した。

- `compute_expires_at(raw_expires_at, received_at, max_ttl_days, default_ttl_days)`: 省略時は`received_at + default_ttl_days`、指定時は`received_at`より後かつ`received_at + max_ttl_days`以下であることを検査し、外れれば`LifecycleError`(fail closed)。
- `mark_expired_if_needed(spool_dir, box, request_id, message, state, now)`: 呼び出し側が既に読み込んだ`(message, state)`を受け取り、`state`が`submitted`/`accepted`かつ`now > message["expires_at"]`なら`"expired"`を追記して`"expired"`を返す。同一request_idへの同時呼び出しに対して安全(下記参照)。
- `append_event_locked(spool_dir, request_id, event_type, occurred_at, extra=None)`: `store.append_event()`を、`mark_expired_if_needed()`と同じ排他ロックの下で呼ぶラッパー。`accept-request`・`reject-request`・返信作成時の「answered」追記は、この関数経由に統一した(是正内容、下記参照)。

### ②「いつ・誰が発行するか」の判断

**遅延・読み取り駆動(lazy, observed-on-read)方式を採った。** 常駐のスイープ処理・systemd timer・cronは一切追加していない。

- 発行者: quory側で当該requestを読める識別子(`operator-channel`を動かす`yoshi`は inbox/outbox 双方、`oprc-receive`を動かす`dev-investigate`は outbox のみ)が、`list-pending`・`show-request`・`show-status`・outbox向け`request-status`・`message-get`・`accept-request`・`reply-opres`の参照先チェックなど、**既存の読み取り操作のついでに**判定・追記する。
- タイミング: 該当requestが次に読まれた瞬間。誰も見に行かなければ、TTLを超えても`submitted`/`accepted`のまま見え続ける。

**採用理由**:

1. requirement §17が新しい常駐processやscheduleの追加を明示的に除外しており、§5.4は「request登録だけでOperatorセッション・調査・ジョブを自動起動しない」としている。遅延判定はこの制約と自然に整合する — 新しい能力を1つも足さずに済む。
2. plan §2.1「エントリポイントは薄く、呼び出し順だけを持つ」に沿って、判定ロジック自体は`lifecycle.py`という1箇所にまとめ、3エントリポイントのどこからも同じ関数を呼ぶ形にした。
3. `store.ALLOWED_TRANSITIONS`の状態機械が`submitted→expired`・`accepted→expired`を既に許可遷移として持っており(Implementer Aの実装済み契約)、新しい遷移を発明する必要がなかった。

**トレードオフ(明記)**: 誰も読みに行かないrequestは、TTLを超えても見かけ上は最後の状態のまま残る。これは許容した — この案件のMVPが「requestの受け渡し」を目的とし、無人での自動処理を意図的に排除している以上、無人でexpiryを検知する仕組みも同じ理由で不要と判断した。

### 同時書き込みの直列化(review Suggestion 2の是正)

**問題**: 期限切れ判定は遅延評価で、`list-pending`/`show-status`/`message-get`/`outbound-list`/`request-status`等すべての読み取り経路が`mark_expired_if_needed()`を呼ぶ。`store.append_event()`は書き込み直前に現在状態を再チェックするが、その再チェックと実際の書き込み(`os.write`)の間には保護が無い(`store.py`自身のdocstringが認めている)。同じrequest_idを2つの読み取りプロセスがほぼ同時に「まだexpired化されていない」と判定すると、両方が`expired`イベントを追記しうる。`store.ALLOWED_TRANSITIONS["expired"]`は空集合のため、2本目の`expired`行は以後そのrequestの読み取りをすべて`StoreInconsistent`にする — 攻撃ではなく、通常運用の同時読み取りだけで到達する自己誘発の破損だった。

**是正**: `oprc/store.py`は変更していない(Implementer Aの実装、状態機械の定義そのものは正本のまま)。代わりに`oprc/lifecycle.py`へ、request_id自身のeventsファイルに対する排他advisory lock(`fcntl.flock`)を追加した(`_events_file_lock()`)。

- `mark_expired_if_needed()`はロックを取ってから`read_state_from_events()`で状態を**ロック下で再読**し、まだ期限切れ可能な状態(`submitted`/`accepted`)であることを確認してから`expired`を追記する。ロック取得を待っていた側は、取得できた時点で既に状態が変わっていれば何も書かずに現在状態を返す(no-op)。
- **`mark_expired_if_needed()`どうしの排他だけでは不十分だった。** `accept-request`・`reject-request`・返信作成時の「answered」追記は、いずれも`store.append_event()`を直接呼んでおり、`mark_expired_if_needed()`のロックとは無関係に動いていた — たとえば「Operatorがacceptを押した瞬間に、別の読み取りが同じrequestを期限切れと判定する」という組み合わせは、`mark_expired_if_needed`単体のロックでは閉じない。これらの呼び出しを**`lifecycle.append_event_locked()`(同じ`_events_file_lock()`を使う)経由に変更**し、`expired`だけでなく`accepted`/`rejected`/`answered`を含むすべての「既存requestへの遷移追記」が同一のロックで直列化されるようにした。新規request作成時の最初の`submitted`追記(`write_accepted()`)は対象外のまま — 生成直後のrequest_idを他のプロセスが参照できるはずがないため、構造的に競合しない。
- ロックはrequest_idごと(そのrequestのeventsファイル単位)であり、無関係な別requestの処理を待たせない。

**再現テストと検証**: `scripts/tests/operator_request_channel/test_lifecycle.py`の`MarkExpiredIfNeededConcurrencyTests`に3件追加した。
1. `test_many_concurrent_callers_append_exactly_one_expired_event`: 12スレッドが`threading.Barrier`で同時に同じstale `state="submitted"`を持って`mark_expired_if_needed()`を呼び、例外なく完了し、`expired`イベントが1行だけ追記され、その後の`read_message()`が正常に読めることを確認。
2. `test_lock_is_scoped_per_request_id_not_global`: 別々のrequest_idどうしは互いを待たせないことを確認。
3. `test_accept_racing_expire_on_the_same_request_does_not_corrupt_it`: `accept-request`相当(`append_event_locked`)と期限切れ判定(`mark_expired_if_needed`)を同じrequestへ同時に競合させ、`accepted`/`expired`のいずれか一方だけが実際に書き込まれ(イベントログを実際に開いて件数を確認)、`read_message()`が最後まで正常に読めることを確認。

**是正前に実際に失敗することを確認した手順**: 修正版のコードを一時的にロック無しの版へ戻し(`store.append_event()`を直接呼ぶだけの実装)、上記1のテストを8回連続実行して**毎回**`InvalidTransition`または`StoreInconsistent`で失敗することを確認したのち、ロック付きの実装へ戻して同じテストが8回連続で成功することを確認した。テストが実際にこのバグを検出できることの裏取りであり、この操作はローカルの一時ファイル操作のみで実ホストには触れていない。

**修正後もなお残る制約(明記)**:

- ロックは`fcntl.flock`によるadvisory lockであり、ローカルファイルシステム上でのみ確実に機能する。quoryのspool(`/var/lib/operator-request-channel`)はローカルディスクを前提としており、ネットワークファイルシステム(NFS等)へ置く設計変更が将来行われた場合はこの前提を再確認する必要がある。
- ロックが直列化するのは、この案件のコード(`mark_expired_if_needed`・`append_event_locked`)を経由する書き込みどうしだけである。`store.append_event()`を将来どこか別の場所から直接呼ぶコードが追加されれば、そこはこのロックの外になる — **`store.append_event()`を直接呼ぶ新しい呼び出し箇所を足すときは、既存requestへの遷移追記である限り`append_event_locked()`を使うこと**(新規requestの最初の`submitted`追記だけが例外)。
- `store.check_capacity()`→`store.create_message()`間の競合(先行記録が既知の制約として明記)は、今回の是正の対象外であり未解決のまま。

### 時刻同期ゲートの許容オフセット(review Suggestion 1の是正)

**問題**: `config.assert_time_synced()`が両呼び出し箇所(`oprc-receive`のsubmit、`operator-channel`の`_create_response`)で引数なしに呼ばれており、`config.json`の`max_clock_offset_seconds`(defaults/main.yml・config.json.j2・ドリフト検査のhash対象にもなっている設定値)がどこにも渡っていなかった。既定値どうし(configの60、関数既定値60.0)が一致していたため動作は正しく見えたが、host間で値を変えても効果が無い死んだ設定項目だった。

**是正**: 両呼び出し箇所を`config.assert_time_synced(max_offset_seconds=cfg.get("max_clock_offset_seconds", 60.0))`に変更した。`cfg.get(..., 60.0)`としたのは、`oprc/config.py`の`REQUIRED_OPERATOR_HOST_KEYS`がこのキーを必須にしていない(先行記録の判断、変更していない)ため — 未設定でも`assert_time_synced()`自身の関数既定値と同じ60.0にフォールバックし、KeyErrorで落ちない。**設定項目は削除せず、実際に配線する側を選んだ**(quory側`config.json.j2`は常にこの値を書き出すため、実運用では常に設定値が使われる)。

是正が「実際に判定へ効くこと」の確認は2段構成で行った。①ライブラリ層: 先行記録(Implementer A)の`test_config.py TimeSyncTests`が、`max_offset_seconds`を明示的に渡したときにその値が閾値として機能することを既に証明している(境界値超過で拒否)。②配線: 本担当が追加した`test_configured_max_clock_offset_seconds_reaches_assert_time_synced`(oprc-receive・operator-channel双方)が、`config.assert_time_synced`をモックし、`config.json`の値を変えたときに実際にその値が`max_offset_seconds`引数として渡っていることを呼び出し引数の検査で確認した。①②を合わせて「設定値→呼び出し引数→実際の閾値判定」の全経路が繋がっていることを示す。

### quoryのPython版preflight(監査指摘1の是正)

**問題**: plan §1「未確認事項への対処」は、quoryのPython版が開発側から観測できないことへの対処として、「server setup playbookの先頭でPython 3.9以降であることを確かめ、前提が崩れていれば配備前に停止させる」preflight assertを明記していた。この実装(当初版)には該当するタスクが1つも無かった — `oprc/`をPython 3.9+標準ライブラリのみに限定するという設計判断(§2.1、TOMLでなくJSONを採る根拠でもあるD1)の裏付けが、実装からすっぽり抜けていた。監査(`_009_audit.md`指摘1)がこれを「クローズを妨げる」指摘として検出した。

**是正**: `roles/operator_request_channel/tasks/common.yml`の**先頭**(schema/rulesetのhash計算より前)へ2 taskを追加した。

```yaml
- name: "Preflight: confirm this host's python3 is 3.9 or newer (plan §1)"
  ansible.builtin.command:
    cmd: python3 -c 'import sys; print(...); assert sys.version_info >= (3, 9)'
  register: operator_request_channel_python_preflight
  changed_when: false
  failed_when: false
  check_mode: false

- name: Fail closed if python3 is missing or older than 3.9
  ansible.builtin.assert:
    that: [operator_request_channel_python_preflight.rc == 0]
    fail_msg: ...
  check_mode: false
```

設計判断:

- **対象playbook**: plan §1は「server setup playbookの先頭で」とだけ書いているが、`common.yml`はclient.yml/server.ymlの両方からimportされる共有task fileであるため、**client(ansy)側にも同じpreflightが自動的に適用される**。ansyのPython版はplan §1の時点で3.14.4と確認済みで不確実性は無いが、(a) `oprc/`の3.9+要件はansy側にも等しく適用される制約であり、(b) common.ymlに1回書くだけで重複task無しに両ホストを守れる、(c) 将来ansyの実行環境が変わった場合の検出にもなる、というコストゼロの理由で対象を絞らなかった。plan §1の文言(quoryの未確認を理由とする)より広い適用だが、**能力を増やす変更ではなく、同じ読み取り専用の安全策を及ぼす範囲を広げただけ**である。
- **`--check`でもスキップされないこと**: `command`モジュールは既定でcheck-mode非対応(auto-skip、`skills/ansible-implementation-style/SKILL.md`「check_modeの実装上の落とし穴」1.)であり、`check_mode: false`を明示しないと`--check`実行時にこのtask自体が評価されずスキップされる。スキップされると、`--check`だけで確認を済ませたときに前提確認が行われないまま「確認した」ことになってしまい、監査が問題視した「配備前に停止させる」という役目を果たさない。読み取り専用で副作用が無いため、`check_mode: false`で常に本実行しても安全側に倒れる(TS-014の「read-onlyな診断taskにはcheck_mode: false」と同型)。
- **判定方法**: Python自身の`sys.version_info >= (3, 9)`によるタプル比較を使い、Jinja側で文字列を分解して独自に大小比較するロジックを書かなかった。将来Python 4系が出た場合も含め、この比較は言語自身が正しく扱う。
- **失敗時の停止**: `command`task自体は`failed_when: false`で常に成功扱いにし、判定は独立した`assert`taskに委ねた(既存の「schema/rulesetが読めるか」チェックと同じ形)。`assert`が失敗すると、Ansibleの既定動作でそのhostに対する以降の全taskが実行されずplayが止まる — `ignore_errors`は使っていない。

**検証**: 実ホストへは一切接続・配備していない。`hosts: localhost, connection: local`の使い捨てplaybook(`docs/ai/core.md`が個別の承認なしで許可する形態)で`operator_request_channel`role(`tasks_from: client`)を`--check`付きで実行し、次の2ケースを確認した。

1. **成功ケース**: このマシンの実際のpython3(3.14.4)でpreflightが`ok`となり、`success_msg: "python3 preflight OK: 3.14.4"`が出力され、後続taskへ進むことを確認した。
2. **失敗ケース**: `PATH`を一時的に書き換え、`echo "3.6.9"; exit 1`だけを行う偽の`python3`(scratchpad配下、repo外)を割り込ませて実行し、`assert`taskが`rc=1`を検出して`fatal`でplayが即座に停止し、後続のschema/ruleset読み取りやファイル配備のいずれのtaskにも到達しないことを確認した。

いずれも`--check`付きで実行しており(preflight task自体は`check_mode: false`のため実際に走り、他の全destructive taskは`when: not ansible_check_mode`のため`--check`下では評価されない)、実ホストの状態を一切変えていない。

### ACLの非対称性から生じた副次設計: `read_state_from_events()`

`dev-investigate`は`inbox/`のメッセージ本文を読めない(下記§4のACL判断)。そのため`oprc-receive`の`request-status`がinbox項目(ansy自身が出したOPREQ)に対して呼ばれた場合、`message["expires_at"]`を読むための`read_message()`自体が実行できない。この場合は`lifecycle.read_state_from_events()`(イベントログだけを読んで状態を判定する、`store.ALLOWED_TRANSITIONS`を再利用し状態機械を二重定義しない)にフォールバックし、**lazy expiry判定は行わない**(判定材料の`expires_at`にそもそも到達できないため)。結果として、ansy自身が出したOPREQの`expired`化は、Operator側(`yoshi`、inbox本文を読める)がそのrequestを何らかの形で見たときにだけ起きる。この非対称性はACL設計の直接の帰結であり、意図的なものとして記録する。

---

## 4. requirement/planとの食い違いを発見し、狭い方(安全側)を採った箇所

### 4.1 plan §2.3の表と説明文の矛盾(inbox ACL)

plan本文 `2026-08-08_002_plan.md` 97行目の表は `inbox/` へ `default u:dev-investigate:r` を挙げているが、直後の107行目の説明文は「**`inbox` に `dev-investigate` の read を与えない**…default ACL が付与するのは…`yoshi` の read だけである」と明記しており、両者は矛盾する。

**この実装は説明文(狭い方)を採用した** — `roles/operator_request_channel/defaults/main.yml`の`operator_request_channel_acl.inbox.default_entries`に`dev-investigate`のエントリを含めていない。理由:

1. 説明文には明確な安全根拠(「提出側は自分の提出物を読み返す必要がない、requirement §5.1の取得対象はOPRES/DEVREQだけ」)が書かれているのに対し、表側にはその種の理由が付いていない — 表側が転記ミスである可能性が高い。
2. 最小権限の原則に合致する狭い方を採る方が、後から広げるより安全側の失敗になる。
3. この判断の帰結を上記§3の`read_state_from_events()`という具体的な設計として吸収した(ACLを狭くしたことで生じる機能的な穴を、別の経路で埋めた)。

`defaults/main.yml`のACL定義ブロック冒頭に、この食い違いと判断根拠をコメントとして残した。**Coordinator/Reviewerはplan本文側の表記を修正するか、この実装のACLを承認するかを確認すること** — これは記録どうしの不一致であり、独断で握りつぶさずここに明記する。

### 4.2 deployment_drift_checkカタログ: 共有ファイルを1エントリでなく2エントリ(ホストごと)にした

plan §3.3は「共有ファイル(ライブラリ・schema・rules)のエントリを `hosts: [ansy, quory]` として登録する」としているが、実装では**ファイルごとに`hosts:[ansy]`/`hosts:[quory]`の2エントリに分けた**。

理由: `roles/deployment_drift_check/tasks/report.yml`の「直し方」ロジックは、1つのカタログエントリにつき`playbook`フィールドを1つしか持てない。`hosts:[ansy,quory]`の1エントリに`playbook: playbooks/operator_request_channel_server_setup.yml`(または client 側)を持たせると、ansy側で見つかったfindingにquoryのsetup playbookを(またはその逆を)案内する**誤った**「直し方」が出る。ファイルごとに2エントリへ分けても、両方が同一の`src:`(同じrepoのファイル)を参照し続ける限り、plan が狙っていた「両ホストの配備物が同一srcと一致する」という推移的な一致検査の実質は変わらない — 変わるのは「1エントリか2エントリか」という表現だけで、**どちらの形でもansy側だけを検査してquory側を検査対象から外す、という抜け(plan本文が警戒していた事態)は起きない**。

`roles/deployment_drift_check/defaults/main.yml`の当該ブロック冒頭にこの判断根拠をコメントとして残した。

---

## 5. 実装中に見つけて修正した既存バグ(自分の担当範囲内)

`operator-channel-client`の初版実装で、新規OPREQ送信時に`conversation_id`を一切生成していなかった(requirement §6.2「新規OPREQでは…conversation_id は起点requestに対応させる」を満たしていなかった) — ユーザーが`conversation_id`を明示的に渡さない限り、送信payloadに`conversation_id`が欠落し、quory側のschema必須フィールド検証で機械的に拒否される状態だった。テスト作成中(`test_submit_generates_its_own_conversation_id`)に発覚し、`cmd_submit`内で`raw["conversation_id"] = ids.generate_conversation_id()`を追加して修正した(サーバー割当フィールドではないため、クライアント側での生成が正しい設計)。

また`operator-channel`の`show-conversation`実装の初版に、ページング内側ループの誤った`break`(最後のページの2件目以降を取りこぼす)があった。これも実装直後の目視レビューで発見し修正した。

---

## 6. 自己検証で確認したこと

- `python3 scripts/tests/operator_request_channel/run-tests.py -v`: **288件全てPASS**(Implementer Aの162件 + 本担当126件、差し戻し是正分の6件を含む)。実行環境はansy相当のローカル環境、`python3.14.4`。同時実行テスト(`MarkExpiredIfNeededConcurrencyTests`)はフレーク耐性を見るため単独で12回連続実行し、全回成功を確認した。
- review Suggestion 2の是正が実際にバグを再現・解消することを、ロック無しの旧実装へ一時的に戻して同じテストが8回連続で失敗し(`InvalidTransition`/`StoreInconsistent`)、ロック付き実装に戻すと8回連続で成功することを確認した(§3参照)。
- `ansible-playbook --syntax-check` を両playbookに実行し、いずれもエラーなし。
- `ansible-lint playbooks/operator_request_channel_{client,server}_setup.yml`: `Passed: 0 failure(s), 0 warning(s) in 7 files processed`。
- `scripts/check-tester-gate.sh`: `[tester-gate-lint] OK (54 playbooks)`。
- `gitleaks detect --no-git`を対象パス(role本体・playbook・test・変更した既存4ファイル)へ個別に実行し、いずれも `no leaks found`。差し戻し是正で変更した6ファイル(`oprc/lifecycle.py`・`bin/oprc-receive`・`bin/operator-channel`・test 3本)についても同じ検査を再実行し、`no leaks found`を再確認した。
- IPv4リテラル検査: `scripts/git-pre-commit-check.sh`と同じ正規表現(`([0-9]{1,3}\.){3}[0-9]{1,3}`、127.0.0.1/0.0.0.0/255.255.255.255は除外)を対象ファイル全文へ適用し、ヒット0件(差し戻し是正分も同様)。DLP fixtureは`_fixtures.py`の断片組み立てのみを使用し、疑似secret・private IPの完成形をファイルへ書いていない。
- 変更/新規のYAML全ファイルを`yaml.safe_load_all`で構文検査し、全件OK。
- `roles/deployment_drift_check`へ足した3クラスが実際にfindingを立てることを、`hosts: localhost, connection: local`の使い捨てplaybook(`docs/ai/core.md`のdecoy inventory相当、実ホスト非接触)で7ケース(owner/group/mode一致・3属性不一致・path欠落・sudoers空・sudoers該当・probe正しく拒否・probe誤って許可)すべて確認した。実ホストの状態は一切変更していない。
- `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh`の既存25本について: `git diff --stat`で**追加58行・削除0行**であることを確認(既存armは1文字も変わっていない)。加えて、新設4本の arity/形式/allowlist外拒否のテストと、既存armのうち quory 固有パスに依存しない6本(disk/load/failed/ports/journal-system/deployed-hash)をこのホスト上でローカル実行するサンプル非回帰テストを`test_dispatcher.py`に含めた。
- DLPの4検査点すべてで同一fixtureが拒否されることを、実際に4つの入口(ansy送信前・quory受入前・quory持ち出し前・ansy取り込み前)を通す統合テスト(`test_dlp_blocks_the_same_fixture_at_all_four_inspection_points`)で確認した。
- request_id衝突時に上書きされず後着が拒否されること(§16「同時submit時にもrequest ID衝突…が起きない」の実測可能な部分)を、`ids.generate_request_id`を固定値へ差し替えて2回submitするテストで確認した。
- **監査指摘1(preflight)の是正確認**: `hosts: localhost, connection: local`の使い捨てplaybookで`operator_request_channel`role(`tasks_from: client`)を`--check`付きで実行し、(a)実際のpython3(3.14.4)では preflight が`ok`となり後続taskへ進むこと、(b)`PATH`をscratchpad配下の偽`python3`(常に旧versionを返して`exit 1`)へ一時的に差し替えるとpreflightの`assert`taskで即座に`fatal`となり後続の全taskが実行されないことを確認した。両ケースとも`--check`付きで実行しており、preflight task自体は`check_mode: false`のため実際に走ることを確認した(§3参照)。実ホストへは一切接続していない。
- `roles/operator_request_channel/tasks/common.yml`変更後の`ansible-playbook --syntax-check`・`ansible-lint`・`scripts/check-tester-gate.sh`を再実行し、いずれも変更前と同じ結果(エラー無し)であることを確認した(上記と同じコマンド、変更後に再実行)。
- **`docs/ai/roles/operator.md`は今回の改訂2で一切変更していない。** Coordinatorが本記録とは別に同ファイルを書き換え、運用の記述を`docs/ai/context/operations/operator-request-channel.md`へ移設したため、その内容についてはこの記録の検証対象から外す(§1「先行担当の主張を現物で確かめずに引き継がない」と同じ理由で、他Agentの変更を自分の成果物として扱わない)。

## 7. requirement §18.1/§18.2・plan §6 T-A〜T-Gとの対応

先行記録が既にカバーした項目(ライブラリ層のschema/DLP/store単体テスト)は再掲しない。本担当が追加したのは主にエントリポイント層の end-to-end 経路。

| 項目 | 対応するテスト |
|---|---|
| T-A(4検査点が同一engine/ruleset) | `test_integration_roundtrip.py`の4チェックポイントテスト |
| T-C(4検査点の回帰、12カテゴリ) | ライブラリ層はA、entry point層での通過確認は本担当(submit/reply/get各所のDLPブロックテスト) |
| T-D(R-1境界) | `ReachabilityBoundaryTests`(oprc-receive)、`R1BoundaryTests`(operator-channel)のコード走査+削除/更新コマンド不在の確認 |
| T-E(message/event不整合でfail closed) | ライブラリ層はA(`store.read_message`の5条件)。entry point層では`mark_expired_if_needed`のStoreError捕捉(リスト全体を落とさない)に加え、**同一request_idへの同時書き込みそのものを`_events_file_lock`で直列化し、不整合の発生自体を防ぐ**(review Suggestion 2是正、§3参照)。`MarkExpiredIfNeededConcurrencyTests`3件で実測 |
| T-F(時刻同期停止) | `test_time_not_synchronised_blocks_submit`/`test_time_not_synchronised_blocks_new_devreq`。get/list/statusは同ゲートを一切呼ばないことをコード確認。**`max_clock_offset_seconds`が実際に`assert_time_synced`へ渡ることを`test_configured_max_clock_offset_seconds_reaches_assert_time_synced`で確認**(review Suggestion 1是正、§3参照) |
| T-G(ドリフト検査新設3クラス) | 上記§6のlocalhost検証7ケース |
| §18.1 originとtypeの許可matrix | entry point層での拒否確認(OPRES/DEVREQ from ansy、OPREQ from operator) |
| §18.1 forced commandのarity/改行/allowlist外拒否 | `test_dispatcher.py`全体 |
| §18.1 既存dev-investigate非回帰 | 上記§6参照 |
| §18.2 4項目(submit→accept→OPRES→pull、standalone DEVREQ、4検査点、再取得の決定性) | `test_integration_roundtrip.py` |
| §18.2 通信切断後の再試行で重複/上書きなし | request_idは常に受信側が新規採番するため「同じidでの再送」は構造的に起きない。その前提となるatomic create衝突拒否をentry point層で実測(§6参照) |
| §18.2 channel経路からSemaphore/systemctl/sudo/Git/任意pathへ到達不可 | `oprc-receive`/`operator-channel`双方のコード走査(subprocess/os.system/shell=True不在) |

---

## 8. 未解決事項・Coordinatorへの確認事項

1. **§4.1のplan/prose矛盾**(inbox ACLのdefault entry)。この実装は説明文(狭い方)を採用し、plan本文の表記修正が必要かはCoordinator/Reviewerの判断を仰ぐ。
2. **§4.2のdeployment_drift_checkカタログ形状**(1エントリ vs ホストごと2エントリ)。挙動は変えず「直し方」の正しさを優先した判断であり、Reviewerに妥当性を確認してほしい。
3. **`docs/ai/context/operations/code-delivery-to-production.md`は未変更。** plan §3.2はこのファイルの`deployed-hash`対応表更新も挙げているが、依頼文の「既存ファイルへの変更(この4つだけ)」表に含まれていないため触れていない。**併せて、既存dispatcherの`deployed-hash`コマンド自体にも`oprc-receive`/`operator-channel`を追加していない**(§10で25本のarmを変えない制約に抵触するため意図的)。配備物のhash検証は`deployment_drift_check_files`カタログ側で完結しており機能的な穴は無いが、`deployed-hash`対応表とこの文書のどちらを更新するかはCoordinatorの判断範囲として残す。
4. 先行記録が挙げていた未解決事項のうち、本担当が引き継がなかったもの(`check_capacity`→`create_message`間の粗い競合防御、DLPの正規表現ヒューリスティックの限界、naive datetimeの扱い)はライブラリ層の範囲でありエントリポイント側からは変更していない。
5. ~~`max_clock_offset_seconds`はconfigのオプションキー…既定値どうしが一致しているため動作は正しい~~ **是正済み(2026-08-08、review Suggestion 1)。** 両entry pointは`config.assert_time_synced(max_offset_seconds=cfg.get("max_clock_offset_seconds", 60.0))`を呼ぶよう変更し、設定値が実際に判定へ渡ることをテストで確認した(§3参照)。設定項目は削除していない。
6. **`expired`イベントの同時二重付与によるrequest恒久破損は是正済み(2026-08-08、review Suggestion 2)。** `oprc/lifecycle.py`にrequest_idごとのadvisory lock(`_events_file_lock`)を追加し、`mark_expired_if_needed`だけでなく`accept-request`/`reject-request`/「answered」追記も同じロック経由(`append_event_locked`)に統一した。修正前に実際に失敗し修正後に成功することをテストで確認済み(§3参照)。**残る制約**: ロックはローカルファイルシステム前提(quoryのspoolはローカルディスクのため現状は問題ない)。将来`store.append_event()`を直接呼ぶ新しい呼び出し箇所を足す場合は、既存requestへの遷移追記である限り`append_event_locked()`経由にすること。`check_capacity`→`create_message`間の競合(先行記録の既知の制約)は今回の対象外で未解決のまま。
7. **実配備は行っていない。** quoryへの`git pull`、`SEMI-SAFE: Semaphore templates setup`の実行、server setup templateの登録・実行はいずれも本セッションの範囲外(plan §5)。
8. **plan §1のquory Python版preflight assertは是正済み(2026-08-08、監査`_009_audit.md`指摘1)。** `roles/operator_request_channel/tasks/common.yml`の先頭に追加し、client(ansy)側にも同じ担保を及ぼした。`--check`実行時にもスキップされないこと(`check_mode: false`)、および実際にrc!=0で配備前にplayが停止することの両方を、`hosts: localhost, connection: local`の使い捨てplaybookで確認済み(§3・§6参照)。監査指摘2(`.gitignore`変更の記帳)・指摘3(Phase 3カタログI-1不変条件への注記)は、監査自身が「クローズを妨げない」「Coordinatorの担当」としており、本担当のこの改訂では対応していない。
