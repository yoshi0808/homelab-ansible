# implement: Operator Request Channel MVP — 共通ライブラリ層

作成: 2026-08-08 / Implementer A(subagent)
requirement: `2026-08-08_001_requirement.md`(正本)
plan: `2026-08-08_002_plan.md`
対象: plan §3.1 の Step 3(共通ライブラリ + schema + DLPルールセット + ライブラリ層 offline test)

エントリポイント(`operator-channel-client` / `oprc-receive` / `operator-channel`)、dispatcher、Ansible role/playbook、ドリフト検査、Semaphoreカタログは対象外(plan Step 4、別担当)。

---

## 1. 対象パス

| path | 内容 |
|---|---|
| `roles/operator_request_channel/files/oprc/__init__.py` | バージョン定数のみ |
| `roles/operator_request_channel/files/oprc/canonical.py` | canonical JSON・内容hash |
| `roles/operator_request_channel/files/oprc/wire.py` | bytes→dict(サイズ・UTF-8・重複key・非有限数・階層深度) |
| `roles/operator_request_channel/files/oprc/schema.py` | JSON Schemaサブセットvalidator + §6.1/§6.2の関係検査 |
| `roles/operator_request_channel/files/oprc/dlp.py` | DLP engine(ruleset駆動、値を一切出力しない) |
| `roles/operator_request_channel/files/oprc/config.py` | config読込・schema/ruleset hash照合・時刻同期gate |
| `roles/operator_request_channel/files/oprc/ids.py` | request_id/conversation_id/attempt_id生成・検証 |
| `roles/operator_request_channel/files/oprc/store.py` | spool永続化(atomic create・append-only event・整合性検査・listing) |
| `roles/operator_request_channel/files/request-schema-v1.json` | request schema(唯一の正本) |
| `roles/operator_request_channel/files/dlp-rules.json` | DLPルールセット(12検出対象 + entropy) |
| `scripts/tests/operator_request_channel/run-tests.py` | offlineテストランナー(`unittest.discover`) |
| `scripts/tests/operator_request_channel/_path_setup.py` | テスト用sys.path設定(`test_*.py`ではない) |
| `scripts/tests/operator_request_channel/_fixtures.py` | 疑似secret/private IPの断片組立て(`test_*.py`ではない) |
| `scripts/tests/operator_request_channel/test_{wire,canonical,ids,schema,config,dlp,store}.py` | ライブラリ層 offline test、計162件 |

`roles/dev_investigate/`、`roles/deployment_drift_check/`、`roles/semaphore_templates/`、`docs/ai/roles/operator.md` 等、plan §3.2 の「既存への変更」には一切触れていない(scope外、Implementer B)。

---

## 2. 契約の充足状況

| 契約(依頼文より) | 状況 |
|---|---|
| Python 3.9+標準ライブラリのみ | 満たす。`tomllib`・サードパーティ不使用。schema/rulesetはJSON(plan §2.1 D1と同じ判断)。時刻同期のみ`chronyc`を`subprocess.run`で固定argv・シェルなし起動(config.py) |
| DLPはengine 1つ・ruleset 1つ | `dlp.py`が唯一のengine、`dlp-rules.json`が唯一のruleset。4検査点はいずれも`config.load_and_verify_dlp_ruleset()`→`dlp.scan()`という同一経路を通る設計(エントリポイントの実装はscope外だが、経路はこの2関数に一本化される) |
| §9.2 fail closed / §9.4 検出値非出力 | `dlp.scan()`は`ScanTimeout`/`RulesetError`で例外化、`Finding`は`category`/`rule_id`/`pointer`のみ保持し一致文字列を持たない(test_dlp.pyで`json.dumps(findings)`に元値が含まれないことを確認) |
| schemaはJSON側のみが正本 | `schema.py`は`request-schema-v1.json`をパースして検証するのみで、maxLength/pattern/enum等のフィールド制約をPython側にハードコードしていない。§4で自己検証した |
| §6.1 サーバー付与フィールドの上書き不可 | `schema.reject_server_assigned_fields()`が生payloadの`request_id`/`source`/`created_at`キー存在を拒否(このチェックはJSON Schemaで表現できないため意図的にコード側に置いた。理由は`schema.py`のdocstring参照) |
| 内容hashはcanonical JSONに対して決定的 | `canonical.content_hash()`。key順ソート・区切り文字固定・非ASCII直接出力・`allow_nan=False`。test_canonical.pyでkey順違い・既知sha256定数の両方を確認 |
| plan §2.9 message/event不整合はfail closed | `store.read_message()`が5条件(JSON破損・message/meta欠落・hash不一致・submitted欠落・不正遷移)を検査し`StoreInconsistent`を送出。`store.list_ids()`は不整合エントリのみ除外し件数を返す(全体を落とさない) |
| plan §2.11 時刻同期 | `config.assert_time_synced()`。固定argv・stdin閉・5秒既定timeout。5条件すべてでfail closed(test_config.py `TimeSyncTests`) |
| plan §2.4 上限・TTL | `store.check_capacity()`(件数・総容量)。TTL自体(`expires_at`の妥当性判定)はschemaのpattern制約止まりで、「最大TTLを超えるexpires_atの拒否」はエントリポイント側が`config`の`max_ttl_days`と突き合わせて判断する設計(store/schemaは値の意味を知らない) — §5「未解決事項」参照 |
| plan §2.5〜§2.7 ID・cursor・evidence形式 | `ids.py`が request_id/conversation_id/attempt_id、`store.list_ids()`がcursor形式(直前ページ最終request_id、固定ページサイズ)、evidence_referencesの形式は`request-schema-v1.json`にpattern/enumとして実装(plan §2.7の`kind`enum・`id`正規表現をそのまま反映) |
| 例外は stderr、protocol出力は stdout | ライブラリ自体は標準出力へ何も書かない(すべて戻り値/例外)。stdout/stderrの使い分けはエントリポイント側の責務(scope外)だが、ライブラリが例外メッセージに検出値を含めないことは自己検証済み |
| configを「読む側」のみ実装、defaults/templatesに触れない | `roles/operator_request_channel/defaults/main.yml`・`templates/`は作成していない。config読込側の契約を下記§3の表で規定した |

---

## 3. config キー一覧(後続担当がtemplateを書くための契約)

`oprc/config.py`の`load_config()`が実際に必須と判定するキーだけを列挙する(値そのものはtemplate側の責務)。

### 共通(ansy・quory両方、`REQUIRED_COMMON_KEYS`)

| キー | 型 | 意味 | 必須 |
|---|---|---|---|
| `config_version` | int | configスキーマの版。現在1固定を想定 | 必須 |
| `role` | string | `"coordinator"`(ansy)または`"operator_host"`(quory)。他の値は`ConfigError` | 必須 |
| `channel_enabled` | bool | plan §2.8の無効化スイッチ。`false`のときchannel操作を拒否する判断はエントリポイント側が行う(config.pyはこの値を読むだけで、真偽に応じた分岐は持たない) | 必須 |
| `libexec_dir` | string(絶対path) | 共通libexec配置先。config.py自身は使わないが、両エントリポイントが共有バイナリ/ライブラリを解決するために必須とした(plan §2.8のansy例に準拠) | 必須 |
| `schema_path` | string(絶対path) | `request-schema-v1.json`の配備先。`config.verify_schema_hash()`が読む | 必須 |
| `dlp_rules_path` | string(絶対path) | `dlp-rules.json`の配備先。`config.load_and_verify_dlp_ruleset()`が読む | 必須 |
| `expected_schema_sha256` | string(hex64) | 配備時にAnsibleがrepoのschemaから算出して埋める期待値 | 必須 |
| `expected_dlp_engine_version` | string | `dlp.ENGINE_VERSION`(現在`"1"`)と一致すべき値 | 必須 |
| `expected_dlp_ruleset_sha256` | string(hex64) | 配備時にAnsibleがrepoのrulesetから算出して埋める期待値 | 必須 |
| `max_payload_bytes` | int | `wire.parse_payload()`へ渡す上限(64 KiB以下、plan §2.8は65536) | 必須 |
| `dlp_timeout_seconds` | number | `dlp.scan()`へ渡すtimeout(plan §2.8は20) | 必須 |

### coordinator専用(ansy、`REQUIRED_COORDINATOR_KEYS`)

| キー | 型 | 意味 | 必須 |
|---|---|---|---|
| `ssh_destination` | string | `~/.ssh/config`のHost名(`quory-investigate`)。config.py自身は使わないが、client実装が必須とするため構造検証に含めた | 必須(role=coordinatorのとき) |
| `ssh_connect_timeout_seconds` | int | SSH接続timeout | 必須(role=coordinatorのとき) |

### operator_host専用(quory、`REQUIRED_OPERATOR_HOST_KEYS`)

| キー | 型 | 意味 | 必須 |
|---|---|---|---|
| `spool_dir` | string(絶対path) | `/var/lib/operator-request-channel/`。`store.py`の全関数の第1引数として渡す | 必須(role=operator_hostのとき) |
| `audit_log_path` | string(絶対path) | `/var/log/operator-request-channel/audit.jsonl`。`store.append_audit()`へ渡す | 必須(role=operator_hostのとき) |
| `max_ttl_days` | int | `expires_at`の最大TTL(plan §2.4は14)。**値の適用はエントリポイント側の責務**(§5参照) | 必須(role=operator_hostのとき) |
| `default_ttl_days` | int | `expires_at`省略時の既定TTL(plan §2.4は7) | 必須(role=operator_hostのとき) |
| `max_messages_per_box` | int | `store.check_capacity()`の`max_messages`引数 | 必須(role=operator_hostのとき) |
| `max_total_bytes` | int | `store.check_capacity()`の`max_total_bytes`引数 | 必須(role=operator_hostのとき) |
| `page_size` | int | `store.list_ids()`の`page_size`引数(plan §2.6は50固定) | 必須(role=operator_hostのとき) |

### quoryのみ・オプション(config.pyは存在を強制しない)

| キー | 型 | 意味 |
|---|---|---|
| `max_clock_offset_seconds` | number | `config.assert_time_synced()`の`max_offset_seconds`引数(既定60.0)。plan §2.8のconfig例には明記が無かったため、config.pyの必須キーには含めていない。**エントリポイントが読んで渡すか、渡さずに関数既定値(60.0)へ任せるかは後続担当の判断**として残した |

`config.load_config()`は上記の「必須」キー欠落だけを`ConfigError`にする。列挙外のキーが追加で存在してもエラーにしない(`additionalProperties`相当の拒否はしていない — configはrepo/Ansible側が生成する信頼された入力であり、`request-schema-v1.json`が守る「untrusted payloadの余剰キー拒否」とは性質が異なると判断した)。

---

## 4. 公開関数・クラス(エントリポイント実装者向け)

事前条件・戻り値・送出例外を関数単位で記す。全モジュールは`roles/operator_request_channel/files/`を`sys.path`に含めれば`from oprc import ...`で読み込める。

### wire.py

- `parse_payload(raw: bytes, max_bytes: int) -> dict`
  事前条件: `raw`はbytes/bytearray。`max_bytes > 0`。
  戻り値: JSON-native型のみで構成されるdict(重複keyなし・非有限数なし・階層は`MAX_DEPTH=8`以内)。
  例外: `TypeError`(rawがbytesでない)、`wire.WireError`(reason: `empty_payload`/`payload_too_large`/`invalid_utf8`/`invalid_unicode`/`duplicate_key`/`non_finite_number`/`invalid_json`/`not_an_object`/`nesting_too_deep`)。
  フィールド単位の形(必須・pattern等)は検査しない — `schema.validate()`の責務。

### schema.py

- `load_schema(path: str) -> dict`
  事前条件: なし。戻り値: パース済みschema dict(load時に`_check_supported`でサポート外keyword不使用を検証済み)。
  例外: `schema.SchemaError`(読込失敗・非対応keyword使用)。
- `validate(payload: Any, schema: dict) -> None`
  事前条件: `schema`は`load_schema()`が返したもの。戻り値: なし(成功時)。
  例外: `schema.ValidationError`(`.errors`は`(json_pointer, rule_name)`のリスト。**値は含まれない**)。全違反を一度に返す(最初の1件で止めない)。
- `reject_server_assigned_fields(raw_payload: dict) -> None`
  事前条件: **augmentation前の生クライアントpayload**に対して呼ぶこと(request_id/source/created_atがまだ存在しない段階)。
  例外: `schema.ValidationError`(`request_id`/`source`/`created_at`のいずれかがpayloadに存在する場合)。
- `validate_source_type_allowed(source: str, type_: str) -> None`
  requirement §4.2の許可matrix。例外: `schema.ValidationError`。
- `validate_local_relationships(message: dict) -> None`
  storeアクセス不要な§6.2ローカル則(現状: OPREQは`in_reply_to`が空であること)。例外: `schema.ValidationError`。
- `validate_reply_target(message: dict, referenced_message: dict) -> None`
  事前条件: `message["in_reply_to"] == referenced_message["request_id"]`(**呼び出し側が`store.read_message()`等で参照先を取得済みであること** — この関数はI/Oを行わない)。
  例外: `schema.ValidationError`(参照先typeが許可されない組み合わせ、または`conversation_id`不一致)。

**想定される呼び出し順**(エントリポイント実装のガイド。plan §2.1「エントリポイントは薄く、呼び出し順だけを持つ」に対応):

```
raw = wire.parse_payload(stdin_bytes, config["max_payload_bytes"])
schema.reject_server_assigned_fields(raw)
message = {**raw, "request_id": ids.generate_request_id(), "source": <entry point固定値>,
           "created_at": <受入口の時刻>, ...}
schema.validate(message, loaded_schema)
schema.validate_source_type_allowed(message["source"], message["type"])
schema.validate_local_relationships(message)
if message["in_reply_to"]:
    referenced_message, _, _ = store.read_message(spool_dir, "inbox", message["in_reply_to"])  # または outbox
    schema.validate_reply_target(message, referenced_message)
result = dlp.scan(message, ruleset, config["dlp_timeout_seconds"])
if result.blocked:
    store.write_quarantine(...); raise  # 検出値を含めずに拒否
store.check_capacity(spool_dir, box, ...)
store.create_message(spool_dir, box, message["request_id"], message, meta)
store.append_event(spool_dir, message["request_id"], "submitted", message["created_at"])
store.append_audit(audit_log_path, {...})  # request本文を含めない
```

### dlp.py

- `load_ruleset(path: str) -> dict` / `parse_ruleset(raw_text: str) -> dict`
  例外: `dlp.RulesetError`(読込失敗・JSON不正・`engine_version`不一致・rule欠損/重複/不正regex・entropy設定不正)。
- `scan(payload: dict, ruleset: dict, timeout_seconds: float) -> dlp.ScanResult`
  事前条件: `ruleset`は`parse_ruleset()`/`load_ruleset()`が返したもの(手組みdict不可 — コンパイル済み`re.Pattern`前提)。**メインスレッドから呼ぶこと**(`SIGALRM`を使うため)。
  戻り値: `ScanResult`(`.blocked: bool`、`.findings: list[Finding]`)。`Finding`は`.category`/`.rule_id`/`.pointer`のみ保持し、一致した文字列そのものは一切保持しない。
  例外: `dlp.ScanTimeout`(timeout超過、非メインスレッド、signal未対応環境)。

### config.py

- `load_config(path: str) -> dict`
  例外: `config.ConfigError`(読込失敗・非object・role不明・必須key欠落)。
- `verify_schema_hash(config: dict) -> None`
  事前条件: `config["schema_path"]`/`config["expected_schema_sha256"]`が存在。例外: `config.ConfigError`。
- `load_and_verify_dlp_ruleset(config: dict) -> dict`
  事前条件: `config["dlp_rules_path"]`/`config["expected_dlp_engine_version"]`/`config["expected_dlp_ruleset_sha256"]`が存在。
  戻り値: `dlp.scan()`にそのまま渡せるコンパイル済みruleset。例外: `config.ConfigError`。
- `assert_time_synced(max_offset_seconds=60.0, timeout_seconds=5.0, chronyc_path=CHRONYC_PATH) -> None`
  **新規`created_at`を採番する2経路(submit・Operator作成のOPRES/DEVREQ)からのみ呼ぶこと。get/list/statusからは呼ばない**(plan §2.11)。
  例外: `config.TimeSyncError`(5条件、§2参照)。

### ids.py

- `generate_request_id(now: Optional[datetime] = None) -> str` / `generate_conversation_id(...)` / `generate_attempt_id(...)`
  `now`省略時は`datetime.now(JST)`。tz-aware datetimeなら内部で`astimezone(JST)`変換する(naive datetimeを渡した場合の挙動は未規定 — `strftime('%z')`が空文字になる可能性があり、呼び出し側はtz-aware datetimeを渡すこと)。
  例外: `ids.IdGenerationError`(生成結果が自身の正規表現に一致しない、通常発生しないはずの内部異常)。
- `is_valid_request_id(value) -> bool` / `is_valid_conversation_id(value) -> bool` / `is_valid_attempt_id(value) -> bool`
  例外を投げない(非文字列や`None`も安全に`False`を返す)。

### store.py

全関数の第1引数は`spool_dir`(`config["spool_dir"]`)。`box`は`"inbox"`または`"outbox"`。

- `create_message(spool_dir, box, request_id, message: dict, meta: dict) -> None`
  事前条件: `meta["content_sha256"] == canonical.content_hash(message)`(**呼び出し側が計算すること**、この関数は検証しない)。
  例外: `store.StoreConflict`(request_id衝突)、`store.StoreError`(不正request_id/box、ディレクトリ不在等)。
- `append_event(spool_dir, request_id, event_type, occurred_at: str, extra: Optional[dict] = None) -> None`
  例外: `store.InvalidTransition`(現在状態から許可されない遷移)、`store.StoreError`(不明なevent_type)。
- `read_message(spool_dir, box, request_id) -> (message: dict, meta: dict, state: str)`
  plan §2.9の5条件をすべて検査してからしか返さない。
  例外: `store.StoreNotFound`、`store.StoreInconsistent`。
- `list_ids(spool_dir, box, cursor: Optional[str], page_size: int) -> (ids: list[str], next_cursor: Optional[str], excluded_count: int)`
  不整合エントリは結果から除外され`excluded_count`に計上される(全体は失敗しない)。
  例外: `store.StoreError`(`cursor`が不正なrequest_id形式)。
- `check_capacity(spool_dir, box, max_messages, max_total_bytes, incoming_size) -> None`
  例外: `store.StoreCapacityExceeded`。**create_messageの前に呼ぶこと**(このライブラリは予約機構を持たないため、チェックと作成の間に競合が起きても`create_message`側の`StoreConflict`/概算超過が最終防御線になる — §5参照)。
- `write_quarantine(spool_dir, attempt_id, record: dict) -> None`
  例外: `store.StoreError`(不正attempt_id)。`record`にpayload本文を含めないのは**呼び出し側の責務**(この関数は中身を検査しない)。
- `append_audit(audit_log_path, record: dict) -> None`
  `record`に本文/検出値を含めないのは**呼び出し側の責務**。

### canonical.py

- `canonical_bytes(obj) -> bytes` / `content_hash(obj) -> str`(sha256 hex) / `sha256_hex(data: bytes) -> str`
  例外なし(通常経路)。ただし`obj`に非有限floatが混入していた場合`ValueError`(`allow_nan=False`) — 通常は`wire.py`が先に弾くため到達しない想定。

---

## 5. 自己検証で確認したこと

- `python3 scripts/tests/operator_request_channel/run-tests.py -v` を実行し、**162件全てPASS**を確認した(実行はansy相当のローカル環境、`python3.14.4`。3.9互換性は構文レベルで確認 — f-string/型annotationsはPython 3.9で有効な範囲のみ使用し、`match`文・`X | Y`合併型・`tomllib`は不使用)。
- requirement §18.1のうちライブラリ層該当項目:
  - 全message typeのschema正常系・異常系 → `test_schema.py`
  - originとtypeの許可matrix → `test_schema.py SourceTypeMatrixTests`
  - standalone DEVREQと返信DEVREQ、conversationと`in_reply_to`の整合性 → `test_schema.py LocalRelationshipTests`/`ReplyTargetTests`
  - canonical JSONとhashの再現性 → `test_canonical.py`
  - duplicate key、サイズ、階層、文字コード制限 → `test_wire.py`
  - request IDとpath traversal耐性 → `test_ids.py`/`test_store.py`(`../../etc/passwd`等)
  - atomic createと同時submit → `test_store.py AtomicCreateTests.test_second_create_with_same_id_conflicts`(**単一プロセス内の逐次呼び出しでの検証。真の並行プロセス競合はOSの`os.link`原子性に依拠しており、マルチプロセスでの実測はしていない** — §6参照)
  - 状態イベントの許可遷移と不正遷移拒否 → `test_store.py EventTransitionTests`
  - DLP各検出カテゴリ(12種) → `test_dlp.py ScanCategoryTests`
  - DLP timeout、ruleset欠損、version不一致時のfail closed → `test_dlp.py TimeoutTests`/`ParseRulesetTests`、`test_config.py LoadAndVerifyDlpRulesetTests`
  - 拒否出力と監査に検出値が含まれないこと → `test_dlp.py`の`_assert_category_detected`が`json.dumps(findings)`に元値が含まれないことを毎回確認
- requirement §9.3の12種すべてにルールがあることを`test_dlp.py ParseRulesetTests.test_real_ruleset_has_all_required_categories`で機械的に確認(期待集合とruleset実物の`category`集合の完全一致を検証)。
- commit hash・request ID・conversation ID・内容hashの誤拒否なし → `test_dlp.py NoFalsePositiveTests`(実際の`request_id`/`conversation_id`/`repo_commit`フィールド値がfindingsに現れないことを確認)。**内容hashはpayloadのフィールドではなくmeta側なので、そもそも`dlp.scan()`の入力に含まれない**(§9.1の4検査点いずれも`message`のみをscanし`meta`はscanしない設計)。
- schemaの制約がJSON側のみにあること → `schema.py`を通読し、フィールド制約(pattern/maxLength/enum等)のハードコードが無いことを確認。コード側が持つのは(a)JSON Schemaの汎用interpreter、(b)§6.1のserver-assigned-field存在チェック(JSON Schemaで表現不能な提出時限定則)、(c)§4.2のsource/type matrix、(d)§6.2のローカル関係則、の4種のみで、いずれも「schemaが既に持つ制約の複製」ではない。
- config keys・公開シグネチャが実コードと一致すること → 本書§3/§4は`config.py`の`REQUIRED_*`定数、および各モジュールの実際の関数定義を読みながら書いた(コピペではなく現物照合)。

---

## 6. 未解決事項・既知の限界

1. **`scripts/tests/operator_request_channel/` は現在`.gitignore`で除外されている。**
   `.gitignore:45-46`は`scripts/tests/*`を一括ignoreし、`scripts/tests/fixtures/`(`check-doc-consistency.py`の回帰fixture)だけを明示的に復活させている。依頼文はこのpathをテスト成果物として明示指定していたが、**現状のままでは`git add`してもこのディレクトリは追跡されない**。`.gitignore`は自分の成果物パス外であり変更していない — Coordinatorの判断が必要(`!scripts/tests/operator_request_channel/`を足すか、依頼文のpath自体を見直すか)。

2. **`max_ttl_days`/`default_ttl_days`の「適用」はこのライブラリの範囲外。**
   `config.py`はこれらの値を必須キーとして要求する(構造検証)だけで、「`expires_at`が`max_ttl_days`を超えていたら拒否する」という**意味論的な検証はどこにも実装していない**。schemaは`expires_at`の書式(pattern)しか見ない。エントリポイント実装者は、提出されたpayloadの`expires_at`(またはそれを省略した場合の既定値計算)を`config["max_ttl_days"]`/`config["default_ttl_days"]`と突き合わせる処理を自分で書く必要がある。

3. **`expired`イベントの自動発行はどこにも実装していない。**
   `store.py`の状態機械は`expired`をvalidな遷移として受け付けるが、「TTLを超えたら誰が`expired`イベントを追記するか」は未実装(定期スイープはrequirement §17の除外範囲に近い性質を持つが、明示的に除外されているわけでもない)。現状、TTL超過したrequestは`read_message()`上は最後に記録された状態(`submitted`/`accepted`)のまま見え続ける。エントリポイント側で「`now > expires_at`なら`expired`として扱う」という表示上の判断を追加するか、Coordinatorに扱いを確認する必要がある。

4. **`check_capacity()`→`create_message()`間の競合は粗い防御に留まる。**
   `check_capacity()`は「作成前の確認」であり、確認と実際の作成の間に別プロセスが割り込むレース(2プロセスが同時に上限ギリギリで作成)は理論上、総容量をわずかに超過させうる。件数上限は`StoreConflict`(request_id衝突)以外の形では最終防御されない。MVPとしては許容範囲と判断したが、正確なクォータ強制が必要ならセマフォ/ロックの追加が要る(未実装)。

5. **DLPの正規表現ヒューリスティックは網羅的な秘密検出エンジンではない。**
   `dlp-rules.json`の12カテゴリは、要求仕様が挙げた最低限の検出対象を機械的に満たすよう作成した合理的な近似であり、実運用上の巧妙な難読化(例: secretを複数fieldへ分割、非標準のkey名)までは捕まえない。特に`semaphore_api_token`・`vault_plaintext`は固有のバイナリフォーマットが存在しないため、key-value文脈のヒューリスティックに依っている。requirement §9.3も「gitleaksを基礎として利用してよい」と留保しており完璧性は求めていないと判断したが、本番投入前にYoshinobuまたはReviewerによる妥当性の再確認を推奨する。

6. **`ids.generate_*(now=...)`にnaive datetimeを渡した場合の挙動は未規定。**
   `datetime.now(JST)`を経路にするため通常は問題にならないが、呼び出し側が明示的にnaiveな`datetime`を`now=`へ渡すと`astimezone(JST)`が失敗する可能性がある(Python 3.6+では naive datetimeの`astimezone()`はローカルTZとして解釈し例外にはならないが、意図しない変換になりうる)。エントリポイント実装者はtz-aware datetimeのみを渡すこと。

7. **時刻同期チェックの`max_clock_offset_seconds`はconfig必須キーに含めていない。**
   §3の表に記載の通り、plan §2.8の例に明記が無かったため任意扱いとした。エントリポイント側でconfigから読むか関数既定値(60.0)に任せるかは後続担当の判断に委ねる。

いずれも「requirementが禁止した能力を追加する」性質のものではなく、この案件の後続工程(エントリポイント実装・Review・Test)で扱うべき設計の続きとして記録した。

---

## 7. requirement/planとの食い違い

現物実装中に新たな食い違いは見つからなかった。plan §7「requirementからの逸脱と、その理由」(D1〜D3、schema/rulesetをJSON化する判断)をそのまま踏襲し、`request-schema-v1.json`/`dlp-rules.json`として実装した。
