# quory 配備手順: `homelab-semaphore-query` の API 移行

作成: 2026-08-19 / Coordinator
実行: Yoshinobu(quory 上)
対象 commit: `0196087`(実装)/ `16e568a`(本手順書)

**ansy では検証済み。実ホストでしか確認できないのは AC9 と AC10 の2つで、それがこの手順の目的である。**

---

## 0. 前提の確認

**ディレクトリを明示して実行する。** quory には少なくとも2つのチェックアウトがあり、**Semaphore はジョブのたびに GitHub から `/opt` 配下へ自分で clone する**(`docs/ai/context/operations/code-delivery-to-production.md` §3.1)。同期の対象は前者だけである。

```bash
cd /home/yoshi/homelab-ansible
git log --oneline -1     # 16e568a 以降であること
git status --short       # 空であること
```

**`16e568a` は本手順書自身が入った commit である。** これより古ければ同期がまだ届いていない(1分間隔)。

**作業ツリーが汚れていたら止める。** `worktree_sync` は汚れた木を直さずに停止する規範であり、汚れている状態自体が異常である。同期が回っているかは `journal-unit worktree-sync.service` で読める。

## 1. 読み取り専用の Semaphore ユーザーとトークンを作る

**`homelab-semaphore-query` が使うトークンは、既存のどれとも別に発行する。** Operator 用とも、`coordinator-readonly` とも、admin とも分ける。**消費者が違えば独立に失効できるべきである。**

admin トークンを使って作る(以下は ansy で実証済みの手順そのまま)。

```bash
B=https://quory.internal:3000/api
A=$(sudo cat /etc/homelab-recovery/semaphore-templates-api-token)   # admin
PW=$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 24)

# 1-1. 非 admin ユーザーを作る
curl -s -H "Authorization: Bearer $A" -H "Content-Type: application/json" \
  -d "{\"name\":\"semaphore-query (read-only)\",\"username\":\"semaphore-query\",\"email\":\"semaphore-query@invalid.local\",\"password\":\"$PW\",\"admin\":false}" \
  "$B/users" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['id'], d['username'], d['admin'])"
```

返った id を `UID` とする。

```bash
# 1-2. project へ guest(読み取り専用)として追加する
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $A" -H "Content-Type: application/json" \
  -d "{\"user_id\":<UID>,\"role\":\"guest\"}" "$B/project/1/users"      # 204 が返ること

# 1-3. そのユーザーとしてログインし、トークンを発行する
curl -s -c /tmp/.oc -o /dev/null -w "%{http_code}\n" -H "Content-Type: application/json" \
  -d "{\"auth\":\"semaphore-query\",\"password\":\"$PW\"}" "$B/auth/login"    # 204
curl -s -b /tmp/.oc -X POST "$B/user/tokens" \
  | python3 -c "import json,sys; open('/tmp/.qt','w').write(json.load(sys.stdin)['id'])"

# 1-4. 置く
sudo install -o root -g root -m 0600 /tmp/.qt /etc/homelab-recovery/semaphore-query-token
sudo stat -c '%n %U:%G %a' /etc/homelab-recovery/semaphore-query-token
rm -f /tmp/.oc /tmp/.qt; unset A PW
```

**`root:root 600` であること。** ACL は次の段の playbook が付ける。

**トークンの値を画面へ出さない。** 上の手順は一度もそれを表示しない。

## 2. Semaphore のボタンを4つ押す

**トークンを置いた後で押す。** ACL タスクの対象がトークンファイルであり、無ければ失敗する。

**テンプレートから新規に起動する。** 過去のタスクの「再実行」は**そのときの commit を掴む**ため、新しい commit の配備にならない(`docs/ai/context/operations/code-delivery-to-production.md` §3.1)。

| 順 | template | 何が入るか |
|---|---|---|
| 1 | `SEMI-SAFE: Recovery exec setup`(id=35) | `homelab-semaphore-query` 本体、トークンへの ACL、**`recovery-exec` の旧 ACL 撤去** |
| 2 | `SEMI-SAFE: Dev investigate setup`(id=36) | **`dev-investigate` のトークン ACL と旧 ACL 撤去。これが無いと調査経路が通らない** |
| 3 | `SEMI-SAFE: Incident investigate setup`(id=34) | 先読み用の専用ディレクトリ、`yoshi` へのトークン ACL |
| 4 | `SEMI-SAFE: Incident inspect setup`(id=40) | 書き換えた `AGENTS.md`、`incident-inspect` の旧 ACL 撤去 |
| 5 | `SEMI-SAFE: Incident capture setup`(id=39) | 収集器(時刻パースの追随) |

**旧 ACL は、それを付けた role がそれぞれ撤去する。** 1本流しただけでは自分の分しか消えない。

**3と4のあいだに順序依存は無い**(専用ディレクトリを1つの role が排他的に所有する形へ直したため)。1と2が先、5が最後であればよい。

> **`dev_investigate_setup` は pre-commit の「配備が要る」に出ない。** あの検査はカタログに載る `copy` 配備物を見るもので、この role の変更は `tasks` と `defaults`(ACL の付与と撤去)だけだからである。**配備の要否は `git diff --stat` で変更された role を見て決める** — pre-commit の出力をそのまま配備リストにしない(2026-08-19、実際にこれで1本落とした)。

## 3. 確認する

### AC5 — dispatch が無変更で動く

ansy から:

```bash
ssh quory-investigate "semaphore-query recent-failed 3"
```

**版上げ前と同じ3件(675 / 631 / 607)が返ること。** これが返れば、私(Coordinator)の調査経路も復旧している。

### AC9 — `yoshi` がトークンを読める

quory 上で:

```bash
homelab-semaphore-query task-time 675
```

**6フィールドが返ること。** 「トークンが読めない」で非ゼロ終了しないこと。

### 旧 ACL が消えたこと

```bash
getfacl -p /var/lib/semaphore | grep -E "^user:[a-z]"
```

**named-user エントリが1つも返らないこと**(返れば撤去タスクが効いていない)。

> **ansy 側の `acl-status semaphore-db` は、この配備以降ずっと `Permission denied` になる。** `dev-investigate` がディレクトリへの traverse を失うためで、**能力が消えたことの証拠であって異常ではない。** ただし **「semaphore.db に ACL が付け直されていないか」を開発側から観測する手段は失われる**(§5)。

### AC6 — incident capture が復旧する

収集器を1周期動かす。**unit 名は `homelab-incident-capture.service`**(テンプレートのファイル名は `incident-capture.service.j2` だが、配備先の名前は `homelab-` が付く)。

```bash
sudo systemctl start homelab-incident-capture.service
sudo systemctl show homelab-incident-capture.service -p ExecMainStatus --value
```

**存在しない unit 名を渡すと、`systemctl show` は既定値の `0` を返す。** 直前の「Unit not found」と並ぶと成功に見えるので、unit 名を先に確かめること。

**`has_errors` が `false` であること。** `true` なら run report に理由が出る。

### AC10 — LLM が先読みファイルを読める

**これは incident 調査が実際に走ったときにしか確認できない。** 次に Semaphore ジョブが失敗し、調査が動いたときの成果物で、Semaphore の情報が引用できているかを見る。

## 4. 戻すとき

**コードは `git revert` で戻せるが、配備物は playbook を流し直すまで戻らない。** 旧版へ戻すなら、revert 後に同じ4つのボタンを押す。

**トークンとユーザーは残してよい**(使われなくなるだけ)。消すなら Semaphore の UI から。

## 5. 残る未確認

| 項目 | いつ分かるか |
|---|---|
| AC10(LLM が先読みファイルを読む) | 次に incident 調査が走ったとき |
| タスク一覧が将来ページングされたときの挙動 | 757件を大きく超えたとき。`task-time` は非ゼロで騒ぐが、`recent-failed` は静かに古い分を落とす |
