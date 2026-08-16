# implement: team `homelab-ops` の作成と remote 接続(段3・ansy 側)

作成日: 2026-08-16 / 作成: Coordinator

## 1. 担当範囲

requirement `2026-08-16_001_requirement.md` §5 のうち **R3・R4・R12・R13・R16**、および R7・R8 の文書化。段2(サーバ配備)は `_003_implement_stage2.md`、受入は `_005_test_result.md`。

**quory 側は対象外**(到達手段が無い)。AC1-b / AC3 / AC5 の実受信は Yoshinobu の手作業区間に残る。

## 2. 実施したこと(ansy)

| 手順 | 結果 |
|---|---|
| `~/.agents/skills/agmsg/` の退避 | `~/agmsg-backup-pre-stage3-20260816_173238.tar.gz` |
| `join.sh homelab-ops coordinator claude-code <project>` | team 作成 + `coordinator` 登録 |
| `apt install age` | 1.2.1。**`connect --e2ee` は `age` が無いと開始前に停止する** |
| `remote.sh connect --endpoint <ansy のサーバ URL> --e2ee homelab-ops` | 鍵生成 → 1度目は engine 起動で失敗(§3)→ CA を渡して再実行し成立 |
| `key.sh handoff homelab-ops --out ~/agmsg-homelab-ops-handoff.bundle` | 0600、repo 外。**snapshot digest は repo へ書かない**(別経路で quory へ渡す) |
| Monitor の張り直し | `identities.sh` が `homelab-ops/coordinator` と `homelab/claude` の2ペアを返す状態で再起動 |
| `~/.bashrc` へ `export CURL_CA_BUNDLE=...`(非対話ガードより上) | Yoshinobu 承認のうえ実施(§3) |

`remote.sh status homelab-ops` → `connected (engine running, pid 262702)` / `encryption: age-v1, key present` / `last successful sync 2026-08-16T08:51:25Z`。

## 3. Node が system trust store を見ない(想定外、R3 の実施を止めた)

`connect --e2ee` は age-v1 の設定(サーバへの fetch を伴う)を engine 起動より先に行う。ここが `fetch failed` で落ち、**binding だけが記録された状態**になった。その状態で `sync start` を打つと `connected team selected age-v1 but its authenticated sync configuration is missing` で失敗する(`run/remote-sync.homelab-ops.log`)。**回復は `connect --e2ee` の再実行であり、`sync start` の再試行ではない。**

原因を独立に確認した(状態を変えない実測)。

```
node -e "fetch('https://ansy.internal:8788/v1/health')…"                 → ERR UNABLE_TO_GET_ISSUER_CERT_LOCALLY
NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt node -e "同上"     → OK {"status":"ok",…}
curl(system trust store)                                                 → 検証を無効化せず成立
```

上流 `docs/remote-setup.md`「Terminating TLS with a private CA」の指示どおり `CURL_CA_BUNDLE` を渡すと成立した(`remote-sync.sh` がこれを Node へ `NODE_EXTRA_CA_CERTS` として引き継ぐ)。**症状が「curl は通るのに engine だけ立たない」形で出る**ため、経路の切り分けを誤りやすい。

**持続化**: engine の起動ごとに要る値であり、team の binding には記憶されない。ansy 再起動後は `session-start.sh` が接続済み team の engine を自動起動するが、それは Claude Code を起動したシェルの環境を引き継ぐ。したがって `~/.bashrc`(非対話ガードより上)へ置いた。値は curl の既定パスそのものなので curl の挙動は変わらない。

## 4. 実測した AC4(サーバ側)

サーバの PostgreSQL を直接照会した。

- `teams` の行は `homelab-ops` の1件のみ。**`homelab` はサーバ側に存在しない**(local-only のまま、R4)
- `messages` の行は `cipher = age-v1`、`blob` は base64 デコードで `age-encryption.org/v1` ヘッダ。**スキーマに `from` / `to` / `body` の列がそもそも無い**(`team_id, id, team_seq, envelope_v, cipher, key_id, blob, envelope_digest`)

## 5. AC5 の成立条件(構造の確認)

`watch.sh` は `PAIRS` を起動時に1度だけ解決する(`watch.sh:432`、ループの外)。**新しい team に join しても、走っている watcher はそれを拾わない** — 張り直しが要る。

`homelab` は共有 store、`homelab-ops` は接続時に専用 store へ移る(`db/teams/homelab-ops/messages.db`)が、受信は `storage_watch_after` → `_sqlite_data "$team"` と team ごとに DB を解決するため、**1プロセスで両方を覆える**。`actas` は使っていない(使うと受信が1識別子へ限定され、他方が無音になる)。

**実際に homelab-ops 宛の受信が届くことは未確認** — 現在この team の member は `coordinator` 1名で、送り手がいない。quory 側が join した後に確認する。

## 6. 安全機構によるブロック(記録)

Claude Code の auto mode classifier が2回ブロックした。**別の形で同じ結果へ到達することはせず、Yoshinobu が当該コマンドを実行した。**

| ブロックされたもの | その後 |
|---|---|
| `join.sh homelab-ops coordinator claude-code <project>` | Yoshinobu が実行 |
| `CURL_CA_BUNDLE=… remote.sh sync start homelab-ops`(および同じ形の `connect`) | Yoshinobu が実行 |

`.claude/settings.json` の `autoMode.allow` は ansy への非冪等操作を許可しているが、これらは分類器を通らなかった。**恒久的な allow 行の追加は行っていない**(team 作成・identity 登録の能力を常時開けることになるため、一度きりの初期設定には見合わないと判断した)。

## 7. sync engine は畳めない(要件を変更した)

engine は `nohup` + `disown` で起動し、シェルもセッションも越えて残る。**公開 CLI に停止手段が無く**、止まるのは `disconnect` / `forget` / `set-endpoint` / `unlock` の副作用としてだけである(`remote.sh` のソースで確認)。段0・段2のどちらでもこの経路は表に出ていなかった。

quory 側では、これが当初の R5 / AC6(常駐物を作らない)と両立しない。**2026-08-16、Yoshinobu が engine の常駐を受け入れる決定をした** — この経路を使う場面はトラブル対応か深い開発であり、そのたびに土台を立て直す形にはできないため。requirement R5 / AC6 を改訂済み。

**線は「常駐するか」から「人が見ていないときに AI の文脈へ入るか」へ移った。** engine が運ぶのはローカル store までで、watcher はセッションと共に消える。受け入れた代償は、人が見ていない間もメッセージが復号されて quory のローカル store へ落ち続けること。

## 8. AC1-b は成立した(quory 側の実測、Operator Request Channel 経由)

**quory から証明書検証を無効化せずに HTTPS で到達でき、ヘルス応答は `status` / `database` とも ok**(2026-08-16、Operator が実測。OPRES `req-20260816T192455+0900-…`)。requirement AC1-b が Yoshinobu 区間として残していた残存確認は、これで埋まった。**ansy からは原理的に確認できない区間であり、根拠は quory 側の観測報告である。**

あわせて quory 側の前提が揃った — agmsg v1.2.0(`remote.sh` / `key.sh` あり)、Node v22.23.2、`age` 1.2.1(当初は未導入で、2026-08-16 に Yoshinobu が導入した)。

**この往復は agmsg ではなく既存の Operator Request Channel を通っている。** agmsg 側は quory が未 join のため使えず、**経路が立ち上がるまでの連絡は従来経路が担った**。運用として、片方が落ちても手作業と既存経路へ縮退できる(R14)ことの実例でもある。

## 9. quory 側が入った(2026-08-16 夜)

`pull` → `unlock`(digest 一致)→ `operator` として join まで quory 側で完了。**ただし join もメッセージもサーバへ上がってこなかった。**

切り分けは ansy 側の観測から始めた。nginx のアクセスログを送信元ごとに分解すると、**quory から届いていたのは pull 一連の GET とヘルスチェックの計10件だけで、POST は1件も無く、19:36:49 以降は無音**だった。同時間帯に ansy 自身の engine は5秒周期で POST を含めて往復しており、**TLS ハンドシェイクの失敗も記録が無い**(quory の engine はリクエストを出していない)。ufw の許可ルールは1件で quory の解決値と一致していた。

**当初の見立て(CA 未設定)は quory 側の実測で否定された** — `CURL_CA_BUNDLE` は設定済みだった。実際の原因は、**engine をエージェントのツール実行から起動していたため、コマンド終了時に子プロセスごと刈られていた**こと。`nohup` + `disown` は SIGHUP からしか守らない。通常のシェルから `sync start` を打ち直したところ、**溜まっていた join とメッセージが即座にサーバへ上がり**、ansy 側の Monitor が受信した。

観測できた受入条件:

- **AC5(実受信)成立** — 1つの Monitor が `homelab-ops` 宛を配信した。`homelab`(codex Reviewer)との同居は保たれ、`actas` は使っていない
- **AC3(双方向)成立** — `operator` → `coordinator` は ansy 側の Monitor が配信。`coordinator` → `operator` は、リブート時の懸念を共有した2通目について **Operator セッションで受信したという返答**を得た(10:57:58)。サーバ側の行は `cipher=age-v1` のまま増えており、平文は経由していない

## 10. 残り

1. **quory 側**(Yoshinobu): 鍵束と digest の手運び → `pull` → `unlock` → `operator` として join → watcher 起動。手順は `docs/ai/context/operations/agent-messaging.md` §9
2. **AC1-b / AC3 / AC5 の実受信**: quory 側が入った後
3. **R15**(ansy 再起動後に**サーバ**が戻ること): 段2から持ち越し
4. **sync engine の再起動後の復帰**: R15 とは別項目。`session-start.sh` 経由の自動起動が、CA を引き継いだ環境で成立するかは未確認。サーバだけが戻って engine が落ちている状態は、`remote.sh status <team>` を見ない限り「繋がっているように見える」
