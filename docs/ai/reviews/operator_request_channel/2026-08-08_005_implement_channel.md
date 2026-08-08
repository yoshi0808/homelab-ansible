# implement: Operator Request Channel MVP — エントリポイント層・配備

作成: 2026-08-08 / Implementer B(subagent)
requirement: `2026-08-08_001_requirement.md`(正本)
plan: `2026-08-08_002_plan.md`
先行記録: `2026-08-08_004_implement_core.md`(共通ライブラリ層、Implementer A)
対象: plan §3.1 の Step 4(3エントリポイント、dispatcher、Ansible role/playbook、ドリフト検査、Semaphoreカタログ、operator.md、残りのoffline/integration test)

先行記録の主張は、着手前に `roles/operator_request_channel/files/oprc/*.py` と `scripts/tests/operator_request_channel/` の現物を自分で読み、実装記録の表(§3公開シグネチャ・§4関数一覧)と現物が一致することを確認してから引き継いだ。一致しない箇所はなかった。

**改訂(2026-08-08、差し戻し)**: 差分レビュー `2026-08-08_006_review.md` の Suggestion 1・2 を是正した。Critical 1(dispatcher配備手順の欠落)はCoordinatorがplan側で処置済みで本記録の対象外。Suggestion 3(operator.mdの参照先安定化)は今回対応しない。是正内容は該当節(§2・§3・§6・§7・§8)を直接更新し、本節を含め新しい節は追加していない。

**改訂2(2026-08-08、監査差し戻し)**: 監査 `2026-08-08_009_audit.md` 指摘1(クローズを妨げる指摘)を是正した — plan §1 が明記していたquory側Python版のpreflight assertが未実装だった。`roles/operator_request_channel/tasks/common.yml` の先頭へ追加し、該当節(§3・§6)を更新した。指摘2(`.gitignore`変更の記帳漏れ)・指摘3(Phase 3カタログI-1の不変条件注記)はCoordinatorの担当範囲であり本記録の対象外。`docs/ai/roles/operator.md`とその後継 `docs/ai/context/operations/operator-request-channel.md` はCoordinatorが別途書き換えており、いずれもこの改訂では一切触れていない。

**改訂3(2026-08-08、配備後検証の差し戻し)**: 配備後検証 `2026-08-08_010_deploy_verification.md` がquory実機で2件の実バグを検出した(item 1: submitが`PermissionError`で確定的に失敗、item 2: 未捕捉例外の生tracebackがstderrへ出る経路の実在)。契約変更(plan §2.3のinbox ACLを`wx`→`rwx`へ改訂、Coordinatorがansy上で実測して裏付け済み)を反映し、両バグを是正した。該当節(§3・§6・§8)を更新した。`docs/ai/roles/operator.md`・`docs/ai/context/operations/operator-request-channel.md`・`.claude/settings.json`はこの改訂でも一切触れていない。

**改訂4(2026-08-08、配備後の縦方向試験による差し戻し)**: quory実機で`accept-request`が`error: unexpected internal failure (StoreError)`で確定的に失敗する3件目の実バグが見つかった(events/ファイルのPOSIX ACL mask問題)。契約変更(plan §2.3に「ファイル作成モードはディレクトリのACLと同じ強さで効く」節を追加、Coordinatorがansy上で実測)を反映し、`oprc/store.py`の`_EVENT_FILE_MODE`を是正した。あわせて、この障害の特定にCoordinatorがOperatorへ`getfacl`を依頼する必要があったという観測性の指摘を受け、共通例外ハンドラ(`lifecycle.run_entrypoint()`)に根本例外のクラス名と`errno`を(メッセージ本文・path・payloadは出さないまま)残す改良を行った。該当節(§3・§6・§8)を更新した。`docs/ai/roles/operator.md`・`docs/ai/context/operations/operator-request-channel.md`・`2026-08-08_002_plan.md`・`docs/ai/status.md`・`.claude/settings.json`はこの改訂でも一切触れていない。

**改訂5(2026-08-08、レビュー`_013_review_event_mode.md`による差し戻し)**: 2件。① Critical 1: `_EVENT_FILE_MODE`の値そのものを直しても、`os.open()`へ渡すmode引数は呼び出し側のumaskの影響を受けうるため、requirement §8「作成時umaskと最終owner／group／modeを固定する」を満たしていなかった。`oprc/store.py`の`append_event()`を、umaskの影響を受けない`os.fchmod()`で作成直後にmodeを固定する形へ書き直した(**ただし、実際にumaskがACL maskへ影響するかはこのsandboxのカーネルでは再現できなかった — 詳細と誠実な記録は下記§3参照**)。② GitGuardianが公開リポジトリの`test_schema.py:76`を誤検知(`password="should-not-be-a-field"`という`key=value`形のliteral)、フィールド名を中立な名前へ変更した。該当節(§3・§6・§8)を更新した。`docs/ai/roles/operator.md`・`docs/ai/context/operations/operator-request-channel.md`・`2026-08-08_002_plan.md`・`docs/ai/status.md`・`.claude/settings.json`はこの改訂でも一切触れていない。

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

**この節は2026-08-08(Operator提示の指摘、Coordinator差し戻し)に理由づけを訂正した。** 以前の記述は「`dev-investigate`は`inbox/`のメッセージ本文を読めない」という主張に基づいていたが、**この主張は成り立たない** — `inbox/<id>.json`はdev-investigate自身のEUIDで作成され(`store._atomic_create`)、mode`0440`は所有者readビットを含むため、dev-investigateは自分が提出したメッセージ自身をACLとは無関係に所有者権限で読める。この設計が実際に与える性質は「**他のidentityが書いた本文を読めないこと**」であり、「提出側が自分の提出物を読めないこと」ではない。`inbox`に入るのは常にdev-investigate自身が送信したOPREQだけなので、越境読み取り(他者が書いたものを読むこと)はそもそも発生しない。

`oprc-receive`の`request-status`がinbox項目(ansy自身が出したOPREQ)に対してメッセージ本文を読まず、`lifecycle.read_state_from_events()`(イベントログだけを読んで状態を判定する、`store.ALLOWED_TRANSITIONS`を再利用し状態機械を二重定義しない)を使う**設計判断そのものは変わっていない**。理由は「読めないから」ではなく「状態の判定に本文が要らないから」 -- request-statusが答えるべきは「このrequestは今どの状態か」だけであり、それはイベントログ単独で過不足なく分かる。所有者権限で本文を読めるという事実に暗黙に依存したコードを書くより、必要なものだけを読む経路の方が、将来ACLや所有権の実装が変わっても壊れにくい。

結果として、ansy自身が出したOPREQの`expired`化(lazy expiry判定、§3の下記参照)は、inbox本文を読める側(Operator、`yoshi`)がそのrequestを何らかの形で見たときにだけ起きる -- これは`read_state_from_events()`が`expires_at`を読まない(読めないからではなく設計上読まない)という選択の帰結であり、ACL上の制約の帰結ではない。

`roles/operator_request_channel/files/oprc/lifecycle.py`のモジュールdocstringと`roles/operator_request_channel/defaults/main.yml`のACLコメントを、同じ訂正で書き直した(§3の下記追記参照)。

### quoryでの受理失敗・生traceback漏出・例外ハンドラの是正(配備後検証item 1・2、Operator指摘の追加是正)

**問題①(item 1、Critical)**: quoryへの配備後、DLP・schemaに合格する正当なOPREQでも`oprc-receive submit`が`PermissionError`で確定的にクラッシュし、request_idが1件も発行できないことが2回再現した。

```
PermissionError: [Errno 13] Permission denied: '/var/lib/operator-request-channel/inbox'
```

原因は`defaults/main.yml`のACL設計と`store.py`の実装の不整合だった: `inbox`の`dev-investigate`権限は当初`wx`(write+execute)のみで`r`(read)を持たず、`store.count_and_size()`(`check_capacity()`経由で全submitがDLP合格後・メッセージ作成前に必ず通る)が容量集計のため`os.listdir(directory)`を呼ぶ。ディレクトリの**列挙**には`r`権限が要り、`x`だけでは個々の既知パスへの到達はできても列挙はできない。dev-investigate identityで実行される限り、この呼び出しは構造的に必ず`PermissionError`になっていた。

**是正①**: Coordinatorがplan §2.3を改訂し、inboxの`dev-investigate`権限を`rwx`へ変更した(ansy上の実測付き)。`roles/operator_request_channel/defaults/main.yml`の該当行を`permissions: wx`から`permissions: rwx`へ変更し、コメントを書き直した(上記「ACLの非対称性…」節と同じ訂正を含む)。`store.py`の`count_and_size()`のdocstringにも、この関数が message 本文を`open()`してはならないという不変条件を明記した(Operator指摘②、下記参照) -- ACL拡大後の安全性はこの不変条件に依存しており、以前はテストだけがこれを守っていた。

**問題②(item 2)**: ①の再現時、Pythonの生tracebackがそのまま`stderr`へ出力されることが実地で確認された。`cmd_submit()`の`try/except`は個別の想定例外(`schema.ValidationError`等)だけを捕捉しており、想定外の例外(今回は`PermissionError`)を捕まえる網が無かった。

**是正②(初版)**: 3エントリポイントそれぞれの`main(argv)`へ、既存の`main`を`_dispatch(argv)`へ改名した上で`try/except Exception`を個別に追加した。

**是正②の追加是正(Operatorレビュー、同日中)**: 3箇所へ複製した`try/except`を、**`oprc/lifecycle.py`の`run_entrypoint(dispatch, argv)`という共通関数1箇所へ括り出した**。3つの入口が将来ばらけて1つだけ生tracebackを漏らす、という事態を防ぐため。

```python
# oprc/lifecycle.py
def run_entrypoint(dispatch, argv) -> None:
    try:
        dispatch(argv)
    except Exception as exc:  # noqa: BLE001
        print("error: unexpected internal failure ({})".format(type(exc).__name__), file=sys.stderr)
        sys.exit(1)

# 各エントリポイント(oprc-receive / operator-channel / operator-channel-client)
def main(argv):
    lifecycle.run_entrypoint(_dispatch, argv)
```

`run_entrypoint()`が保証する契約(Operator提示のとおり):

- `PermissionError`・`OSError`を捕捉する -- いずれも`Exception`のサブクラスであり、`except Exception`が既に両方を含む(名指しした理由は、今回の実バグが`PermissionError`そのものだったため)。
- tracebackを出さない。
- 例外メッセージ(`str(exc)`)をそのまま表示しない -- 表示するのは`type(exc).__name__`(**クラス名のみ**)。クラス名はpayload内容から作られることがないが、例外メッセージ自体は処理対象の断片を含みうる(下記テストが確認する観点そのもの)。
- payload・path・DLP検出値は表示しない -- この関数自身はそれらに一切触れず、`dispatch()`が投げた例外オブジェクトしか受け取らない。
- 返すのは`error: unexpected internal failure (<例外クラス名>)`という1行とゼロでない終了コードのみ -- 予期しない例外でもfail closed。
- `SystemExit`(`_deny()`/`_error()`が使う)は`Exception`のサブクラスではないため捕捉されず、既存の`denied:`/`error:`終了経路は変更していない。

**是正の実効性を検証した手順**: `oprc-receive`の`main()`を一時的に是正前の形(`_dispatch(argv)`をそのまま呼ぶだけ)へ戻し、`UncaughtExceptionSafetyTests`を実行 -- 想定どおりテスト自身がエラー(生tracebackが実際に伝播することの確認)になったことを確認したのち、是正版へ戻して同じテストが成功することを確認した(§6参照)。

**Operator指摘への追加テスト**: 既存の注入テストは例外の**クラス名**だけを見ており、**例外メッセージ本体**に疑似secretが乗るケースは無かった。3エントリポイントそれぞれへ、疑似secret文字列を例外メッセージに直接埋め込んだ`RuntimeError`/`PermissionError`を注入するテストを追加し、stdout・stderrいずれにもその文字列が現れないことを確認した(§6参照)。

### events/ファイルのPOSIX ACL mask問題(配備後の縦方向試験、3件目の実バグ)

**問題**: quory実機でOperatorが`accept-request`を実行すると`error: unexpected internal failure (StoreError)`で失敗し、状態は`submitted`のまま変化しなかった。`list-pending`/`show-request`/submitはいずれも成功していた。Operatorが対象ファイルへ`getfacl`を実行した結果:

```text
# file: /var/lib/operator-request-channel/events/req-...jsonl
# owner: dev-investigate
user::rw-
user:yoshi:rw-              #effective:r--
user:dev-investigate:rw-    #effective:r--
mask::r--
group::---
other::---
```

**原因**: POSIX ACLでは、ディレクトリにdefault ACLがある状態で**新規**ファイルを作成すると、そのACL_MASKエントリは`open()`/`creat()`に渡した`mode`引数の**groupビット**によって上書き・制限される — ディレクトリのdefault ACL自体が何を許可しているかとは独立に、である(`group::`エントリはこれとは別に、ディレクトリ自身の`default:group::`から継承される)。`oprc/store.py`の`_EVENT_FILE_MODE`は`0o640`(groupビット`r--`)だったため、`events/`のdefault ACLが`dev-investigate`/`yoshi`双方に与えていた`rw`は、新規作成されたファイル上では常に実効`r--`へ切り詰められていた — 上記`getfacl`の出力と完全に一致する。

`events/`はsubmit(dev-investigateが作成し"submitted"を追記)・accept/reject/reply-opres(yoshiが"accepted"/"rejected"/"answered"を追記)・lazy expiry判定(どちらの側からも起こりうる"expired"の追記)のいずれもが、**自分が作成していないファイルへ書き込む**唯一のspoolファイル種別であり、この切り詰めが即座に機能不全を引き起こした。

**是正**: `roles/operator_request_channel/files/oprc/store.py`の`_EVENT_FILE_MODE`を`0o640`から`0o660`(groupビット`rw-`)へ変更した(`store.py`はImplementer Aの実装だが、この1点はCoordinator/Operatorの明示指示による)。plan §2.3にCoordinatorが追加した「ファイル作成モードは、ディレクトリのACLと同じ強さで効く」節と、その実測(毎回新しいディレクトリ、各3回、決定的)に基づく。

**この実装者自身による裏取り**: このsandbox上で`setfacl`/`getfacl`を使い、`events/`と同じmode(`1700`)・同じ形のdefault ACLを持つ使い捨てディレクトリを作り、実際に`0o640`で作成したファイルが`mask::r--`(バグを再現)、`0o660`で作成したファイルが`mask::rw-`(是正を確認)になることを実測した(`scripts/tests/operator_request_channel/test_event_file_acl_mask.py`)。第2の実OS uidは不要 — `setfacl`のnamed entryは実在するアカウントに解決できなくても機能するため、任意の数値UIDで機構そのものを再現できる。

**「他のファイルに同じ罠が無いこと」の確認(依頼文の指示どおり自分で確認、要らないものまで広げない)**:

| ファイル種別 | 作成モード | 別identityが後から必要とする権限 | 結論 |
|---|---|---|---|
| `inbox`/`outbox`の message(`_MESSAGE_FILE_MODE`) | `0o440` | 読み取り(`r`)のみ -- messageはwrite-onceで、作成後は誰も書き込まない | **変更不要**。groupビット`r--`から作られるmask`r--`は、必要な`r`をちょうど満たす(実測: `test_message_file_mode_grants_exactly_the_read_access_it_needs`) |
| `quarantine-metadata`(`_MESSAGE_FILE_MODE`共用) | `0o440` | 現状、この案件のどのentry pointからも読み書きされない(読み取りに対応するforced command/CLI操作自体が無い) | **変更不要**。書き込みが要る箇所が存在しない |
| `audit.jsonl`(`_AUDIT_FILE_MODE`) | `0o660`(既存のまま) | dev-investigate・yoshi双方が追記 | **変更不要、かつ元から無関係**。Ansibleが`file: state=touch mode=0660`で**先に**作成し(`server.yml`)、その後`setfacl -m`で既存ファイルへ直接ACLを付与する経路であり、「ディレクトリのdefault ACLを新規ファイルが継承する」経路(バグの発生条件そのもの)を通らない。既存ファイルへの`setfacl -m`はmaskを自動的に再計算するため、この罠に元から該当しない(実測: `test_setfacl_on_an_existing_0660_file_grants_full_effective_rw`) |

**`group::`・`other::`が広がっていないことの確認**: 同じ実測(`test_fix_does_not_broaden_group_or_other`)で、`0o640`作成時と`0o660`作成時の`group::`/`other::`が完全に一致することを確認した -- どちらも`---`のまま。これらのエントリは(default ACLにgroup::/other::の明示指定が無い限り)ディレクトリ自身の`default:group::`/`default:other::`から継承され、作成モードの引数には左右されない。

### 未捕捉例外の観測性改善(同じ障害の診断が困難だったことへの対応)

**問題**: 上記バグの原因特定には、Coordinatorがquory上のOperatorへ`getfacl`の実行を依頼する必要があった。`run_entrypoint()`が出力していたのは外側の例外(`StoreError`)のクラス名だけで、その下の根本原因(`PermissionError`)は握りつぶされていた。`store.append_event()`自身の`StoreError`メッセージは実際には安全な形で根本原因のクラス名を含んでいた(`"cannot open event log: {}".format(type(exc).__name__)`)が、`run_entrypoint()`は`str(exc)`を一切出力しない設計だったため、この情報も一緒に失われていた。

**是正**: `oprc/lifecycle.py`に`_root_cause(exc)`(`__cause__`/`__context__`を辿って連鎖の最深部を返す、循環耐性あり)と`_describe_failure(exc)`(外側のクラス名・根本原因のクラス名(異なる場合のみ)・根本原因が持つ`errno`(整数のみ)を組み立てる、`str(exc)`と`.filename`/`.filename2`は一切読まない)を追加し、`run_entrypoint()`の出力を`error: unexpected internal failure (<説明>)`へ変更した。

**設計判断: どこへ残すか(stderrのみ、監査記録へは残さない)**: 依頼文が「あなたの設計判断」とした点。stderrのみとし、`audit.jsonl`への記録は追加しなかった。理由:

1. `run_entrypoint()`は`dispatch`と`argv`だけを引数に取る、意図的に依存の無い薄いラッパである(§3「同時書き込みの直列化」の`_events_file_lock()`と同じく、共通化の価値は「単純で複製されないこと」にある)。監査記録には`audit_log_path`(configから得る)が要り、これを引数に加えると、3つの呼び出し元すべてが常に正しいpathを渡す責任を負うことになり、複製のリスクを共通化前の状態へ半分戻すことになる。
2. 例外は`_load_config()`より前(configそのものが壊れている場合)にも起こりうる -- その場合`audit_log_path`は存在しない。stderrはconfigの状態に関わらず常に使える経路である。
3. 今回の実インシデントを実際に解決したのはstderrの情報(Operatorがそれを見てCoordinatorへ伝え、Coordinatorが`getfacl`を依頼した)であり、監査記録が必要だったわけではない。observabilityの実際のニーズはstderrで満たされる。

**再確認条件の充足状況**: 根本例外のクラス名と`errno`は`_describe_failure()`が出力に含める。例外メッセージ本文・path・payload・検出値は`_describe_failure()`のどの経路でも一切読まない(`.filename`/`.filename2`を明示的に避けている)ことをコードとdocstringの両方に明記し、疑似secretをメッセージ本文へ埋め込む既存テスト(review差し戻しで追加)が是正後も全件成功することを確認した(§6参照)。

### events/作成modeのumask依存を解消(review `_013_review_event_mode.md` Critical 1の是正)

**指摘**: `_EVENT_FILE_MODE`を`0o660`に直しても、`os.open()`へ渡す`mode`引数はカーネルが`mode & ~umask`として適用するため、呼び出し側(quory上のOperatorセッション)のumask次第で結果が変わりうる。requirement §8は「作成時umaskと最終owner／group／modeを固定する」と明記しており、これが未実装だった。quoryのOperatorセッションのumaskは開発側から観測できない。

**是正**: `oprc/store.py`の`append_event()`を書き直した。`os.open(..., O_CREAT | O_EXCL, _EVENT_FILE_MODE)`でまず作成を試み、

- 自分が**新規作成した**場合(成功時): 直後に`os.fchmod(fd, _EVENT_FILE_MODE)`を呼ぶ。`os.fchmod()`(`os.chmod()`と同様)はumaskの影響を一切受けない -- これが実際に固定を担保する。`_atomic_create()`が message ファイルに対して既にやっている「作成後にchmodする」パターンをevents/にも適用した形。
- **既に存在した**場合(`FileExistsError`): chmodを一切試みない。理由(依頼文が明示した見落としやすい点そのもの): chmod/fchmodはファイルの所有者(またはroot)しか呼べない。events/ファイルは自分が作成していない側が追記する(dev-investigateが作成した"submitted"にyoshiが"accepted"を追記、等)ことが前提の設計であり、追記だけの側がchmodを試みると`EPERM`になる。追記側は`O_WRONLY | O_APPEND`(`O_CREAT`なし)で開くだけで、mode変更は一切試みない。

**この修正で正直に記録すべきこと**: 是正の実装中、「umaskが実際にACLのmaskへ影響するか」をこのsandbox上で再現しようと試みたが、**再現できなかった**。ext4・tmpfsいずれの上でも、`events/`と同じ形(mode `1700`・named userへのdefault ACL)のディレクトリでumask `022`を有効にした状態で単純な`os.open(path, O_CREAT, 0o660)`を実行しても、結果のACL maskは`rw-`のままだった(mask化されなかった)。一方、**default ACLが絡まない普通のファイル**では、同じumask `022`が`0o660`を`0o640`へ確実に切り詰めることも別途確認した(umask自体は機能している)。

このため、「default ACLが存在するディレクトリでの新規ファイル作成時、umaskがACL maskへ及ぶかどうか」は、少なくともこのsandboxのカーネルでは確認できなかった、というのが実際の実測結果である。**ただしこれは是正を見送る理由にはならない**:

1. この挙動は移植性のある仕様として文書化されているものではなく、カーネルバージョンやACL実装によって過去に異なる振る舞いをしてきたと言われている領域であり、quoryの実際のカーネルがこのsandboxと同じ挙動を示す保証が無い(quoryのカーネルはこのセッションから観測できない)。
2. `os.fchmod()`がumaskの影響を一切受けないことは、ACLの有無に関係なく無条件に正しいPOSIXの挙動であり(これも直接再検証した)、この経路を使えば「default ACL とumaskの相互作用がどちらに転ぶか」という問いそのものを迂回できる。
3. requirement §8は「固定する」ことを求めており「安全な方に転ぶことを祈って測る」ことを求めていない。

`store.py`のコードコメントと`test_event_file_acl_mask.py`のテストdocstringの両方に、この実測結果(再現できなかったこと)を誠実に記載した -- 「umaskがこの経路を壊すことを確認した」という、実際には確認できていない主張はどこにもしていない。

**再確認条件の充足状況**:

- **umaskを変えて実際に確かめるテスト**: `EventFileModeIsUmaskIndependentTests`(`test_event_file_acl_mask.py`)が、umaskを`022`(グループの書き込みビットを削る値)に設定した状態で実際に`store.append_event()`を呼び、結果のACL maskが`rw-`になること(`test_append_event_fixes_the_mode_even_under_a_hostile_umask`)、`os.fchmod()`自体がumaskの影響を受けないこと(`test_fchmod_is_exempt_from_umask_unconditionally`、ACL非依存の直接証明)、umaskそのものはこのプロセスで機能していること(`test_umask_masks_a_plain_open_with_no_default_acl_involved`、対照実験)を確認した。umaskはテスト内で確実に元へ戻す(`addCleanup`、プロセス全体に影響する値のため他テストへ漏れないことも確認済み)。
- **追記側がEPERMにならないこと**: `AppendToExistingEventFileNeverAttemptsChmodTests`が、`os.fchmod()`が「作成した1回だけ」呼ばれ、同じrequest_idへの2回目以降の`append_event()`(追記)では**呼ばれない**ことをモックで確認した(`mock.patch("os.fchmod", wraps=os.fchmod)`で呼び出し回数を検証)。このsandboxには実uidが1つしか無く`EPERM`そのものは再現できないため、`EPERM`回避が依存している「作成時にしかchmodを試みない」というコードレベルの保証を直接検証する形にした(この限界は依頼文の過去のやり取りで許容されている手法と同型)。
- **message/quarantine/auditの扱いを変えていないこと**: `_atomic_create()`(message/quarantine共用)・`_AUDIT_FILE_MODE`の初期化経路はいずれも今回変更していない(`append_event()`のみを変更)。既存の`test_event_file_acl_mask.py`の該当テストクラスは変更前と同じ内容のまま全件成功する。
- **是正前に実際に失敗することの確認**: `append_event()`を一時的に是正前の形(`os.open(..., O_CREAT | O_APPEND, _EVENT_FILE_MODE)`単発)へ戻し、`AppendToExistingEventFileNeverAttemptsChmodTests`が実際に失敗する(`fchmod`呼び出し回数が0のまま)ことを確認したのち、是正版へ戻して成功することを確認した。**`EventFileModeIsUmaskIndependentTests`側は、是正前のコードでもこのsandboxでは成功してしまう**(上記の「再現できなかった」実測と整合する結果であり、テストの不備ではなく、環境依存の挙動をこのsandboxが偶然踏まないことの反映)。

### GitGuardianの誤検知source除去(review Suggestion)

`scripts/tests/operator_request_channel/test_schema.py`の`test_additional_property_is_rejected`が`_base_message(password="should-not-be-a-field")`という`key="value"`形のliteralを持っており、公開リポジトリに対するGitGuardianが「Generic Password」として誤検知した(検知された値は文字列`should-not-be-a-field`そのもので、実在の資格情報ではない)。このテストが確かめているのは「schemaが未知のフィールドを拒否すること」であり、フィールド名が`password`である必然性は無かったため、`unexpected_field`という中立な名前へ変更した。テストの意図(additionalPropertiesによる拒否)・強度(拒否されることのアサーション)は変えていない。

`_fixtures.py`の断片組み立て方式(secretを実行時に非literalな形で組み立てる)は変更していない -- 依頼文の指示どおり。

**同種literalの横断確認**: `password=`/`secret=`/`token=`(`key="value"`形および`"key": "value"`形の両方)を`scripts/tests/operator_request_channel/`と`roles/operator_request_channel/`全体へ`grep`し、`_fixtures.py`以外に該当するliteralは上記1件のみだったことを確認した。`password`/`secret`/`token`/`credential`を含む他の一致箇所(`test_dlp.py`のカテゴリ名文字列、`_fixtures.py`自身の断片組み立て呼び出し、`ids.py`の標準ライブラリ`secrets`モジュール名、docstring中の説明文など)はいずれも`key=value`/`key: value`という資格情報の見た目を持たないことを個別に確認した(§6参照)。

---

## 4. requirement/planとの食い違いを発見し、狭い方(安全側)を採った箇所

### 4.1 plan §2.3の表と説明文の矛盾(inbox ACL、当時の経緯)

**この節は当時の判断の経緯としてのみ残す。理由づけは§3で訂正済みであり、ここでは繰り返さない。**

plan本文 `2026-08-08_002_plan.md` の当初の表は `inbox/` へ `default u:dev-investigate:r` を挙げていたが、直後の説明文は「`inbox` に `dev-investigate` の read を与えない」と明記しており、両者は矛盾していた。この実装は説明文(狭い方、`dev-investigate`向けのdefault readエントリを与えない側)を採用し、`roles/operator_request_channel/defaults/main.yml`の`operator_request_channel_acl.inbox.default_entries`に`dev-investigate`のエントリを含めなかった。

**この採用判断(ACLの具体的な設定)自体は、その後のrwx化・理由づけ訂正(§3)を経ても変わっていない** — dev-investigate向けのdefault readエントリを与えない、という設定は今も正しい(他identityの書いた本文を読めないという実際に守るべき性質を、このエントリの不在が支えている)。訂正されたのは、この判断を下した**当時の理由づけ**(「提出側は自分の提出物を読み返す必要がない」を「読めない」という安全根拠であるかのように記述していた点)であり、**設定そのものではない**。

`defaults/main.yml`のACL定義ブロックは、この経緯を繰り返さず、現在の正しい理由づけ(§3参照)だけを記載する形に書き直した。plan本文側の当初の矛盾は、その後Coordinatorがplan §2.3を実測に基づいて改訂したことで解消されている。

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

- `python3 scripts/tests/operator_request_channel/run-tests.py -v`: **324件全てPASS**(Implementer Aの162件 + 本担当162件)。実行環境はansy相当のローカル環境、`python3.14.4`。同時実行テスト(`MarkExpiredIfNeededConcurrencyTests`)はフレーク耐性を見るため単独で12回連続実行し、全回成功を確認した。
- **umask依存是正(review `_013_review_event_mode.md` Critical 1)の確認**: `test_event_file_acl_mask.py`へ追加した`EventFileModeIsUmaskIndependentTests`(2件)と`AppendToExistingEventFileNeverAttemptsChmodTests`(1件)、計3件で以下を確認した。(a)umaskを`022`(グループ書き込みビットを削る値)へ実際に変更した状態で`store.append_event()`を呼び、結果のACL maskが`rw-`のまま(切り詰められない)こと。(b)`os.fchmod()`自体は(ACLの有無に関係なく)umaskの影響を受けないこと。(c)同じumask `022`が、default ACLの絡まない普通のファイル作成では`0o660`を確実に`0o640`へ切り詰めること(umaskがこのプロセスで実際に機能していることの対照実験)。(d)`os.fchmod()`が、あるrequest_idへの1回目の`append_event()`(新規作成)でのみ呼ばれ、2回目以降(追記)では呼ばれないこと(`mock.patch("os.fchmod", wraps=os.fchmod)`で呼び出し回数を検証、追記側が`EPERM`を踏まない設計の担保)。umaskはプロセス全体に影響する値のため`addCleanup`で確実に元へ戻し、他テストへ漏れないことを確認した。**是正前に実際に失敗することの確認**: `append_event()`を一時的に是正前(`O_CREAT | O_APPEND`単発、fchmodなし)へ戻し、(d)のテストが実際に失敗する(fchmod呼び出し回数が0のまま)ことを確認したのち、是正版へ戻して成功することを確認した。**正直に記録する限界**: (a)のテストは、是正前のコードでもこのsandboxでは成功してしまう(§3で記載した通り、このカーネル上ではdefault ACLが絡む`os.open()`のumaskによる切り詰めそのものを再現できなかったため)。旧/新の判別ができるのは(d)のみであり、(a)(b)(c)は「umaskに依存しない」という要求仕様そのものの検証として位置づけている。
- **events/ ACL mask是正の確認**: `test_event_file_acl_mask.py`(5件、`setfacl`/`getfacl`を実際に使う)が、(a)`store._EVENT_FILE_MODE`(定数そのものを参照、値をハードコードし直していない)で作成したファイルの`mask`が`rw-`になり`#effective:r--`の切り詰めが出ないこと、(b)`0o640`で作成すると`mask::r--`・`#effective:r--`が実際に再現すること、(c)`group::`/`other::`が是正前後で完全に一致すること(広がっていないこと)、(d)`inbox`/`outbox`のmessageファイルは`0o440`のままで必要な`r`をちょうど満たすこと、(e)`audit.jsonl`は既存ファイルへの`setfacl -m`という別経路のためこの罠に該当しないこと、を実測で確認した。**是正前に実際に失敗することの確認**: `store._EVENT_FILE_MODE`を一時的に`0o640`へ戻し、`test_the_actual_store_event_file_mode_is_not_capped_to_read_only`が実際に失敗する(`mask::r--`のまま)ことを確認したのち、`0o660`へ戻して成功することを確認した。
- **根本例外の可視化(errno・クラス名)の確認**: 3エントリポイントそれぞれへ`test_root_cause_class_name_and_errno_survive_a_wrapped_exception`を追加した。`store.append_event()`が実際に使う形(`except OSError as exc: raise StoreError(...)`、Pythonの暗黙連鎖`__context__`を利用)で`PermissionError(13, "Permission denied")`を`StoreError`越しに送出し、stderrに外側クラス名(`StoreError`)・根本原因クラス名(`PermissionError`)・`errno=13`のすべてが現れること、かつ例外メッセージ本文(`"Permission denied"`・`"cannot open event log"`)がstdout/stderrいずれにも一切現れないことを確認した。既存の疑似secret混入テスト(差し戻し2回目で追加)も是正後の出力形式で引き続き全件成功することを確認済み(§3参照)。
- **配備後検証item 1・2の是正確認**: (a)`test_capacity_no_content_read.py`(5件)が、`count_and_size()`/`check_capacity()`が容量検査のためメッセージファイルの`open()`を一切呼ばないこと、かつ保存件数・総容量の上限自体は引き続き正しく機能する(超過でStoreCapacityExceeded、範囲内で成功)ことを確認した。**限界(依頼文の許容どおり明記)**: このセッションには第2のOS uidが無く、`inbox`の実際の権限境界を直接再現するテストは書けていない -- 検査したのは「コードが本文readに依存しない」という設計レベルの性質であり、ACLそのものの実測はCoordinatorがansy上で行った測定(plan §2.3)に依っている。(b)`UncaughtExceptionSafetyTests`(3エントリポイントそれぞれに追加、計19件)が、`_dispatch()`内の想定外例外(`store.check_capacity`/`store.append_event`/`store.read_message`/`canonical.content_hash`/`_run_ssh`等をモックしてRuntimeError・実際に発生したPermissionErrorを注入)がstdout/stderrへ`Traceback`の文字列を一切出さないことを確認した。`SystemExit`(`denied:`)経路が誤って握りつぶされていないことも別テストで確認した。
- **Operatorレビューの3件の是正確認**: ①**共通化**: 3エントリポイントそれぞれに`test_uses_the_shared_run_entrypoint_safety_net`を追加し、`main()`が`oprc.lifecycle.run_entrypoint()`を実際に呼ぶこと(`_dispatch`を第一引数として渡すこと)をモックの呼び出し検証で確認した -- 個別`try/except`が復活していないことの機械的な担保。②**count_and_sizeのdocstring**: 目視で確認(store.pyはコードでもテストでも既にこの不変条件を守っており、今回はdocstringへの明文化のみ)。③**「読めない」記述の除去**: `grep -rn`で`roles/operator_request_channel/`と本記録全体を走査し、「dev-investigateはinboxの本文を読めない」の類の主張が(訂正の説明として引用している箇所を除き)残っていないことを確認した。
- **例外メッセージ本体への疑似secret混入テスト(Operator指摘)**: 3エントリポイントそれぞれへ`test_exception_message_body_containing_a_pseudo_secret_is_not_leaked`/`test_permission_error_message_body_containing_a_pseudo_secret_is_not_leaked`(計6件)を追加した。`_fixtures.password_keyvalue_text()`/`_fixtures.slack_bot_token()`で生成した疑似secretを例外の**メッセージ本体**(`str(exc)`に現れる部分)へ直接埋め込み、stdout・stderrいずれにもその文字列が現れないことを確認した -- 既存のクラス名ベースの注入テストとは異なる観点(メッセージ本体)を明示的に検査する。
- **是正②が実際にバグを再現・解消することの検証**: `oprc-receive`の`main()`を一時的に是正前(`_dispatch(argv)`を直接呼ぶだけ)へ戻し、`UncaughtExceptionSafetyTests`のうちRuntimeErrorを注入するテストが**テスト自身がエラーとして失敗する**(生tracebackが実際に伝播し、注入したマーカー文字列が例外として飛び出す)ことを確認したのち、是正版に戻して同じテストが成功することを確認した(§3参照)。
- review Suggestion 2の是正が実際にバグを再現・解消することを、ロック無しの旧実装へ一時的に戻して同じテストが8回連続で失敗し(`InvalidTransition`/`StoreInconsistent`)、ロック付き実装に戻すと8回連続で成功することを確認した(§3参照)。
- `ansible-playbook --syntax-check` を両playbookに実行し、いずれもエラーなし。
- `ansible-lint playbooks/operator_request_channel_{client,server}_setup.yml`: `Passed: 0 failure(s), 0 warning(s) in 7 files processed`。
- `scripts/check-tester-gate.sh`: `[tester-gate-lint] OK (54 playbooks)`。
- `gitleaks detect --no-git`を対象パス(role本体・playbook・test・変更した既存4ファイル)へ個別に実行し、いずれも `no leaks found`。差し戻し是正で変更した6ファイル(`oprc/lifecycle.py`・`bin/oprc-receive`・`bin/operator-channel`・test 3本)についても同じ検査を再実行し、`no leaks found`を再確認した。events/ ACL mask是正・根本例外可視化(改訂4)で変更した6ファイル(`oprc/store.py`・`oprc/lifecycle.py`・test 4本)についても同じ検査を再実行し、`no leaks found`・IPv4ヒット0件を確認した。この改訂ではAnsible YAMLを変更していないため`--syntax-check`/`ansible-lint`/`check-tester-gate.sh`は再実行のみ(結果は前回と同じ、エラー無し)。
- IPv4リテラル検査: `scripts/git-pre-commit-check.sh`と同じ正規表現(`([0-9]{1,3}\.){3}[0-9]{1,3}`、127.0.0.1/0.0.0.0/255.255.255.255は除外)を対象ファイル全文へ適用し、ヒット0件(差し戻し是正分も同様)。DLP fixtureは`_fixtures.py`の断片組み立てのみを使用し、疑似secret・private IPの完成形をファイルへ書いていない。
- **GitGuardian誤検知source除去の確認**: `grep -rnE`で`password=`/`secret=`/`token=`(`key="value"`形・`"key": "value"`形の両方)を`scripts/tests/operator_request_channel/`・`roles/operator_request_channel/`全体へ適用し、`_fixtures.py`の断片組み立て呼び出し以外に該当するliteralが残っていないことを確認した(§3参照)。`test_schema.py`の該当テストは`unexpected_field`への改名後も同じアサーション(additionalPropertiesによる拒否)で成功することを324件の全体実行に含めて確認した。
- **今回変更した5ファイル**(`oprc/store.py`・`test_event_file_acl_mask.py`・`test_schema.py`、および前回までの変更を含む差分全体)へ`gitleaks detect --no-git`と上記IPv4正規表現を再実行し、いずれも`no leaks found`・ヒット0件を確認した。この改訂ではAnsible YAMLを変更していないため`--syntax-check`/`ansible-lint`/`check-tester-gate.sh`は再実行のみ(結果は前回と同じ、エラー無し)。
- 変更/新規のYAML全ファイルを`yaml.safe_load_all`で構文検査し、全件OK。
- `roles/deployment_drift_check`へ足した3クラスが実際にfindingを立てることを、`hosts: localhost, connection: local`の使い捨てplaybook(`docs/ai/core.md`のdecoy inventory相当、実ホスト非接触)で7ケース(owner/group/mode一致・3属性不一致・path欠落・sudoers空・sudoers該当・probe正しく拒否・probe誤って許可)すべて確認した。実ホストの状態は一切変更していない。
- `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh`の既存25本について: `git diff --stat`で**追加58行・削除0行**であることを確認(既存armは1文字も変わっていない)。加えて、新設4本の arity/形式/allowlist外拒否のテストと、既存armのうち quory 固有パスに依存しない6本(disk/load/failed/ports/journal-system/deployed-hash)をこのホスト上でローカル実行するサンプル非回帰テストを`test_dispatcher.py`に含めた。
- DLPの4検査点すべてで同一fixtureが拒否されることを、実際に4つの入口(ansy送信前・quory受入前・quory持ち出し前・ansy取り込み前)を通す統合テスト(`test_dlp_blocks_the_same_fixture_at_all_four_inspection_points`)で確認した。
- request_id衝突時に上書きされず後着が拒否されること(§16「同時submit時にもrequest ID衝突…が起きない」の実測可能な部分)を、`ids.generate_request_id`を固定値へ差し替えて2回submitするテストで確認した。
- **監査指摘1(preflight)の是正確認**: `hosts: localhost, connection: local`の使い捨てplaybookで`operator_request_channel`role(`tasks_from: client`)を`--check`付きで実行し、(a)実際のpython3(3.14.4)では preflight が`ok`となり後続taskへ進むこと、(b)`PATH`をscratchpad配下の偽`python3`(常に旧versionを返して`exit 1`)へ一時的に差し替えるとpreflightの`assert`taskで即座に`fatal`となり後続の全taskが実行されないことを確認した。両ケースとも`--check`付きで実行しており、preflight task自体は`check_mode: false`のため実際に走ることを確認した(§3参照)。実ホストへは一切接続していない。
- `roles/operator_request_channel/tasks/common.yml`変更後の`ansible-playbook --syntax-check`・`ansible-lint`・`scripts/check-tester-gate.sh`を再実行し、いずれも変更前と同じ結果(エラー無し)であることを確認した(上記と同じコマンド、変更後に再実行)。
- **`docs/ai/roles/operator.md`は今回の改訂2で一切変更していない。** Coordinatorが本記録とは別に同ファイルを書き換え、運用の記述を`docs/ai/context/operations/operator-request-channel.md`へ移設したため、その内容についてはこの記録の検証対象から外す(§1「先行担当の主張を現物で確かめずに引き継がない」と同じ理由で、他Agentの変更を自分の成果物として扱わない)。
- **改訂3(配備後検証是正)の検証**: 変更した8ファイル(`defaults/main.yml`・3エントリポイント・新規/既存test 4本)へ`gitleaks detect --no-git`と`scripts/git-pre-commit-check.sh`と同じIPv4正規表現を再実行し、いずれも問題なし(`no leaks found`、IPv4ヒット0件)。`ansible-playbook --syntax-check`・`ansible-lint`・`scripts/check-tester-gate.sh`も`defaults/main.yml`変更後に再実行し、変更前と同じ結果(エラー無し)を確認した。`git status`で`roles/operator_request_channel/`が(この改訂の時点で)既にgit管理下にあることを確認したが、`git add`/`commit`/`push`はこのセッションでは一切行っていない。`.claude/settings.json`・`docs/ai/reviews/operator_request_channel/2026-08-08_002_plan.md`はいずれもCoordinatorが別途変更したものであり、この改訂でも触れていない。

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

1. ~~§4.1のplan/prose矛盾(inbox ACLのdefault entry)~~ **plan本文が修正済み(2026-08-08、配備後検証を経てCoordinatorがplan §2.3を改訂)。** 当初の表記矛盾は解消され、実測に基づく新しい記述(ディレクトリは`rwx`、default ACLに dev-investigate 向け read エントリは無い)へ置き換わっている。**この節・§3の是正後の理解では**、それでも守られるのは「dev-investigateが他identityの書いた本文を読めないこと」であって「dev-investigate自身が書いた本文を読めないこと」ではない(所有者権限で読めるため) -- inboxは越境読み取りの対象が無い、outbox/config等は他identity(Operator/root)所有のため引き続き保護される。
2. **§4.2のdeployment_drift_checkカタログ形状**(1エントリ vs ホストごと2エントリ)。挙動は変えず「直し方」の正しさを優先した判断であり、Reviewerに妥当性を確認してほしい。
3. **`docs/ai/context/operations/code-delivery-to-production.md`は未変更。** plan §3.2はこのファイルの`deployed-hash`対応表更新も挙げているが、依頼文の「既存ファイルへの変更(この4つだけ)」表に含まれていないため触れていない。**併せて、既存dispatcherの`deployed-hash`コマンド自体にも`oprc-receive`/`operator-channel`を追加していない**(§10で25本のarmを変えない制約に抵触するため意図的)。配備物のhash検証は`deployment_drift_check_files`カタログ側で完結しており機能的な穴は無いが、`deployed-hash`対応表とこの文書のどちらを更新するかはCoordinatorの判断範囲として残す。
4. 先行記録が挙げていた未解決事項のうち、本担当が引き継がなかったもの(`check_capacity`→`create_message`間の粗い競合防御、DLPの正規表現ヒューリスティックの限界、naive datetimeの扱い)はライブラリ層の範囲でありエントリポイント側からは変更していない。
5. ~~`max_clock_offset_seconds`はconfigのオプションキー…既定値どうしが一致しているため動作は正しい~~ **是正済み(2026-08-08、review Suggestion 1)。** 両entry pointは`config.assert_time_synced(max_offset_seconds=cfg.get("max_clock_offset_seconds", 60.0))`を呼ぶよう変更し、設定値が実際に判定へ渡ることをテストで確認した(§3参照)。設定項目は削除していない。
6. **`expired`イベントの同時二重付与によるrequest恒久破損は是正済み(2026-08-08、review Suggestion 2)。** `oprc/lifecycle.py`にrequest_idごとのadvisory lock(`_events_file_lock`)を追加し、`mark_expired_if_needed`だけでなく`accept-request`/`reject-request`/「answered」追記も同じロック経由(`append_event_locked`)に統一した。修正前に実際に失敗し修正後に成功することをテストで確認済み(§3参照)。**残る制約**: ロックはローカルファイルシステム前提(quoryのspoolはローカルディスクのため現状は問題ない)。将来`store.append_event()`を直接呼ぶ新しい呼び出し箇所を足す場合は、既存requestへの遷移追記である限り`append_event_locked()`経由にすること。`check_capacity`→`create_message`間の競合(先行記録の既知の制約)は今回の対象外で未解決のまま。
7. **実配備は行っていない。** quoryへの`git pull`、`SEMI-SAFE: Semaphore templates setup`の実行、server setup templateの登録・実行はいずれも本セッションの範囲外(plan §5)。
8. **plan §1のquory Python版preflight assertは是正済み(2026-08-08、監査`_009_audit.md`指摘1)。** `roles/operator_request_channel/tasks/common.yml`の先頭に追加し、client(ansy)側にも同じ担保を及ぼした。`--check`実行時にもスキップされないこと(`check_mode: false`)、および実際にrc!=0で配備前にplayが停止することの両方を、`hosts: localhost, connection: local`の使い捨てplaybookで確認済み(§3・§6参照)。監査指摘2(`.gitignore`変更の記帳)・指摘3(Phase 3カタログI-1不変条件への注記)は、監査自身が「クローズを妨げない」「Coordinatorの担当」としており、本担当のこの改訂では対応していない。
9. **配備後検証item 1(submitのPermissionErrorクラッシュ)・item 2(未捕捉例外の生traceback漏出)は是正済み(2026-08-08、`_010_deploy_verification.md`)。** item 1はplan §2.3のACL改訂(inboxを`wx`→`rwx`)、item 2は`oprc/lifecycle.py`の共通`run_entrypoint()`で対応した(§3参照)。**依頼文が明示的に許容した限界**として、第2のOS uidが無いため`inbox`の実際の権限境界そのものをこのセッションのテストで再現することはできず、`test_capacity_no_content_read.py`は「容量検査がファイル内容readに依存しない」という設計レベルの性質のみを検証している(§6参照)。item 3-7・22・23・25・26(Operator操作・Semaphore実行を要するもの)は本セッションでも未判定のまま(Operatorセッション起動・Semaphore実行はYoshinobu側の操作を要するため)。
10. **quory側Operatorレビューを受けた3件の追加是正(2026-08-08、本改訂)。** ① 3エントリポイントに複製していた`try/except`を`oprc/lifecycle.py`の`run_entrypoint()`1箇所へ統合した。② `store.count_and_size()`のdocstringへ「message本文を`open()`してはならない」という不変条件を明記した(store.pyはImplementer Aの実装だが、この1点はCoordinator/Operatorの明示指示により本担当が変更した)。③ 「dev-investigateはinboxの本文を読めない」という成立しない主張を、本記録(§3・旧§4.1)・`oprc/lifecycle.py`のdocstring・`oprc-receive`のコメント・`defaults/main.yml`のACLコメントのすべてから除去し、正しい性質(「他のidentityが書いた本文を読めない」、inboxには越境読み取り対象がそもそも無い)に置き換えた。`read_state_from_events()`を使うという設計判断そのものは変えていない。例外メッセージ本体に疑似secretを埋め込むテストを新設した(§6参照)。
11. **配備後の縦方向試験で見つかったaccept-requestの`StoreError`失敗は是正済み(2026-08-08、前回改訂)。** 原因はPOSIX ACLのmask機構(`events/`のdefault ACLが与える`rw`が、ファイル作成モードのgroupビットによって実効`r`へ切り詰められていた)。`oprc/store.py`の`_EVENT_FILE_MODE`を`0o640`から`0o660`へ変更し、`setfacl`/`getfacl`による実測で是正前に再現・是正後に解消することを確認した(§3・§6参照)。他のファイル種別(message/quarantine/audit)は同じ実測で「変更不要」と確認済み(表は§3)。あわせて、`lifecycle.run_entrypoint()`が根本例外のクラス名と`errno`を出力するよう改良した(監査記録への保存は設計判断として見送り、理由は§3参照)。**残る制約**: `_MESSAGE_FILE_MODE`/`_AUDIT_FILE_MODE`が将来変更される場合、または新しいspoolファイル種別が追加される場合は、同じPOSIX ACL maskの罠に該当しないか`test_event_file_acl_mask.py`と同じ手法(`setfacl`/`getfacl`によるローカル実測)で確認すること -- この案件がそうだったように、書き込みモードの数字だけを見て安全かどうかを判断しない。**ただし項目11の是正だけでは`events/`の作成が依然umaskの影響を受けうることが後続review(`_013_review_event_mode.md` Critical 1)で判明し、項目12で追加是正した。**
12. **`events/<id>.jsonl`作成がumaskに依存する欠陥(review `_013_review_event_mode.md` Critical 1)、およびGitGuardian誤検知source、いずれも是正済み(2026-08-08、本改訂)。** 前者: `_EVENT_FILE_MODE`の値だけでは`os.open()`のmode引数が呼び出し側umaskの影響を受けうる(requirement §8「作成時umaskと最終owner／group／modeを固定する」が未実装だった)。`append_event()`を`O_EXCL`で新規作成を判別し、自分が作成した場合のみ直後に`os.fchmod()`(umaskの影響を受けない)でmodeを固定するよう書き直した。既存ファイルへの追記(自分が作成していない場合)ではchmod/fchmodを一切試みない -- 依頼文が明示した通り、所有者でない側がchmodを試みると`EPERM`になるため。umaskを実際に`022`へ変更した状態での実測、および`os.fchmod()`が作成時の1回しか呼ばれないこと(追記側でのEPERM回避の担保)をモックで検証した(§3・§6参照)。**正直な限界として記録する**: このsandboxのカーネルでは、default ACLが存在するディレクトリでの`os.open()`がumaskによってACL maskまで切り詰められる現象そのものを再現できなかった(ext4・tmpfs両方で確認)。これは是正を不要とする根拠にはならない(quoryの実カーネルがこのsandboxと同じ挙動を示す保証が無く、`os.fchmod()`のumask非依存性は無条件に正しいため)、という判断過程を§3に記載した。後者: `test_schema.py`の`test_additional_property_is_rejected`が使っていた`password="should-not-be-a-field"`というliteralがGitGuardianに誤検知されたため、フィールド名を`unexpected_field`へ変更した(テストの意図・強度は不変)。`password=`/`secret=`/`token=`形の他の該当箇所が無いことをgrepで横断確認した(§3・§6参照)。
