# implement: agmsg リファレンスサーバの ansy 配備(段2)

作成日: 2026-08-16 / 作成: Implementer
改訂: 2026-08-16 — 独立レビュー(Request Changes、Critical 2件/High 1件)への対応。**①**証明書・秘密鍵は`deploy_semaphore.yml`で別々のtaskとして置き換わり、`.path` unitが証明書だけを監視していたため、鍵が後から変わる窓でreloadが一度も再試行されず古いペアのまま固定されうる欠陥を修正(鍵も監視対象に追加)。**②**nginxがIPv6でもlistenしていたが、`firewall.yml`が管理するufwルールはIPv4のみで、IPv6面の到達可否がroleの外側(ufwの既定ポリシー)に暗黙に依存していたため、IPv6のlistenを外し公開面をIPv4のみへ揃えた。**③**`firewall.yml`は新しいアドレスの許可を追加するだけで、quoryの解決先が変わった場合に古いアドレスの許可が残り続ける欠陥があったため、対象ポートの許可ルールから現在の解決値と一致しないものを削除するpruneステップを追加。あわせてtester-gateマーカーの表記をPolicy指定の形(em dash)へ揃え、`--check`の説明を実装(全task skip)に合わせて訂正した。**旧§4.5(検知/反応を分離した試験)は本改訂で置き換え、結合試験の結果に更新した。**

改訂2: 2026-08-16 — 独立レビュー round3(Request Changes、Critical 2件/High 1件)への対応。round1〜3を通じて①②③には触れていない(前回の指摘で「意図どおり改善されている」と判定済み)。今回の指摘は round2 で新設した pruner とその周辺に限られる。**①**`roles/agmsg_server/tasks/main.yml`は`packages → deploy → proxy → firewall`の順で、公開面(nginx)が到達制御より先に立ち上がっていた。かつ`firewall.yml`はufwが有効かつdefault-denyであることを一度も確認しておらず、`ufw status`が`inactive`を返しても pruner は「stale 0件・成功」を返していた。**順序を`firewall → packages → deploy → proxy`へ入れ替え、`firewall.yml`の先頭にufwの active/default-deny確認をfail-closedで追加した**(`--check`でも常に実行、TS-014)。**②**pruner は対象ポートを含むが想定外の形式の行を黙って無視し、「stale 0件」に丸め込んでいた。**「認識できない行がある」ことを「stale 0件」と区別し、前者は明示的な失敗として返すよう書き換えた。** Suggestion(削除のTOCTOU)に対応し、削除は番号ではなくルール仕様(`ufw delete allow from <ip> to any port <port> proto tcp`)で行う形へ変更した。上記2点は実機のダミー1件試験では検出できないため、`roles/agmsg_server/tests/test_prune_stale_ufw_rule.py`を新設し、レビューが挙げた場合分け(active+default-deny / inactive / default allow / stale なし / 複数stale / 未知形式・locale差 / 削除途中失敗)をfixtureとして実装・全件確認した。あわせてplaybookヘッダを、read-only診断task(`command`/`assert`/`set_fact`)が`--check`でも常に実行される実装に合わせて訂正した。§2・§3.8・§4に本改訂の内容を反映し、旧記述は書き直した(積み増していない)。

## 1. 担当範囲

requirement `2026-08-16_001_requirement.md` §5 のうち **R1・R2・R10・R11・R15**、および段0の実測 `2026-08-16_002_spike.md` を引き継いだ実装。team 作成・E2EE 鍵束・remote 接続・AC1-b(quory からの実到達)は対象外(段3)。AC1〜AC8 の受入判定は Tester の職掌であり、本記録では判定を書かない。ここに書くのは何を作り、何を実測したかだけである。

対象は ansy のみ。`quory` / `pve1` / `pve2` / `authy` / `sophos-fw` / `monnie` / `sandbox` へは変更を広げていない。`~/.agents/skills/agmsg/`(段1の成果物、client)は未変更。`roles/homelab_cert_renew/` / `playbooks/cert_renew*.yml` / `roles/operator_request_channel/` / `roles/dev_investigate/` も未変更(`git status` で確認)。

## 2. 成果物

| パス | 内容 |
|---|---|
| `roles/agmsg_server/defaults/main.yml`(新規) | バージョン固定(`v1.2.0`)、配置パス、Docker/nginxのポート、既存fullchain証明書パスの参照、到達範囲の絞り込み対象 |
| `roles/agmsg_server/tasks/main.yml`(新規) | **firewall → packages → deploy → proxy** の実行順序(round3改訂。旧順序はfirewallが最後で、公開面が到達制御より先に立つ窓があった) |
| `roles/agmsg_server/tasks/packages.yml`(新規) | Docker Engine・Compose v2 plugin・nginxの導入、Dockerのenable+start(R15) |
| `roles/agmsg_server/tasks/deploy.yml`(新規) | 上流ソース(pin済みtag)のgit checkout、PostgreSQLパスワードの一度限りの生成、ansible管理のcompose.yamlデプロイ、`community.docker.docker_compose_v2`によるスタック起動 |
| `roles/agmsg_server/tasks/proxy.yml`(新規) | nginxのenable+start、reverse proxy site配備、default site無効化、証明書監視systemd unit配備 |
| `roles/agmsg_server/tasks/firewall.yml`(新規) | **ufwの active/default-deny確認(fail-closed、round3新設)**、quoryホスト名の実行時IPv4解決(R2)、旧アドレスの許可ルールのprune、ufwルール追加 |
| `roles/agmsg_server/files/prune-stale-ufw-rule.py`(新規) | 対象ポートのufw許可ルールのうち、現在の解決アドレスと一致しないものを削除(レビュー指摘③)。**round3で書き直し**: 認識できない行を「stale 0件」に丸め込まず失敗として返す(指摘②)、削除は番号でなくルール仕様で行う(TOCTOU Suggestion) |
| `roles/agmsg_server/tests/test_prune_stale_ufw_rule.py`(新規、round3) | 上記スクリプトの純粋な分類・事前条件ロジックをufwなしでfixture検証。ホストへ配備しない |
| `roles/agmsg_server/handlers/main.yml`(新規) | nginx reload、systemd daemon-reload |
| `roles/agmsg_server/templates/compose.yaml.j2`(新規) | 上流`server/compose.yaml`由来。差分はファイル冒頭コメントに明記 |
| `roles/agmsg_server/templates/nginx-agmsg.conf.j2`(新規) | TLS終端 + reverse proxy |
| `roles/agmsg_server/templates/agmsg-cert-reload.path.j2`(新規) | 証明書ファイルの置き換え検知(R10) |
| `roles/agmsg_server/templates/agmsg-cert-reload.service.j2`(新規) | 検知後の`nginx -t && systemctl reload nginx` |
| `playbooks/agmsg_server_setup.yml`(新規) | 呼び出し口。`hosts: ansy`のみ |
| `playbooks/README.md`(既存へ1行追記) | カタログ登録 |
| 本ファイル | implement記録 |

## 3. 設計判断とその根拠

### 3.1 到達範囲を二層で絞った(R2)

段0(sandbox)の結論は「Dockerが直接公開したポートはufwのINPUT chainを素通りする」というものだったが、ansyにはDocker導入前は`DOCKER-USER` chain自体が存在しなかった。今回Docker導入後のansyで実際に観測した。

- `sudo iptables -L DOCKER-USER -n` → chainは**存在する**(空)。Docker導入により`FORWARD`chainへ`DOCKER-USER`/`DOCKER-FORWARD`が挿入されている(`iptables -L FORWARD -n`で確認、`policy DROP`配下に両chainが並ぶ)。
- ただし`docker port agmsg-server-1` → `8787/tcp -> 127.0.0.1:8787`。`ss -ltn`でも8787はloopbackにしか現れない。**Dockerが公開する面をloopback限定にしたことで、DOCKER-USER chainの中身を一切気にする必要が無い設計になっている**(そこを通る経路自体が存在しない)。
- 外部から到達できるのは nginx が公開する `0.0.0.0:8788`(IPv4のみ、§3.6参照)だけであり、nginxはコンテナではないため通常のufw INPUT chainがそのまま効く。これは段0のQ1回答(二層設計)どおりだが、根拠をsandboxの構造からansy実機の観測へ置き換えた。

到達範囲の絞り込みは、Dockerの`DOCKER-USER`へ手書きルールを足す形ではなく、**「外部公開面をnginx 1箇所に集約し、そこだけufwで絞る」**という設計にした。DOCKER-USER chainを直接操作しないため、ufw運用と一貫する(段0の判断をそのまま踏襲)。

### 3.2 `ufw`はホスト名を解決しない(実測、想定外の欠陥)

初回実行(2026-08-16 15:37 JST)で`firewall.yml`が`ERROR: Bad source address`で失敗した。

```
/usr/sbin/ufw allow from quory.internal to any port 8788 proto tcp comment '...'
```

`community.general.ufw`モジュールは`from_ip`の値をそのまま`ufw`コマンドへ渡すだけで、ホスト名の解決を一切行わない(モジュールソース `ufw.py` を確認 — `is_starting_by_ipv4`/`is_starting_by_ipv6`による分岐はcheck_modeのdiff判定用であり、値そのものの解決には関与しない)。`ufw`コマンド自身も同様で、`sudo ufw --dry-run allow from quory.internal ...`で同じエラーを再現した。

修正は、`roles/alloy`が remote syslog の送信元許可リストで既に使っている手法(`getent ahostsv4`による実行時のIPv4解決、`roles/alloy/tasks/main.yml`)に倣った。`firewall.yml`は次の4taskに分けた。

1. `getent ahostsv4 {{ hostvars['quory']['ansible_host'] }}`を実行(read-only、`check_mode: false`)
2. 解決結果をassertで検証(rc・出力有無・IPv4パターン一致)— 失敗時は**fail-closed**(絞り込み無しのルールを黙って作らない)
3. 解決結果からIPを`set_fact`
4. そのIPを`from_ip`としてufwルールを追加

解決はansy自身のローカルな名前解決(DNS/hosts)で完結し、quoryホストへは一切到達しない(接続ではなく名前解決)。解決結果のIPはどのrepoファイルにも書いていない — play実行中のみメモリ上に存在する。IPv4リテラルをrepoへ書かない方針は維持している(`getent`の引数は`hostvars['quory']['ansible_host']`、すなわちinventory上の`quory.internal`というホスト名であり、literalなIPはコード中に一切現れない)。

修正後、`sudo ufw status numbered`に3番目のルールとして`8788/tcp ALLOW IN <quoryの解決済みアドレス>`が入っていることを確認した(`/etc/ufw/user.rules`のcomment行はhexエンコードされており、平文コメントの中身はrepoの記述と一致することを`echo <hex> | xxd -r -p`で確認済み)。

### 3.3 上流compose.yamlを直接使わず、1枚のcompose.yamlとして再構成した(R1・R11・R15)

Docker Composeのmulti-file merge(`-f base -f override`)では`ports:`のようなsequenceフィールドが結合される(上書きでなく追加)。上流の`"8787:8787"`(全interface公開)とこちらの`"127.0.0.1:8787:8787"`を両方指定すると、同一ポートへの二重bindでコンテナ起動が失敗する経路になりうる。この不確実性を避けるため、上流compose.yamlをそのまま使う設計はやめ、`roles/agmsg_server/templates/compose.yaml.j2`として1枚に再構成した。差分(restartポリシー追加・Docker公開をloopback限定・パスワードのsecret化・buildコンテキストの絶対path化)はテンプレート冒頭のコメントに明記し、上流ファイルの形が変わったら要再確認である旨を書いた。

上流ソース自体(`server/`ディレクトリ、Dockerfile含む)は`git`モジュールで`v1.2.0`固定のpinとしてcheckoutし(`agmsg_server_src_dir`)、`build:`のcontextとして絶対pathで参照する。クライアント側(段1)と同じくupstreamのソースはこのrepoへ写さない(`docs/ai/context/operations/agent-messaging.md`§1と同型の判断)。

### 3.4 PostgreSQLパスワードの扱い(公開情報と秘密情報)

上流`compose.yaml`は`POSTGRES_PASSWORD: agmsg-local-only`を直書きしている。この値をrepoへ書ける性質のものではないと判断し、`ansible.builtin.copy`(`force: false`)+`lookup('ansible.builtin.password', '/dev/null', ...)`で一度だけ生成し、`/opt/agmsg-server/deploy/.env`(root:root, mode 0600)へ保存した。`force: false`により2回目以降のplaybook実行では上書きされない(再生成するとDocker volumeに残っている既存Postgresデータのパスワードと食い違い、コンテナが起動しなくなるため)。生成task自体は`no_log: true`。

実測: `sudo stat`で`600 root:root`を確認。`yoshi`(非root)で`cat`すると`Permission denied`。生成された値そのものをrepo内でgrepしても出現しないことを確認した(値自体をyoshiでも読めないため、間接的な確認に留まる)。

### 3.5 証明書は既存fullchainをそのまま参照(R11)、置き換え検知はansy側のsystemd `.path` unit(R10)

`cert_renew`側は変更しない制約(2026-08-16 Yoshinobu決定)のため、`nginx-agmsg.conf.j2`は`/etc/semaphore/tls/ansy.internal.crt`/`.key`をそのまま`ssl_certificate`/`ssl_certificate_key`に指定した(新しい証明書材料は作っていない)。置き換え検知は`agmsg-cert-reload.path`(`PathModified=`)+`agmsg-cert-reload.service`(`nginx -t && systemctl reload nginx`)という、cert_renewの外側から動く別経路にした。

### 3.6 証明書と秘密鍵は別々のtaskで置き換わる — `.path` unitは両方を監視する(レビュー指摘①、修正)

`roles/homelab_cert_renew/tasks/deploy_semaphore.yml`を読むと、`Deploy certificate`(証明書)と`Deploy private key`(秘密鍵)は**別々のtask**で、両方とも`when: cert_needs_renewal`、あいだに他の処理は無い。証明書が先、鍵が後という順序である。

初版の`agmsg-cert-reload.path`は証明書だけを`PathModified=`で監視していた。この場合、証明書だけが変わった瞬間(新しい証明書 + 古い鍵、ペアが不一致)に1回reload試行が起き、`nginx -t`が鍵不一致で失敗する(safe — nginxは直前の有効なペアを提供し続ける)。しかし鍵が**後から**変わっても、監視対象が証明書のパスだけなので**再試行が一度も起きない** — 結果として、証明書・鍵ファイルはどちらも新しくなっているのに、nginxは古いペアを提供し続けたまま人手の介入なしには収束しない、という欠陥だった。

修正: `agmsg-cert-reload.path.j2`に`PathModified=`を2行(証明書・秘密鍵それぞれ)持たせた。順序に関わらず、**後から変わった方のファイルのイベントが、両方とも新しい状態でのreload試行になる**ため、必ず収束する。結合試験は§4.5を参照。

### 3.7 IPv6のlistenを外した(レビュー指摘②、修正)

初版は`nginx-agmsg.conf.j2`に`listen [::]:{{ agmsg_server_public_port }} ssl;`を含めていたが、`firewall.yml`が管理するufwルールはIPv4のみ(`getent ahostsv4`で解決)であり、IPv6面の到達可否を制御する行を1つも持っていなかった。この状態では「IPv6から到達できない」という結果は成立していても、それは**role自身が確認・管理しているからではなく、ホスト側のufwの既定ポリシー(`default deny (incoming)`、`/etc/default/ufw`の`IPV6=yes`)がたまたまそうなっているから**であり、role単体で見ると公開面(IPv4+IPv6)と管理している到達範囲(IPv4のみ)が一致していなかった。

対応として、IPv6の許可ルールを追加する方向ではなく、**公開面をIPv4のみへ絞る**方向を選んだ(`listen [::]:...`を削除)。この環境(homelab全体)がIPv6を積極的に使っている形跡が無く(既存のUniFi NTPのIPv6絡みの既知の落とし穴等)、quory自身がIPv6アドレスを持つかどうかも不明であるため、AAAA解決とv6 ufwルール管理を新たに背負うより、単純にIPv6面を持たない方が最小差分だと判断した。

### 3.8 quoryの解決アドレスが変わったとき、古いufw許可が残り続ける(レビュー指摘③)

`firewall.yml`は「今回解決されたアドレスを許可する」ルールを`community.general.ufw`で追加するだけで、**過去に解決されたアドレスの許可を取り除く処理を持っていなかった**。`community.general.ufw`には「このポートについては今回のルールだけを残す」という宣言的な操作が無いため、`roles/agmsg_server/files/prune-stale-ufw-rule.py`を新設した(round2)。

**round3の独立レビューで、このスクリプトとその呼び出しに2件のCriticalと1件のSuggestionが指摘され、以下のとおり書き直した(§4.7)。**

- **①ufwの健全性を誰も確認していなかった。** `roles/agmsg_server/tasks/main.yml`の実行順序が`packages → deploy → proxy → firewall`で、**公開面(nginx)が到達制御より先に立ち上がる**構成になっていた。加えて`firewall.yml`はufwが`active`かどうか、default incoming policyが`deny`かどうかを一度も確認していなかった。`ufw status`が`inactive`を返しても、pruner は「対象ポートのルールが0件」を正常な「stale 0件」として報告し、続く`community.general.ufw`の`rule: allow`は**ufwにルールを保存するだけで、ufw自体を有効化しない**。**対応**: (a) `roles/agmsg_server/tasks/main.yml`の実行順序を`firewall → packages → deploy → proxy`へ入れ替え、公開面が立つ前に到達制御が確立していることを保証する構成にした。(b) `firewall.yml`の先頭に、ufwが`active`かつ`Default: deny (incoming)`であることを`ansible.builtin.assert`でfail-closed確認するtaskを追加した(`command`+`assert`、`check_mode: false`、`when: not ansible_check_mode`を付けない — read-only診断はTS-014により`--check`でも常に実行する)。この確認が失敗すれば、`firewall.yml`以降の全task(パッケージ導入・deploy・proxyを含む)が実行されない。
- **②認識できない行を「stale 0件」に丸め込んでいた。** 旧版のpruner は、対象ポートを含むが期待した正規表現に一致しない行(想定外の形式、locale違い、IPv6行など)を単純に無視していた — 「該当なし」と「判定不能」を区別していなかった。**対応**: `classify()`を「対象ポートに言及する全ての行(candidate)」と「その中で認識できる形の行(strict)」の2段階に分け、candidateだがstrictでない行が1件でもあれば、それを`unrecognized`として呼び出し元へ返す。`main()`は`unrecognized`が非空なら**削除を一切試みず**exit 3で失敗する(「0件」としては絶対に扱わない)。
- **Suggestion: 削除のTOCTOU。** 旧版は`ufw status numbered`が振ったルール番号を保持し、その番号で`ufw --force delete <番号>`していた。別プロセスが同時にufwを変更すると番号がずれ、意図しないルールを消しうる。**対応**: 削除をルール番号ではなく**ルール仕様**(`ufw delete allow from <ip> to any port <port> proto tcp`)で行うよう`delete_by_spec()`を書き換えた。ufwは仕様に一致するルールを位置に関わらず特定して消すため、番号のずれに影響されない。

**この2件のCriticalは実機のダミー1件試験(happy path)では検出できない**(ufwを実際に停止させる/未知形式の行を実際に作るのは、本番のufwに触れる操作であり避けるべきである、と指摘・合意)。そのため`roles/agmsg_server/tests/test_prune_stale_ufw_rule.py`を新設し、`classify()`・`is_active_default_deny()`・`perform_prune()`・`main()`をufwを一切呼ばずに検証する15項目のfixture testを実装した(§4.7)。

## 4. 自己検証(実測)

すべてansy上、`ansible-playbook playbooks/agmsg_server_setup.yml -l ansy`を前景で実行して確認した。

### 4.1 構文・lint・カタログ整合

```
ansible-playbook playbooks/agmsg_server_setup.yml --syntax-check   # rc=0
ansible-lint playbooks/agmsg_server_setup.yml roles/agmsg_server   # Passed: 0 failure(s), 0 warning(s)
bash scripts/check-tester-gate.sh                                  # OK (55 playbooks)
python3 scripts/check-doc-consistency.py                           # check1/2/3 いずれもOK
```

### 4.2 実行履歴と冪等性

- 1回目(初回適用): `changed=14, failed=1`。`firewall.yml`が§3.2の理由で失敗し、それ以外の全task(Docker/nginx導入、compose起動、reverse proxy、証明書監視unit)は成功していた。
- `firewall.yml`を§3.2のとおり修正後、2回目: `changed=1`(ufwルール追加のみ)、`ok=20`。1回目で既に作られたリソースはすべて`ok`(再作成されない)ことを確認。
- 3回目(同一条件で再実行): `changed=0, ok=21, failed=0`。全task が `ok` となり、冪等性を確認した。
- レビュー対応(§3.6〜§3.8)後、4回目: `changed=4`(nginx site再テンプレート・`.path` unit再テンプレート・nginx reload・prunerスクリプト配備)、`ok=25`。IPv6のlisten削除・両ファイル監視・prunerの3変更が反映されたことに対応する差分のみで、それ以外は`ok`。
- 5回目(同一条件で再実行): `changed=0, ok=23, failed=0`。全task が `ok` となり、レビュー対応後も冪等性を維持していることを確認した(prunerのcopy taskとprune実行taskがtask数へ加わったため`ok`件数は変わったが、`changed`は0)。
- round3レビュー対応(実行順序の入れ替え・ufw健全性確認の追加・prunerの書き直し)後、6回目: `ok=25, changed=1`(prunerスクリプトの再配備のみ)。実行順序を`firewall → packages → deploy → proxy`へ入れ替えたにもかかわらず、既存の全リソースは`ok`のまま(構成の内容自体は変えていないため)。
- 7回目(同一条件で再実行): **`ok=25, changed=0, failed=0`**。冪等性を維持していることを確認した。
- §4.7のとおり実機へダミーのstaleルールを追加してから8回目を実行: `ok=25, changed=1`(pruneが実際に発火し、ダミールールだけを削除)。9回目(同一条件で再実行): `ok=25, changed=0`。ダミールール削除後も冪等性が保たれることを確認した。

### 4.3 コンテナ・ネットワーク状態

```
$ sudo docker ps -a
agmsg-server-1     Up ...   127.0.0.1:8787->8787/tcp
agmsg-postgres-1   Up ... (healthy)   (公開ポート無し)

$ curl -s http://127.0.0.1:8787/v1/health
{"status":"ok", ..., "database":"ok"}

$ curl -sk https://127.0.0.1:8788/v1/health -H 'Host: ansy.internal'
{"status":"ok", ..., "database":"ok"}
```

IPv6(§3.7の修正後、listenしていないことの確認):

```
$ ss -tln | grep 8788
LISTEN 0 511 0.0.0.0:8788 0.0.0.0:*        # IPv4のみ、[::]:8788は無い

$ curl -6 -sk https://[::1]:8788/v1/health
curl: (7) Failed to connect to ::1 port 8788: Connection refused
```

TLSチェーン(informational、AC1の判定はTesterの職掌):

```
$ openssl s_client -connect 127.0.0.1:8788 -servername ansy.internal -showcerts
subject=CN=ansy.internal / issuer=CN=Home-TLS-CA
subject=CN=Home-TLS-CA / issuer=CN=Home-RADIUS-CA
(証明書2枚を提示)
```

### 4.4 ufwとDockerの関係(実機観測、§3.1の詳細)

```
$ sudo iptables -L DOCKER-USER -n
Chain DOCKER-USER (1 references)
target ... (空、Docker導入により自動挿入されている)

$ sudo iptables -L FORWARD -n | head
Chain FORWARD (policy DROP)
DOCKER-USER  ...
DOCKER-FORWARD ...
ufw-before-forward ...

$ sudo ufw status numbered
[1] 22/tcp        ALLOW IN  Anywhere
[2] 3000/tcp       ALLOW IN  Anywhere
[3] 8788/tcp       ALLOW IN  <quoryの解決済みアドレス> # agmsg_server (...) -- quory only
```

Semaphore(3000/tcp)のルールは変更していない。`systemctl is-active semaphore` は全工程を通じて`active`のままだった。

**stale rule pruning(§3.8)の実機動作確認(round3の書き直し後、§4.7も参照)**: 実際にquoryの解決アドレスを変えて再現することはできない(実DNS/hostsを操作しないため)ので、pruneスクリプト単体を実際の`ufw`に対して動かして検証した。round2版(番号ベースの削除)・round3版(仕様ベースの削除)のいずれについても同じ手順で確認している。

1. 現在の正規ルールに加え、RFC 5737予約(TEST-NET-2、ドキュメント用に予約されたレンジで実在ホストではない)のアドレスを送信元とする8788/tcpのダミー許可ルールを`ufw insert`で追加(`ufw status numbered`でルール数が1件増えることを確認)
2. `playbooks/agmsg_server_setup.yml`をplaybook経由で再実行 → pruner taskが`changed`を報告し、ダミールールの送信元アドレスだけが標準出力に出て削除され、22/tcp・3000/tcp・正規の8788/tcpルールはすべて残ることを`ufw status numbered`で確認(§4.2の8回目)
3. 続けて再実行(9回目)しても、ダミーを作らない通常時は削除対象0件で`changed`が出ないことを確認済み(冪等性)

### 4.5 R10(証明書置き換え検知)の結合試験 — `cert_renew`を待たずに、実際の置き換え順序で

**旧版(初回実装時)は「検知」と「反応」を分離して別々に検証していたが、独立レビューで「`deploy_semaphore.yml`が証明書と秘密鍵を別task・別タイミングで置き換える実際の順序を通していない」と指摘され、Request Changesとなった。本節はその指摘を受けた再検証であり、旧内容を置き換える。**

実際の`/etc/semaphore/tls/ansy.internal.*`は一切変更していない(Semaphoreの現用証明書のため)。かわりに、`/tmp`配下の使い捨てcert/keyペア2組(自己署名、実CA・実ホスト名とは無関係)と、本番unitとは別名の一時nginx site(loopback限定、`ufw`未登録の検証専用ポート)・一時`.path`/`.service`ペア(§3.6修正後と同じ構成 — 証明書・秘密鍵の両方を`PathModified=`で監視)を用意し、`homelab_cert_renew/tasks/deploy_semaphore.yml`と**同じtask構成**(`ansible.builtin.copy`、`Deploy certificate`→`Deploy private key`の順、あいだに他のtaskを挟まない)を持つ使い捨てplaybookで、decoyの証明書・秘密鍵を「古いペア」から「新しいペア」へ置き換えた。

観測(`journalctl`、時刻はUnix時刻昇順):

1. `Deploy certificate`完了直後 — `.path` unitが発火、`nginx -t`が`SSL_CTX_use_PrivateKey(...) failed (SSL: error:05800074:x509 certificate routines::key values mismatch)`で失敗(新証明書+旧鍵の不一致)。reloadは実行されず、nginxは直前の有効な設定(旧ペア)を提供し続けた
2. 同一状態に対しごく短い間隔でもう一度同じ失敗が記録された(inotifyの重複イベントによるものと見られる。2回とも安全側=reload未実行で終わっており実害は無い)
3. `Deploy private key`完了後 — `.path` unitが再度発火、今度は`nginx -t`が成功しreloadが実行された

`openssl s_client`で検証ポートの提示証明書のシリアル番号を確認し、置き換え前は「古いペア」のシリアル、置き換え後は`Deploy private key`完了後に「新しいペア」のシリアルへ切り替わっていることを確認した — **証明書・秘密鍵が別々のtaskで置き換わる実際の順序のもとで、最終状態は必ず新しいペアへ収束する**ことを実測した。試験に使った一時nginx site・systemd unit・decoyファイルはすべて削除済み。実証明書ファイル(`/etc/semaphore/tls/ansy.internal.crt`/`.key`)のmtimeは試験前後で不変であることを確認した。Semaphore・本番nginx・本番agmsgサイトは試験中・試験後とも`active`/応答正常のままだった。

**ここで確認したのは「decoy素材で、実際の2task構成を通した結合の収束」である。** cert_renewが実際に証明書を書き換える瞬間(実credential、実タイミング)での確認ではない — 次回の実更新は9月上旬。

### 4.6 R15(再起動後の復帰) — 実際には再起動していない

```
docker      enabled / active
nginx       enabled / active
agmsg-cert-reload.path  enabled / active
agmsg-server-1   RestartPolicy=unless-stopped
agmsg-postgres-1 RestartPolicy=unless-stopped
docker volume: agmsg_agmsg-postgres (データ永続化)
```

systemdのenable状態とDockerのrestart policyから、ansy再起動時にDockerデーモン起動→`unless-stopped`によるコンテナ自動起動→nginx自動起動、という経路が動く**はず**であることを構成から示した。**実際にansyを再起動して確認してはいない**(指示どおり)。

### 4.7 round3: ufw健全性のfail-closed確認とprunerの分類ロジック — fixtureでの検証

**独立レビューround3が指摘した2件のCriticalは、実機のダミー1件試験(happy path)では検出できない性質のものである。** ①「ufwが無効/default-allowでもpruner・ufwルール追加は成功したように見える」ことを確かめるには、ansyの実ufwを実際に無効化する必要があり、それ自体が禁止されている(「ansyのufwを無効化した状態を作らないこと」)。②「認識できない行を`stale 0件`に丸め込む」ことを確かめるには、`ufw status numbered`が普段出さない形の行を実際に作る必要があるが、そのような行を実ufw上に意図的に作ること自体が実ufwの状態を予測不能にする。**したがって両方とも、ufwを一切呼ばないfixture testで検証した。**

`roles/agmsg_server/tests/test_prune_stale_ufw_rule.py`(新規、ホストへは配備しない)は、`roles/agmsg_server/files/prune-stale-ufw-rule.py`を`importlib`でモジュールとして読み込み、`ufw`コマンドを一切実行せずに次の15項目を確認する。

```
$ python3 roles/agmsg_server/tests/test_prune_stale_ufw_rule.py
PASS: active + default-deny is recognized as safe
PASS: inactive is refused
PASS: active but default-allow incoming is refused
PASS: no stale rules when the only rule matches keep_ip
PASS: multiple stale rules for the target port are all found, unrelated port ignored
PASS: an unrecognized line for the target port (e.g. an IPv6 rule) is NOT folded into '0 stale'
PASS: a translated/non-English action word for the target port is unrecognized, not skipped
PASS: genuinely no rules for this port at all is 0 stale, 0 unrecognized (a real success case)
PASS: a delete failure for one stale entry does not stop the others, and is reported (not silently dropped)
PASS: main() exits 5 (not 0) when ufw is inactive -- round3 Critical #1 scenario
PASS: main() exits 5 (not 0) when default policy is allow incoming
PASS: main() exits 3 (not 0) when a rule for the port is unrecognized -- round3 Critical #2 scenario
PASS: main() exits 0 with active+default-deny and no stale rules
PASS: main() exits 0 and prunes when active+default-deny and multiple stale rules exist
PASS: main() exits 4 (not 0) when a delete fails partway through -- reported, not silent (TOCTOU Suggestion)

All checks passed.
```

レビューが挙げた場合分け(active+default-deny / inactive / default allow / stale なし / 複数stale / 未知形式・locale差 / 削除途中失敗)を全てカバーしている。テスト用の送信元アドレスは`KEEP-ADDR`/`STALE-ADDR-A`/`STALE-ADDR-B`という非IP形の記号であり(IPv4リテラルをrepoへ書かない方針、docs/ai/core.md)、分類対象のスクリプトはsrcを不透明な文字列として扱うため検証の意味は変わらない。

**実装中に見つけた自分自身のバグ(実行前にコードレビューで発見、実行はしていない)**: `perform_prune(stale, port, delete=delete_by_spec)`という最初の実装は、`delete`のデフォルト値を関数定義時に一度だけ束縛していた(Pythonのデフォルト引数は定義時評価)。このため、fixtureテストで`mod.delete_by_spec`を差し替えても、デフォルト引数経由で呼ばれる`main()`側はその差し替えに気づかず、`main()`系のテストは実際の`ufw`コマンドを呼ぼうとして失敗するはずだった。fixtureのテストコードを書いている最中にこの束縛タイミングの問題に気づき、最初のテスト実行より前に`delete=None`をデフォルトにし関数本体内で`if delete is None: delete = delete_by_spec`という遅延束縛へ修正した。修正後の初回実行から15件全てPASSしている(§本節冒頭の出力)。fixtureを書く過程そのものが検証設計上のバグを見つけた実例として記録する。

**ufw健全性確認(①)の実機側**: fixtureは`is_active_default_deny()`のロジックを検証するが、Ansible側の`assert` task(`roles/agmsg_server/tasks/firewall.yml`冒頭)がansyの実際の`ufw status verbose`に対して正しく`PASS`することは、§4.2の6〜9回目の実行(いずれも`ok`、失敗なし)で確認済み — ansyのufwは`active`・`Default: deny (incoming)`のままなので、この確認は常に通過する側であり、**「実際に落ちる」ことまでは実機で確認していない**(§7参照、意図的にufwを落とさないため)。

## 5. 発見していた問題(解決した)

- `ufw`がホスト名を解決しない(§3.2)。修正済み。
- 1回目実行時、`docker compose`が `[WARNING]: Docker Compose is configured to build using Bake, but buildx isn't installed` という警告を出した(`buildx`未導入)。ビルド自体は成功しており(`agmsg-server`イメージが作成され、コンテナは正常稼働)実害は確認していないが、`docker-compose-v2`パッケージ導入のみで`buildx`は入れていない。**未解決事項へ記載**。
- 独立レビュー round2(Request Changes)で3件: 証明書監視が鍵の置換を捉えない(§3.6)、IPv6公開面がrole管理外(§3.7)、旧アドレスのufw許可が残り続ける(§3.8)。いずれも修正済み、実機確認は§4.4・§4.5。
- §4.5の結合試験中、`.path` unitが同一の変更に対し短間隔で2回発火する場面が観測された(inotifyの重複イベントによるものと見られる)。2回とも`nginx -t`失敗→reload未実行という安全側の結果で終わっており、収束にも影響していない(最終的に成功したのは3回目の発火)。実害は無いと判断し修正はしていないが、事実として記録する。
- 独立レビュー round3(Request Changes)で2件: ufwの健全性(active/default-deny)を誰も確認していなかった(§3.8①)、prunerが認識できない行を「stale 0件」に丸め込んでいた(§3.8②)。いずれも修正済み、fixture検証は§4.7。
- round3対応中に自分自身のバグ(Pythonのデフォルト引数の早期束縛によりfixtureでの差し替えが効かない)をコードレビューで発見・修正した(§4.7)。

## 6. 到達していないこと(確認)

- `quory` / `pve1` / `pve2` / `authy` / `sophos-fw` / `monnie` / `sandbox` への変更・接続なし。§3.2のホスト名解決はansy自身のローカル名前解決であり、quoryへの到達ではない。
- `~/.agents/skills/agmsg/`は無変更(`VERSION`=`v1.2.0`のまま、team登録・履歴には触れていない)。
- `roles/homelab_cert_renew/` / `playbooks/cert_renew*.yml` / `roles/operator_request_channel/` / `roles/dev_investigate/` に差分なし(`git status --short`で確認)。
- Semaphore(:3000)は全工程を通じて停止・再起動していない(`systemctl is-active semaphore`が常に`active`)。
- `/etc/semaphore/tls/ansy.internal.crt`/`.key`(実証明書)は一切変更していない(mtime不変を確認)。
- `git add` / `git commit` / `git push` は行っていない。
- 生成したPostgreSQLパスワードの実値はコンソール出力・本記録・repoのいずれにも現れていない(`no_log: true`、mode 0600)。

## 7. 未解決事項

1. **R10は、decoy素材で実際の2task構成(証明書→鍵)を通した結合試験まで確認した(§4.5)。** ただし、`cert_renew`が**実credentialで実際に**証明書を書き換える瞬間そのものでの確認ではない — 次回の実更新は9月上旬。
2. **R15は再起動なしの構成確認に留まる**(§4.6)。実際の再起動を伴う確認は行っていない。
3. **AC2の「想定していない発信元からの到達不能」は、quory以外の実ホストからの到達試行という形では検証していない。** ufw/iptablesのルール構成(§4.4)・IPv6のlisten削除(§3.7)から到達不能である**はず**だと示したに留まる。他の実ホストからの到達試行は、この段のscope(ansyのみ、他ホストへ触れない)の外にある。
4. **AC1-bは対象外**(quoryからの実到達、requirement で Yoshinobu 確認と合意済み)。
5. `docker compose`のBake関連警告(§5)。実害は未確認。`buildx`導入の要否はCoordinator判断。
6. 新しく増えたrepo外の秘密(`/opt/agmsg-server/deploy/.env`のPostgreSQLパスワード)を`docs/ai/status.md`「スナップショットから戻したときに要るもの」へ加えるべきかは判断していない。requirement §11の成果物表はR16(age鍵束、段3のP1項目)を想定しており、本段の秘密をどう扱うかはscope外と判断し、docs/ai/status.mdは変更していない。
7. `agmsg_server_public_port`(8788)は、上流の既定値(8787)と意図的に別番号にする設計判断をしたが、段3のクライアント設定(`remote.sh connect --endpoint https://ansy.internal:8788 ...`)で使われるURLとの整合は、段3のImplementer/Coordinatorが確認する必要がある。
8. `.path` unitの重複発火(§5)。実害・収束への影響は無いと判断したが、原因(inotifyイベントの重複)そのものは深追いしていない。
9. IPv6を「持たない」方向で揃えた(§3.7)。quory自身がIPv6アドレスを持つか、将来この環境がIPv6を使う方向になるかは確認していない — もしIPv6経路が必要になった場合は、`firewall.yml`側にも`ahostsv6`解決とv6 ufwルール管理を対で追加する必要がある(nginx側だけ`listen [::]`を足すと§3.7と同じ欠陥に戻る)。
10. **ufw健全性確認(§3.8①)が実際に失敗する経路(ufw inactive / default-allow)は、fixture(§4.7)でのみ検証した。** 「ansyのufwを無効化した状態を作らないこと」という制約のもと、実機のufwを実際に落として`firewall.yml`が本当に停止することまでは確認していない — `ansible.builtin.assert`のJinja条件(`is search(...)`)自体はAnsible標準の枯れた機能であり、`is_active_default_deny()`とのロジックの一致は目視で確認した(2つの実装は独立しており、意図的に共有していない — AnsibleのassertからPythonスクリプトの関数を直接呼ぶ手段が無いため)。
11. **prunerの`unrecognized`判定基準は`ufw status numbered`の現在の出力形式に依存している。** ufwのバージョンアップやlocale設定の変更で出力形式が変わった場合、正当なルールまで`unrecognized`と判定されfail-closedする可能性がある(意図した挙動ではあるが、運用上は「pruneが急に失敗するようになった」という形で気づかれる点に留意)。
