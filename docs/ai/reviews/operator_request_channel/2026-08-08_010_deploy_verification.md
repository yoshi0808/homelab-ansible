# Operator Request Channel MVP — 配備後検証(deploy verification)

作成: 2026-08-08 / Tester(subagent)
対象: requirement §19完了条件のうち`2026-08-08_008_test_result.md`が「未判定(配備後)」として残した10項目(#1, 3-7, 22, 23, 25, 26)。配備前の検証結果はそちらが正、本記録では上書きしない。

**実行環境: ansy(このセッション自身がansy上で動作)。quoryへは既存`dev-investigate` forced command(`ssh quory-investigate "<command>"`)経由でのみ到達した。** quoryへの通常SSH、Operatorセッション起動、config書き換えのいずれも行っていない。

---

## 0. 結論(先出し)

**item 1 は FAIL。** DLP・schemaに合格する正当なOPREQでも、quoryのforced command経由の受理処理(`oprc-receive submit`)が`PermissionError`で確定的にクラッシュし、request_idが1件も発行できない。原因はACL設計(`dev-investigate`はinboxに`wx`のみでread権限を持たない)と実装(`store.count_and_size()`が容量チェックのため`os.listdir()`を呼ぶ)の不整合で、**配備のやり直しでは直らない、コード側の欠陥**。2回独立に再現し、再現性を確認した(§4)。

このバグはDLP機構そのものには影響しない(DLPは容量チェックより前で完結しており、4検査点のうち検証できた2点は正しく機能した)。ただし「経路が開通している」という前提そのものが、実際の受理(accept)に関しては成立していない。

---

## 1. 配備済みartifactとRepoのhash照合(item 26 の一部)

### 1.1 ansy側(実測・完全一致)

```
sha256sum /usr/local/bin/operator-channel-client roles/operator_request_channel/files/bin/operator-channel-client
sha256sum /etc/operator-request-channel/dlp-rules.json roles/operator_request_channel/files/dlp-rules.json
sha256sum /etc/operator-request-channel/request-schema-v1.json roles/operator_request_channel/files/request-schema-v1.json
find /usr/local/libexec/operator-request-channel -name "*.py" | (各ファイルをrepo srcとsha256sum突合)
```

結果: `operator-channel-client`本体、`dlp-rules.json`、`request-schema-v1.json`、`oprc/`配下9ファイル全てがrepoのsrcと**バイト単位で一致**。`/etc/operator-request-channel/config.json`の内容も確認した(`expected_schema_sha256`/`expected_dlp_ruleset_sha256`は上記repo一致ハッシュと同一値)。

**判定: PASS(ansy側)。**

### 1.2 quory側(dispatcherのみ実測、oprcライブラリ本体は未確認)

```
ssh quory-investigate "deployed-hash investigate-dispatch-quory"
→ 72dad521348f7169489aa0c478d6306754516337261766135e44b502fb29e9dc
sha256sum roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh
→ 72dad521348f7169489aa0c478d6306754516337261766135e44b502fb29e9dc  (一致)
```

`deployed-hash`の許可カタログ(`recovery-investigate-dispatch-quory.sh`内の`case`)には`operator_request_channel`配下のファイル(`operator-channel`本体、`oprc/*.py`、`dlp-rules.json`、`request-schema-v1.json`)が1件も含まれていない — 到達可能な読み取り操作25+4本のいずれにも、quory上のこれらファイルを直接hashする手段が無い。`roles/deployment_drift_check/defaults/main.yml`のカタログには該当エントリが`hosts:[quory]`として存在するが、これは通常のAnsible facts収集を要し、forced commandでは実行できない。

**判定: 未判定(quory側)。** 間接的な整合性の裏付けとして、§3・§4で示すとおり quory側のDLP/schema検証(`config.verify_schema_hash` / `config.load_and_verify_dlp_ruleset`)がエラーなく通過し、ansyが期待するのと同じ4カテゴリ(private_ipv4 / ipv6_ula / ipv6_link_local / pem秘密鍵相当)を実際に検出・拒否した(§4)。これは quory 側ファイルが**動作としては**期待どおりであることを示すが、ファイル内容そのもののhash一致を確認したものではない。判定に要るもの: `deployment_drift_check.yml`をquoryに対して通常Ansible経路で実行する、または`deployed-hash`カタログへ本案件のファイルを追加する。

---

## 2. 既存`dev-investigate` 25操作の非回帰(配備後実測)

```
for cmd in users status disk load memory network ports failed journal-system \
  investigation-list "report-list drift" "report-playbooks" "acl-status yoshi-home" \
  "deployed-hash worktree-sync" forced-command-keys unit-files dmesg; do
  ssh quory-investigate "$cmd"
done
```

全コマンドが期待どおりの出力・rc=0で応答した(`report-list`/`acl-status`は引数必須のため引数付きで再実行し確認)。`forced-command-keys`は引き続き1エントリのみ(鍵は増えていない)。

**判定: PASS。** `_008_test_result.md`のローカル非回帰ハーネス(全45+9ケース終了コード一致)と合わせ、既存操作の実挙動が配備後も変わっていないことを実測で確認した。

---

## 3. channel経由の読み取り往復(item 7 の機構部分)

```
/usr/local/bin/operator-channel-client list
→ {"items": [], "next_cursor": null, "excluded_count": 0}
ssh quory-investigate "operator-outbound-list"
→ {"items": [], "next_cursor": null, "excluded_count": 0}
```

client→ssh→dispatcher→`oprc-receive outbound-list`→`store.list_ids()`の全区間が実際に動作し、空のoutbox(Operatorがまだ何も作成していないため)を正しく返した。`operator-channel-client`が未知の引数(`--help`)をローカルで`denied: unknown command`として弾く(sshを一切呼ばない)ことも確認した。

**判定: PASS(read往復の機構そのもの)。** ただし取得対象となるOPRES/DEVREQが実在しないため、item 7が求める「実際にOPRES/DEVREQを取得できる」ことそのものは未判定のまま(§7参照)。

---

## 4. DLP: 疑似secret・private IP・IPv6 ULA/link-localの拒否(配備後実測)

### 4.1 checkpoint 1(ansy送信前) — `operator-channel-client submit`経由

4種類のペイロード(PEM秘密鍵疑似値・private IPv4・IPv6 ULA・IPv6 link-local)をそれぞれ個別のOPREQとして`operator-channel-client submit`へ投入。

結果: **全4件が`denied: dlp blocked this payload before it was sent`でローカル拒否**(sshは実行されない=quoryへは届かない)。stderrに検出値そのものは一切含まれない(カテゴリ名も出力されない、doc通りの最小メッセージ)。

### 4.2 checkpoint 2(quory受入前) — dispatcher直接投入(ansyのDLPを経由しない独立確認)

ansy側client(checkpoint 1)を経由せず、schema上有効な`conversation_id`/`expires_at`を付与した同型4ペイロードを`ssh quory-investigate "operator-request-submit"`で直接quoryへ送った(checkpoint 1が無くてもcheckpoint 2単体で拒否できることの確認)。

結果: **全4件が`denied: dlp blocked this payload`で拒否**。request_idは1件も発行されず、stderrに検出値は含まれない。

**判定: PASS(checkpoint 1・2とも実測)。** checkpoint 3(quory持ち出し前)・checkpoint 4(ansy取り込み前)はOperatorがOPRES/DEVREQを作成しないと踏めないため、配備後の実地確認はできていない(offlineテストでは4点とも同一fixtureで拒否されることを確認済み — `_008_test_result.md` §2)。

### 4.3 監査記録に検出値が残らないこと

`quarantine-metadata`・`audit.jsonl`を読む手段がforced commandカタログに無いため、**ファイルの中身は未確認**。`lifecycle.write_rejection()`のソースコードを読み、渡している引数が`category`/`rule_id`/`pointer`/`dlp_engine_version`/`dlp_ruleset_sha256`のみ(検出値そのものは引数に無い)であることをコードで確認した(`_008_test_result.md`と同じ確認)。今回新たに実挙動として確認できたのは「4種のペイロードが実際に拒否パスを通った」ことまでで、そのときquarantine-metadataに書かれた中身は未読。

---

## 5. 【重要】正当なOPREQの受理(item 1)— FAIL、再現性あり

### 5.1 手順

DLP・schemaの両方を通る、機密情報を含まない検証専用ペイロードを作成し、`operator-channel-client submit`で投入した(purposeに「配備後検証専用」であることを明記)。

```json
{
  "schema_version": 1,
  "type": "OPREQ",
  "purpose": "配備後検証専用リクエストです。Operator Request Channel MVPの経路開通確認のみが目的で、実対応は不要です。accept、rejectいずれでも構いません。",
  "target_names": ["quory"],
  "observed_facts": [],
  "requested_information": "対応不要です。経路とDLPの配備後動作確認のためのrequestです。",
  "evidence_references": [],
  "expected_result": "request_idが発行され、状態がsubmittedとして取得できること。",
  "unconfirmed": []
}
```

事前にこのペイロードに対し`oprc.dlp.scan()`をローカルで直接呼び、`blocked: False`(DLP合格)であることを確認した上で送信した。

### 5.2 結果(2回再現)

```
denied: Traceback (most recent call last):
  File "/usr/local/libexec/operator-request-channel/oprc-receive", line 293, in <module>
    main(sys.argv)
  File "/usr/local/libexec/operator-request-channel/oprc-receive", line 277, in main
    cmd_submit(cfg)
  File "/usr/local/libexec/operator-request-channel/oprc-receive", line 164, in cmd_submit
    store.check_capacity(cfg["spool_dir"], "inbox", cfg["max_messages_per_box"], cfg["max_total_bytes"], len(raw_bytes))
  File "/usr/local/libexec/operator-request-channel/oprc/store.py", line 188, in check_capacity
    count, total = count_and_size(spool_dir, box)
  File "/usr/local/libexec/operator-request-channel/oprc/store.py", line 163, in count_and_size
    names = os.listdir(directory)
PermissionError: [Errno 13] Permission denied: '/var/lib/operator-request-channel/inbox'
```

同一手順を2回実行し、同一の`PermissionError`を確定的に再現した。

### 5.3 原因(コードを読んで特定)

- `roles/operator_request_channel/defaults/main.yml`(69-72行目)は`inbox`のACLとして`dev-investigate`に`wx`(write+execute)のみを付与し、`r`(read)を与えない。これは意図的な設計(dev-investigateが他者の提出済みOPREQを読めないようにする、R-1関連の秘匿境界)。
- `roles/operator_request_channel/files/oprc/store.py`の`count_and_size()`(155-163行目)は容量集計のため`os.listdir(directory)`を呼ぶ。ディレクトリの列挙には`r`権限が要る(`x`だけでは個々のファイルへの到達はできても列挙はできない)。
- `check_capacity()`(`store.py` 177-189行目)は`oprc-receive`の`cmd_submit()`(164行目)から、DLP合格後・メッセージ作成前に**必ず**呼ばれる。dev-investigate identityで実行される限り、この呼び出しは`wx`のみのACLの下で**構造的に必ず`PermissionError`になる**。
- `cmd_submit()`はこの例外を`store.StoreError`系としてキャッチしておらず(139-166行目の`try/except`は`schema.ValidationError`のみを捕捉)、Pythonの生tracebackがそのまま`sys.exit`せずクラッシュし、標準エラーへ出力される。`operator-channel-client`はこの内容を「value-freeだから」という前提でそのまま中継する(`_run_ssh()`のコメント参照)が、その前提はDLP拒否メッセージについては正しくても、想定外の例外については検証されていない。

この不整合は**配備の順序や設定値の問題ではなく**、ACL設計(defaults/main.yml)と実装(store.py)の間の食い違いであり、コード修正なしに配備をやり直しても再現する。

### 5.4 影響範囲の切り分け

- **DLPチェックポイント自体は無傷**: `check_capacity()`はDLP合格後に呼ばれるため、拒否されるペイロード(§4)はこのコードパスへ到達する前に`denied:`で正しく終わる。今回の4件のDLP拒否試験・過去のDLP拒否試験がいずれも正常に完了していたのはこのため。
- **outbox・events・quarantine-metadataは同じ壊れ方をしない**: ACL定義(`defaults/main.yml` 76-102行目)で、dev-investigateは`outbox`に`rx`(read込み)、`events`に`rwx`を持つ。実際`operator-outbound-list`(`store.list_ids()`も同じ`os.listdir()`パターン)は正常に応答した(§3)。**壊れているのは`inbox`一箇所だけ**であり、これは「submitでrequest_idを発行する」経路そのもの。
- **Operator側(operator identity)は別ACLのため今回の欠陥に該当しない可能性が高い**: `outbox`へのOperatorの権限は`rwx`(69-72行目と対称的に`r`を含む)であり、reply-opres/new-devreqが`check_capacity(outbox)`を呼んでも同種のPermissionErrorにはならないと**コード上は**読める。ただしOperatorセッションを起動する手段がこのセッションには無いため、実地確認はできていない(推測であることを明記する)。

### 5.5 spoolへの残留

上記2回の試行はいずれも`store.create_message()`に到達する前に例外で終了しており、**request_idは1件も発行されず、inbox/outbox/eventsのいずれにもメッセージは作成されていない**。DLP拒否試験(§4、計8件)も設計どおりrequest_idを発行しない。**このセッションを通じてquoryのspoolへ残ったrequestは0件。**

**item 1の判定: FAIL。**

---

## 6. Semaphore server setup template(item 22, 23)

```
ssh quory-investigate "semaphore-query template-list 50"
```

結果: 登録済み52件のtemplate一覧を確認したが、`operator_request_channel_server_setup.yml`を参照するtemplateは**1件も存在しない**。`playbooks/dev_investigate_setup.yml`(`SEMI-SAFE:Dev investigate setup`)は登録済み(id=36)。

`roles/semaphore_templates/defaults/main.yml`(343-344行目)にはカタログエントリとして`operator_request_channel_server_setup.yml`(class: SEMI-SAFE)が存在し、`class`にscheduleを表すフィールドは無く、対象は`playbook`自身の`hosts: quory`に委ねる構造(§343-344近傍のコメントに設計理由あり)。

**item 22の判定: 未判定。** `SEMI-SAFE: Semaphore templates setup`がまだ実行されておらず、Semaphore側にこのtemplateが登録されていないことを実測で確認した。判定に要るもの: Yoshinobuまたは承認済み手順による同templateの実行。

**item 23の判定: 未判定。** 未登録のため「登録されたtemplateが〜」を確認する対象が存在しない。カタログ定義自体(quory限定・schedule非対応)は構造として確認済み(コード確認、実測ではない)。

**観察(判定に影響しない)**: quory側のserver setup自体(ファイル配備、§1.1参照相当)はこのtemplate登録より前に別経路で完了している(タスク冒頭のCoordinator報告どおり)。これは`docs/ai/context/operations/operator-request-channel.md`が明記する「template登録(押すもの#1)と実際のserver setup実行(押すもの#2)は別物」という設計と矛盾しない — 今回はテンプレート登録を経ずに配備が行われた、という運用上の事実であり、要求仕様が禁止する経路(自動起動等)には該当しない。

---

## 7. request IDを指定したOperator起動、accept/reject、OPRES/DEVREQ作成(item 3-6)

**判定: 未判定(Operatorセッション後)。** quory上でOperatorセッション(`operator-channel`ローカルCLI)を起動する手段がこのセッションには無い(タスク前提のとおり)。

- item 3(user起動): 未判定。
- item 4(list-pending/show-request/accept/reject): 未判定。ただし`list-pending`はinboxを読む操作であり、Operator identityはinboxに`rx`(69-73行目)を持つため、§5のバグには該当しないと**コード上は**読める(未検証)。
- item 5(OPRES作成): 未判定。§5.4のとおりOperatorのoutbox権限は`rwx`でありチェックポイント自体は通る可能性が高いが未検証。
- item 6(standalone/reply DEVREQ作成): 同上、未判定。

判定に要るもの: Yoshinobuによるquory上のOperatorセッション起動と、そこでの`list-pending`/`accept-request`/`reply-opres`/`new-devreq`の実行結果。

---

## 8. ansyのOPRES/DEVREQ取得(item 7)

**判定: 未判定。** §3で確認したとおりread往復の機構(client→ssh→dispatcher→oprc-receive→store)自体は動作するが、取得対象となるOPRES/DEVREQが1件も存在しない(§7の未判定と表裏)。判定に要るもの: Operatorが作成した実際のOPRES/DEVREQ。

---

## 9. Semaphore UI経由でのserver setup実行(item 25)、配備済みartifactのhash照合quory側(item 26後半)

**item 25の判定: 未判定。** quory上にserver setup相当のファイル一式が存在し、dispatcherのhashもrepoと一致することは実測した(§1.2・§2)が、それが「Yoshinobuが登録済みtemplateをSemaphore UIから明示実行した」結果であることをこのセッションから確認する手段がない(実行履歴・Semaphore task履歴を読む到達可能な操作が無い)。判定に要るもの: Semaphore側のtask実行履歴、またはYoshinobu自身の申告。

**item 26の判定: PASS(ansy側)/未判定(quory側)。** §1参照。

---

## 10. まとめ

| # | 完了条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | ansyから既存SSH forced command経由でOPREQを登録できる | **FAIL** | §5。`PermissionError`で確定的に再現(2回)。ACL(`defaults/main.yml`)と実装(`store.py`)の不整合 |
| 3 | userがrequest IDを指定してquoryでOperatorを起動できる | 未判定 | Operatorセッション起動手段なし |
| 4 | Operatorがpending requestを一覧・取得・accept/rejectできる | 未判定 | 同上 |
| 5 | OperatorがOPRESを作成できる | 未判定 | 同上 |
| 6 | Operatorがstandalone DEVREQおよび返信DEVREQを作成できる | 未判定 | 同上 |
| 7 | ansyがOPRES/DEVREQをread-onlyで取得できる | 未判定 | 機構は実測PASS(§3)、対象データが無い |
| 22 | 既存の`SEMI-SAFE: Semaphore templates setup`でserver setup templateを登録・更新できる | 未判定 | 未実行を実測確認(§6) |
| 23 | 登録されたtemplateがquoryだけを対象とし、scheduleを持たない | 未判定 | #22未実行のため対象なし。カタログ定義は構造確認済み |
| 25 | Yoshinobuが登録templateをSemaphore UIから明示実行して配備できる | 未判定 | 配備結果は実測確認、実行経路(Semaphore UI)の確認手段なし |
| 26 | 配備済みartifactとRepoのhashを照合できる | **PASS(ansy)/未判定(quory)** | §1。ansyは全ファイルバイト一致、quoryはhash読み取り手段がカタログに無い |

**FAIL 1件(item 1、Critical)。PASS 1件(item 26のansy側のみ)。残り8件は未判定のまま。**

---

## 11. spoolへ残したrequest

**0件。** DLP拒否試験(§4、8件)・受理試験(§5、2件)のいずれもrequest_idを発行する前に終了しており、quoryのinbox/outbox/eventsに新規メッセージは作成されていない。quarantine-metadata/audit.jsonlへは、DLP拒否試験(§4、8件相当。ansy側checkpoint 1で完結した4件を含めるとansy側では書き込みは発生しない — quorayに到達したのはcheckpoint 2向けの4件のみ)と受理試験の失敗(2件、DLP合格後だが容量チェックでクラッシュしたため`write_rejection`は呼ばれておらず、こちらも記録は残っていないと読める — `cmd_submit`のコードでは`check_capacity`の例外は`write_rejection`を経由しない生の例外なので、quarantine-metadataにも書かれていない可能性が高い、未確認)相当のイベントが残っている可能性があるが、内容を読む手段がないため件数・中身とも未確認。

---

## 12. 未実施項目とその理由

| 項目 | 理由 |
|---|---|
| item 3-6(Operator操作全般) | quory上でOperatorセッションを起動する手段がこのセッションに無い |
| item 7の実データ取得 | 取得対象のOPRES/DEVREQが存在しない(item 5・6が未判定のため) |
| item 22・23の完全な実測 | `SEMI-SAFE: Semaphore templates setup`の実行はこのセッションの範囲外 |
| item 25の実行経路確認 | Semaphore task実行履歴を読む到達可能な操作がない |
| item 26のquory側hash直接照合 | `deployed-hash`カタログに本案件のファイルが1件も無く、`deployment_drift_check`は通常Ansible経路を要するためforced commandでは実行できない |
| quarantine-metadata/audit.jsonlの中身確認 | 読み取りに対応するforced commandが存在しない |
| DLP checkpoint 3・4の配備後実地確認 | Operatorが作成したOPRES/DEVREQが存在しないため踏めない(offlineテストでは4点とも確認済み) |

## 13. 残存リスク

1. **item 1のFAILは即座に開発側へ差し戻すべき欠陥。** 現状のACL設計のまま`store.check_capacity()`を使い続ける限り、dev-investigate identityからのOPREQ submitは恒久的に失敗する。修正方針の候補(判断はCoordinator/Implementerに委ねる): (a) inboxのACLへdev-investigateの`r`を追加する(ただしrequirement §7.1・R-1が意図する「submitterは他者のOPREQを読めない」秘匿境界を弱める可能性がある、要検討)、(b) 容量チェックを`os.listdir()`に依らない方式(別途カウンタファイル・events側の集計等)に変更する、(c) `check_capacity()`の`PermissionError`を`store.StoreError`として明示的に捕捉し、fail closed(`error:`)として安全に落とす応急処置(根本解決ではないが、生tracebackの漏出だけは止められる)。
2. **生tracebackがstderrへ出る経路がある**ことを実地で確認した。今回のケースでは検出値(秘密情報)は含まれていなかったが、`operator-channel-client`の「相手のstderrはvalue-freeだから中継してよい」という設計上の前提(モジュールdocstring)は、想定外の例外については保証されていない。他の未捕捉例外パスが無いか、oprc-receive/operator-channel全体の棚卸しが望ましい。
3. **item 3-7・22・23・25・26(quory側)は今回も未判定のまま。** Operatorセッション・Semaphore実行の両方ともYoshinobu側の操作を要する。item 1が直らない限り、item 3-7の実地確認(標準的なOPREQ→accept→OPRES往復)は成立しない可能性がある(Operator起点のstandalone DEVREQ(item 6)はこの制約を受けない)。
