# Incident: 人が見ていないCodexスレッドが `operator` を名乗り自律的に応答した

日付: 2026-08-16
状態: 解決済み
対象: `~/.agents/skills/agmsg/`(client、ansible管理外) / team `homelab-ops` / quory の Operator
種別: セキュリティ事故
原因分類: #要件定義ミス #運用考慮ミス

## 症状

2026-08-16 の 20:48〜21:14 JST、team `homelab-ops` で ansy 側 Coordinator が送ったメッセージに対し、`operator` 名義の返信が届き続けた。**Yoshinobu はその会話を一度も見ていない。** 返信は経緯を把握した内容で、設計上の指摘や訂正まで含んでいた。

**気づけなかったのは、返信が届くこと自体が「Operator セッションが受け取った証拠」に見えたためである。** 測れていたのはメッセージが quory のホストに入ったところまでで、どの文脈が読んだかは観測できていなかった。

21:07 JST に quory を再起動しても止まらず、21:14 JST の疎通確認(`TEST-3`)にも自動で返信が来た。

証拠は bridge 自身のログにある。

```
$ grep -nE 'started thread|resumed thread' run/codex-bridge.homelab-ops.operator.log
1:   codex-bridge: resumed thread 01a00a3f-…   [pid 1763963]
201: codex-bridge: resumed thread 01a00a3f-…   [pid 1938142]
249: codex-bridge: resumed thread 01a00a3f-…   [pid 2186432]
250: codex-bridge: resumed thread 01a00a3f-…   [pid 5128]    ← 再起動後
```

**`started thread` は0件。** 新しい会話が作られていたのではなく、**同一のスレッドが4回起こされていた**。再起動を跨いでいるのは、seat の記録がディスクに残るためである。

当のスレッドが自認している(同ログ 255行)。

> TEST-3は手動確認なしでこの文脈へ届いたため、指定どおり `TEST-3 自動` とだけ返信します。TEST-3 自動 と返信しました。再起動後もmonitor自動配送は正常です。

## 原因

3つが重なった。**単独ではどれも事故にならない。**

**1. seat 記録が「人が開いているスレッド」ではなく「記録された時点の thread id」を指す。**
記録の実体は `run/role-session.<team>__<agent>` の1ファイルで、中身は `session=<thread id>`。bridge は起動のたびにこれを `thread/resume` する。**人が同じスレッドを開いているかは条件に入っていない。** ファイルはディスクに残るので再起動でも消えない。

**2. sandbox の例外が、人のいる文脈といない文脈を区別しない。**
`[sandbox_workspace_write] writable_roots` への agmsg の `run` / `db` / `teams` の追加と、agmsg CLI の絶対パス prefix の恒常許可。**どちらも対話セッションが agmsg を使うために必要な対処であり、対処自体は正しい。** しかし人の在否を区別しないため、無人スレッドにも同じ実行能力を与えた。

前後がログに残っている。例外が入る前、同じスレッドは送信できていない。

```
CreateProcess: Rejected("rejected by user")
```

入った後は通っている(同ログ 205 / 207行)。

> 作成した固定prefixルールがASKなしで機能することも同時に確認できます
> 先ほどはスキル読込と送信を1つのcompound commandにまとめたため、固定prefixに一致せず前段で拒否されました。ルール設計どおり、送信コマンド単体で再実行します。

**通る形をスレッド自身が探り当てている。**

**3. requirement が引いた線を、別の経路が跨いだ。**
R5 / AC6 は「常駐するかではなく、**人が見ていないときに AI の文脈へ入るか**」で線を引き、watcher をセッションと共に終わらせることでそれを守る設計だった。**seat 記録という経路がその線を跨ぐことを、requirement は見ていなかった。**

### 補足 — 自動拒否が「人の拒否」として見える

bridge は headless 時に承認要求をすべて自動拒否する(`auto-declining an approval request (headless bridge)`)。**この自動拒否がアプリケーションへは `Rejected("rejected by user")` として返る。** 人は何も押していない。当のスレッドも最初これを Yoshinobu の判断と解釈し、後から「ASKが表示されていない以上、Yoshinobuが拒否したとは判断できません」と自ら訂正している。

## 修正内容

**seat 記録の削除**(Yoshinobu、2026-08-16 に実施)。

```
rm ~/.agents/skills/agmsg/run/role-session.homelab-ops__operator
```

launcher は seat 未記録の role を配送対象から外す(`codex-bridge-launcher.sh` の「A role without a recorded seat has no live TUI to receive its turn.」)。**これで当該スレッドは二度と起こされない。** 戻る状態は「monitor 自動配送が未成立」で、requirement の線から見て安全側である。

**権限側は変えない**(Yoshinobu 判断)。固定 prefix の恒常許可は維持する。

> コマンドは許可するし、実際のデータは機械的な漏洩チェックはする。但し、ai同士の会話を許可制には運用上回りません。

**したがって対策は権限を絞る側ではなく、「無人の文脈を存在させない」側に置く。**

**このリポジトリのコードは変更していない。** agmsg の client は ansible 管理外の第三者製 skill であり、repo が持つのは server 側(`roles/agmsg_server`)だけである。ansy 側にも変更を加えていない。

## 確認方法

2026-08-17 に Coordinator から `homelab-ops` へ1通送り、**自動返信が来ないこと**で確認した。

| | 時刻(JST) | 事実 |
|---|---|---|
| 送信 | 14:39:12 | サーバへ `stored` |
| quory 受領 | 14:40:56 | ローカル store に入った(サーバ側アクセスログで確認) |
| 自動返信 | **無し** | 14:57 時点で17分間、返信なし。quory の sync client は同時刻も稼働中 |

**事故が起きていた間は、同じ経路で 13〜34秒で返信が来ていた。** 受け取れる状態のまま返信が来ないことが、headless 再開が止まったことの確認になる。

## 起動元について

**自動起動は無かった**(2026-08-17 に確認)。quory の `new-session.sh` は tmux と Codex を起こし、sync engine も通常シェルから起動するが、**boot 時に走る仕掛けは無い。** 再起動後に engine と bridge が戻ったのは、**人が手で `new-session.sh` を実行したため**である。

再起動による無音は **42秒**(21:07:25 → 21:08:07 JST)。`uptime` が示す boot 時刻には丸めの幅があり、engine 復帰は boot の **18〜78秒後**の範囲にある。当初「人がセッションを立てるには早すぎる」と読んだが、その幅では人の操作を排除できない。

**したがって残る危険は「何かが勝手に起動すること」ではない。** `new-session.sh` は seat 記録にも残存 bridge にも触れないため、**人が手で起動するたびに、可視スレッドと seat が指す古いスレッドが必ずズレる。** `--reset` も tmux セッションを kill するだけで agmsg 側は掃除しない。**seat を消さない限り、起動のたびに再発する構造である。**
