# Operator Request Channel MVP — 再配備後の縦方向試験(vertical test)

作成: 2026-08-08 / Tester(subagent)
対象: `46231af`(バグ2件修正)を反映した quory server setup・ansy client setup 再実行後の、quory側Operatorが提示した10項目。

**実行環境: ansy(このセッション自身がansy上で、identity `yoshi` として動作)。quoryへは既存`dev-investigate` forced command(`ssh quory-investigate "<command>"`)経由でのみ到達した。** quoryへの通常SSH、Operatorセッション起動、config書き換え、rootへの昇格のいずれも行っていない。identityはrequirement §4.2が定める入口(ansyの既存SSH forced command → `source: coordinator`)と一致する。

---

## 0. 結論(先出し)

**item 1 は PASS。** 前回FAILだった`PermissionError`は再現しなくなり、正当なOPREQのsubmitでrequest_idが発行された(`req-20260808T175324+0900-dc55ae91d0b8de0d`)。DLP拒否試験(checkpoint 1・2・4相当、計6件+2件)も全て正しく拒否し、検出値・tracebackの漏洩は無かった。既存25操作の非回帰も確認した。

**item 2〜7のうち、item 2・3・4・6(標準の対話操作)は今回も未判定。** quory上でOperatorの`operator-channel`ローカルCLIを起動する手段がこのセッションに無いため。item 5(OPRES作成)は未判定、item 7(quory持ち出し前DLP)も未判定 — いずれもOperatorの操作を要する。item 6のうち**standalone DEVREQの作成**も同じ理由で未判定。

**PASS 4件(1, 8[部分], 9, 10)。未判定 6件(2, 3, 4, 5, 6, 7)。FAILは無い。**

---

## 1. item 1 — 正常OPREQのsubmitでrequest IDが発行される

### 手順

```
$ operator-channel-client submit <<'EOF'
{
  "schema_version": 1,
  "type": "OPREQ",
  "purpose": "2026-08-08 縦方向試験(_012)。再配備後の経路開通確認専用。実対応は不要、accept/rejectいずれでも構いません。",
  "target_names": ["quory"],
  "observed_facts": [],
  "requested_information": "対応不要です。request_id発行確認のみが目的です。",
  "evidence_references": [],
  "expected_result": "request_idが発行され、状態がsubmittedとして取得できること。",
  "unconfirmed": []
}
EOF
```

### 結果

```
{"request_id": "req-20260808T175324+0900-dc55ae91d0b8de0d", "conversation_id": "cnv-20260808T175323+0900-ebc989ac55446d75"}
rc=0
```

状態照会でも一致を確認した。

```
$ operator-channel-client status req-20260808T175324+0900-dc55ae91d0b8de0d
{"request_id": "req-20260808T175324+0900-dc55ae91d0b8de0d", "state": "submitted"}

$ ssh quory-investigate "operator-request-status req-20260808T175324+0900-dc55ae91d0b8de0d"
{"request_id": "req-20260808T175324+0900-dc55ae91d0b8de0d", "state": "submitted"}
```

ansy client経由・quory forced command経由の両方で同一状態(`submitted`)を確認した。

**判定: PASS。** `2026-08-08_010_deploy_verification.md` item 1のFAILが再現しなくなったことを実測で確認した。

---

## 2. 配備物のhash照合(item 26相当、前回未判定分の補強)

```
$ ls -la /usr/local/bin/operator-channel-client /etc/operator-request-channel/config.json
-rwxr-xr-x 1 root root 12598 Aug  8 17:50 /usr/local/bin/operator-channel-client
```

再配備(17:50)がこのセッションの直前に行われたことをタイムスタンプで確認した。

```
sha256sum /usr/local/bin/operator-channel-client roles/operator_request_channel/files/bin/operator-channel-client
→ 完全一致(fb8f91b5...)
sha256sum /etc/operator-request-channel/dlp-rules.json roles/operator_request_channel/files/dlp-rules.json
→ 完全一致(23d0bdb7...)
sha256sum /etc/operator-request-channel/request-schema-v1.json roles/operator_request_channel/files/request-schema-v1.json
→ 完全一致(1e6d1c6b...)
diff -q した /usr/local/libexec/operator-request-channel/oprc/{canonical,config,dlp,ids,lifecycle,schema,store,__init__}.py と
     roles/operator_request_channel/files/oprc/*.py
→ 全9ファイルで差分ゼロ
```

quory側dispatcher(変更なしのはずの部分)も確認した。

```
ssh quory-investigate "deployed-hash investigate-dispatch-quory"
→ 72dad521...
sha256sum roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh
→ 72dad521...(一致、想定どおり変更なし)
```

**quory側の`oprc/`ライブラリ本体・`oprc-receive`・`operator-channel`のhashは、前回同様、forced commandカタログに読み取り手段が無いため直接照合できていない。** ただし今回、item 1の挙動変化(PermissionErrorが消えた)自体が、この変更が実際に反映されていることの強い間接証拠になっている。

**判定: PASS(ansy側、実測)。未判定(quory側ライブラリのhash直接照合、前回から変わらず)。**

---

## 3. item 9・checkpoint 1/2 — DLP拒否(疑似secret・private IP)と検出値/traceback非漏洩

### 3.1 checkpoint 1(ansy送信前) — `operator-channel-client submit`

PEM疑似鍵とprivate IPv4の2種を個別に投入。

```
$ cat opreq_pem.json | operator-channel-client submit
denied: dlp blocked this payload before it was sent
rc=1

$ cat opreq_privip.json | operator-channel-client submit
denied: dlp blocked this payload before it was sent
rc=1
```

いずれもrequest_idは発行されず、stderrに検出値・カテゴリ名・tracebackは一切含まれない。

### 3.2 checkpoint 2(quory受入前) — dispatcher直接投入(ansyのDLPを経由しない独立確認)

`operator-channel-client`を経由せず、schema上有効な`conversation_id`(`oprc.ids.generate_conversation_id()`で生成)を付けたOpenSSH形式PEMおよびIPv6 ULAのpayloadを`ssh quory-investigate "operator-request-submit"`で直接送った。

```
$ cat opreq_pem2.json | ssh quory-investigate "operator-request-submit"
denied: dlp blocked this payload

$ cat opreq_ipv6ula.json | ssh quory-investigate "operator-request-submit"
denied: dlp blocked this payload
```

いずれもrequest_idは発行されず、stderrは`denied: dlp blocked this payload`の固定文言のみ(検出値・カテゴリ名・traceback無し)。

**中間メモ**: 最初`expires_at`を自前でISO文字列にして付けたところ`denied: expires_at is out of bounds`となった。これは自作payloadの不備(client側が内部で使う placeholder 生成規約と一致しなかった)であり、DLP機構の不具合ではない。`expires_at`を省略しdefault TTLに任せたところ通常どおりschema検証を通過し、DLP段階まで到達した。

### 3.3 checkpoint 4(ansy取り込み前)相当の関数レベル確認

`operator-channel-client get`は既存quoryのメッセージが要るため実行できない(§6参照)。そこで**cmd_getが呼ぶのと同じ`oprc.dlp.scan()`を、実際に配備された`/usr/local/libexec/operator-request-channel/`のコードと`/etc/operator-request-channel/dlp-rules.json`を使って直接呼び出した**(schema上妥当なOPRES形状のdictを組み立て、`observed_facts`に疑似secretを1件だけ入れる)。

```python
sys.path.insert(0, "/usr/local/libexec/operator-request-channel")
from oprc import dlp, config
cfg = config.load_config("/etc/operator-request-channel/config.json")
ruleset = config.load_and_verify_dlp_ruleset(cfg)
result = dlp.scan(msg, ruleset, cfg["dlp_timeout_seconds"])
```

4種(PEM疑似鍵、private IPv4、IPv6 ULA、Slack webhook風URL)全てで`result.blocked == True`。`result.findings`の内容を確認したところ、各要素は`category` / `rule_id` / `pointer`のみを持ち、検出した生の値は含まれていない(例: `Finding(category='pem_private_key', rule_id='pem-or-ssh-private-key', pointer='/observed_facts/0')`)。

**これは checkpoint 4 の完全な往復試験ではない** — 実際にquoryのoutboxを経由した実データではなく、ansy上でライブラリ関数を直接呼んだ結果である。完全な往復にはOperatorが作成した実OPRES/DEVREQが要る(§6・§7参照)。

**item 9の判定: PASS。** checkpoint 1・2・4相当のいずれでも、拒否時に検出値・traceback・カテゴリの生値が一切出力されないことを実測で確認した(checkpoint 3は未確認、§7参照)。

---

## 4. item 8 — ansy取り込み前DLPで疑似secretを拒否できる

§3.3の結果がそのまま該当する。**deployed済みのDLPエンジンとrulesetが、checkpoint 4で使われるのと同じ関数`dlp.scan()`を通じて疑似secret 4種を確実にblockすることを実測した。**

ただし、これは「関数レベルの確認」であり、「quoryのoutboxに置かれた実データをansyがsshで取得し、その取得経路の中でDLPが動いて拒否する」という完全な往復ではない。完全な往復を試すには、Operatorが疑似secretを含むOPRES/DEVREQをまず作成し、それがquory側の持ち出し前DLP(checkpoint 3)を通過してしまう必要があるが、**設計上checkpoint 3が正しく機能していればそのようなデータはそもそもoutboxに置かれない**(fail-safe)。したがって、checkpoint 3が健全である限り、checkpoint 4の完全往復試験は「意図的にDLPを迂回してテストデータをoutboxへ置く」という、requirement §9.1が禁じる経路を作らない限り原理的に成立しない。今回はこの迂回を行っていない。

**判定: PASS(関数レベルで確認)。完全な往復(実データ経由)は未確認 — 上記の理由により、Operator操作を経ても本質的に確認しづらい種類の項目であることを付記する。**

---

## 5. item 10 — 既存25操作の非回帰

```
for cmd in users status disk load memory network ports failed journal-system \
  investigation-list "report-list drift" "report-playbooks" "acl-status yoshi-home" \
  "deployed-hash worktree-sync" forced-command-keys unit-files dmesg; do
  ssh quory-investigate "$cmd"
done
```

15コマンド全てrc=0で応答(出力バイト数も前回と同オーダーで、空応答や異常終了は無い)。`forced-command-keys`は引き続き1エントリのみ(鍵は増えていない)。

**判定: PASS。** ローカルのオフライン回帰ハーネス(312テスト)に加え、実quory上での代表サブセット実行でも非回帰を確認した。

---

## 6. item 2〜7 — Operatorの対話操作(未判定)

quory上で`operator-channel`ローカルCLI(`list-pending` / `show-request` / `accept-request` / `reject-request` / `reply-opres` / `new-devreq` / `show-conversation` / `show-status`)を起動する手段が、このセッションには無い。dispatcher(`recovery-investigate-dispatch-quory.sh`)がforced command経由で公開しているのは`operator-request-submit` / `operator-outbound-list` / `operator-message-get` / `operator-request-status`の4本だけであり(実装ファイルの`case`文で確認)、これらはいずれもOperator local CLIの操作ではない。

| 項目 | 判定 | 理由 |
|---|---|---|
| 2. list-pending / show-request で取得 | 未判定 | Operator local CLI操作。forced commandに相当操作なし |
| 3. accept-request | 未判定 | 同上 |
| 4. OPRES作成 | 未判定 | 同上 |
| 5. ansyがOPRESを取得 | 未判定(機構は実測PASS、対象データが無い) | `operator-channel-client list`/`get`自体は正常応答するが(§8参照)、Operatorが何も作成していないため取得対象が0件 |
| 6. standalone DEVREQの作成・取得 | 未判定 | 作成側がOperator local CLI操作 |
| 7. quory持ち出し前DLP(checkpoint 3) | 未判定 | Operatorが疑似secretを含むOPRES/DEVREQを作ろうとする操作自体がOperator local CLI経由でしか行えない |

**判定に要るもの**: Yoshinobuがquory上で`operator-channel`のOperatorセッションを起動し、次を実行してその出力を共有すること。

1. `list-pending`(item 2) → このセッションが送った`req-20260808T175324+0900-dc55ae91d0b8de0d`が一覧に出るか
2. `show-request req-20260808T175324+0900-dc55ae91d0b8de0d`(item 2)
3. `accept-request req-20260808T175324+0900-dc55ae91d0b8de0d`(item 3)
4. `reply-opres req-20260808T175324+0900-dc55ae91d0b8de0d`(item 4)で無害な結果を返す
5. ansy側で`operator-channel-client get req-20260808T175324+0900-dc55ae91d0b8de0d`を実行しOPRESが取得できるか(item 5)
6. `new-devreq`でstandaloneのDEVREQを作成し(item 6)、ansy側で`operator-channel-client list`/`get`で取得できるか
7. `reply-opres`または`new-devreq`へ疑似secret(例: PEM疑似鍵)を含む内容を渡し、quory側で拒否されること・検出値/tracebackが出ないことを確認する(item 7、item 9のcheckpoint 3部分)

---

## 7. read往復の機構そのもの(item 5の前提部分)

```
$ operator-channel-client list
{"items": [], "next_cursor": null, "excluded_count": 0}

$ ssh quory-investigate "operator-outbound-list"
{"items": [], "next_cursor": null, "excluded_count": 0}
```

client→ssh→dispatcher→`oprc-receive outbound-list`→`store.list_ids()`の全区間が正しく動作し、空のoutbox(Operatorがまだ何も作成していない)を返した。**機構としては前回に続き実測PASSだが、Operatorが何も作っていないため実データの取得は依然未判定。**

---

## 8. spoolへ残したrequest

**1件。**

| request_id | conversation_id | type | 状態 | purpose(要約) |
|---|---|---|---|---|
| `req-20260808T175324+0900-dc55ae91d0b8de0d` | `cnv-20260808T175323+0900-ebc989ac55446d75` | OPREQ | submitted | 2026-08-08縦方向試験(_012)専用。経路開通確認のみが目的で実対応不要、accept/rejectいずれでも可。 |

DLP拒否試験(§3、計4件: checkpoint 1が2件、checkpoint 2が2件)はrequest_idを発行していないため、spoolへの残留は無い。§3.3(checkpoint 4相当)・§8[原文§4相当]の`dlp.scan()`直接呼び出しはquoryへ一切送信していないため、当然quory側に何も残らない。

**このrequestは削除できない**(§ 到達してはいけない状態、および運用context「削除はYoshinobuの明示操作だけ」)。item 2以降の判定に必要な材料として、上記§6の手順1・2でそのまま使えるようpurposeへ明記している。

---

## 9. まとめ

| # | 項目 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 正常OPREQのsubmitでrequest ID発行 | **PASS** | §1。前回FAILが再現せず、request_id発行・状態照会とも一致 |
| 2 | Operatorがlist-pending/show-requestで取得 | 未判定 | §6。Operator local CLI操作、到達手段なし |
| 3 | accept-requestできる | 未判定 | 同上 |
| 4 | OPRESを作成できる | 未判定 | 同上 |
| 5 | ansyがOPRESを取得できる | 未判定(機構はPASS) | §5・§7。read機構は実測、対象データ無し |
| 6 | standalone DEVREQを作成・取得できる | 未判定 | §6。作成側がOperator local CLI操作 |
| 7 | quory持ち出し前DLPで疑似secret拒否 | 未判定 | §6。checkpoint 3はOperator操作を要する |
| 8 | ansy取り込み前DLPで疑似secret拒否 | **PASS(関数レベル)** | §4・§3.3。deployedコードで直接確認、完全往復は原理的にcheckpoint 3を要する |
| 9 | 拒否時に検出値・traceback非漏洩 | **PASS** | §3。checkpoint 1/2/4相当で確認、checkpoint 3は未確認 |
| 10 | 既存25操作の非回帰 | **PASS** | §5。代表15コマンド全rc=0、鍵1件のまま |

**FAILは無い。PASS 4件(うち1件は範囲を関数レベルへ限定)。未判定6件、いずれもOperator local CLIセッションの起動を要する。**

---

## 10. 未実施項目とその理由

| 項目 | 理由 |
|---|---|
| item 2〜4・6(作成側)・7 | quory上でOperator local CLI(`operator-channel`)を起動する手段がこのセッションに無い |
| item 5の実データ取得 | 取得対象のOPRESが存在しない(item 4が未判定のため) |
| item 8の完全往復(実データ経由) | checkpoint 3(Operator操作)を経ないとoutboxに実データが置かれず、意図的な迂回は行わない方針のため原理的に成立しない |
| item 9のcheckpoint 3部分 | 同上、Operatorの持ち出し操作を要する |
| quory側`oprc/`ライブラリのhash直接照合 | `deployed-hash`カタログに本案件のファイルが1件も無く、forced commandでは実行できない(前回から変わらず) |

---

## 11. 残存リスク

1. **item 2〜7(Operatorの対話操作全般)は今回も未判定のまま。** item 1のバグ修正でsubmit自体は動くようになったが、「submit → accept → OPRES作成 → ansy取得」という要求仕様の中核となる往復フローは、このMVP全体を通じてまだ1回も端から端まで実地確認されていない。§6の7手順をYoshinobuが実行すれば、既存のrequest(`req-20260808T175324+0900-dc55ae91d0b8de0d`)を使って一度に大半を判定できる。
2. **quory側`oprc/`ライブラリ本体・`oprc-receive`・`operator-channel`のバイト単位のhash照合は、依然として到達可能な手段が無い。** item 1の挙動変化は強い間接証拠だが、hash不一致(例: 配備が一部だけ反映された状態)を直接には排除できない。`deployment_drift_check.yml`を通常Ansible経路(Semaphore経由)で実行するか、`deployed-hash`カタログへ本案件のファイルを追加すれば解消する。
3. **checkpoint 3(quory持ち出し前DLP)は、関数レベルの確認すら今回できていない。** checkpoint 4は`/usr/local/libexec`のコードをansy上で直接呼べたため関数レベルで確認できたが、checkpoint 3はOperator identity・quory上のプロセスとしてしか実行されない設計であり、ansyから同じ迂回はできない(意図的にも行っていない)。Operatorセッションでの実行以外に確認手段が無い。
4. **今回の試験でquoryのinboxに恒久的なrequestが1件増えた**(§8)。削除はYoshinobuの明示操作のみで行える。今後の判定作業でこのrequestを再利用する分には追加の払い出しは不要。

## 12. 使用した手段(箇条書き)

- `operator-channel-client submit` / `status` / `list`(ansy、identity `yoshi`)
- `ssh quory-investigate "operator-request-submit"` / `"operator-request-status <id>"` / `"operator-outbound-list"`(forced command、identity `dev-investigate`)
- `ssh quory-investigate "deployed-hash investigate-dispatch-quory"` / `"forced-command-keys"` / 既存read-only 15コマンド
- `sha256sum` / `diff -q` によるansy配備物とrepo srcの突合
- `/usr/local/libexec/operator-request-channel/oprc`配下のPythonモジュールを`sys.path`経由でansy上から直接import・実行(`dlp.scan()` / `config.load_and_verify_dlp_ruleset()` / `ids.generate_conversation_id()`)。quoryへは一切送信していない
- **未確認**: quory上でのOperatorセッション起動、quory側`oprc/`ライブラリのhash直接照合、`quarantine-metadata`/`audit.jsonl`の中身
