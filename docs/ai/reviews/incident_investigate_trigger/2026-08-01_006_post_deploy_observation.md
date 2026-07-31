# post_deploy_observation: 起動契機切り替えの本番配備後観測

日付: 2026-08-01
Tester: Claude Code subagent(tester role)。実装・レビュー・配備前検証(`2026-07-31_004_test_result.md`)には関与していない別セッション。
対象契約: `docs/ai/reviews/incident_investigate_trigger/2026-07-31_001_requirement.md`(AC1・AC2・AC3・AC6・AC7)。
親Incident: `docs/ai/memory/incidents/2026-07-31_incident-investigate-callback-did-not-enqueue.md`「確認方法」節の配備後観測3点。
Policy: `docs/ai/policies/incident_capture_policy.md` §3.5(IC-034〜IC-042)。

配備は2026-08-01早朝にYoshinobuが実施済み(commit / push / quoryでの `git pull --ff-only` / `playbooks/incident_investigate_setup.yml` 再実行)。本記録はその後quoryをread-onlyで観測した結果。**quoryへの非冪等操作、権限昇格、`sudo`は一切行っていない。**

## 総括

| 観測項目 | 判定 | 一言 |
|---|---|---|
| 1. 通過側(AC1、成果物スキーマ、IC-040/IC-042) | **PASS(実測)** | `semaphore-495`含む滞留バンドル10件すべてが拾われ成果物が生成された。スキーマ完全一致、生ログ転記・内部IP・修正差分・被疑パスいずれも検出されず |
| 2. 非通過側(AC2) | **PASS(実測、時間を空けた2回観測)** | `semaphore-495.json` のsha256・mtimeが約5分の間隔を空けた2回の観測で完全不変。成果物の重複なし |
| 3. callback未読込(キューディレクトリへの新規キューファイル) | **観測不能** | ディレクトリ自体が `ann` からは `stat` すら不可(0750 yoshi:yoshi、`ann` はother)。権限昇格は行っていない。間接シグナルとして `ansible.cfg` に `callback` 行が無いこと(grep rc=1)を実測 |
| systemd `is-failed` | **`activating`/`inactive` を観測、`failed` は一度も観測せず** | `systemctl show` で直近実行(`ExecMainStartTimestamp=2026-08-01 05:43:04`)は `Result=success` / `ExecMainStatus=0` |
| AC3(72時間閾値) | **PASS(実測)** | 72h超の `semaphore-466/467/469` 等は成果物なし。72h以内の `semaphore-473`(閾値の約15分後)は成果物あり |

## 観測1: 通過側(AC1)

quoryの `reports/incidents/_investigations/` を確認した(`ansible quory -m command -a "ls -la ..."`、2026-08-01 05:37 JST時点)。

```
semaphore-473.json/.md  (2026-08-01 05:30)
semaphore-474.json/.md  (05:31)
semaphore-476.json/.md  (05:32)
semaphore-479.json/.md  (05:33)
semaphore-480.json/.md  (05:34)
semaphore-482.json/.md  (05:35)
semaphore-495.json/.md  (05:36)  ← 親Incidentで滞留していたバンドル
semaphore-496.json/.md  (05:37)
```

その後(05:38〜05:39)に `semaphore-497.json/.md`・`semaphore-498.json/.md` も追加で生成され、最終的に72時間以内の全未調査バンドル10件(473, 474, 476, 479, 480, 482, 495, 496, 497, 498)が処理された。**`semaphore-495` は契約§7の「切り替え後の最初の対象として拾われる」対象そのものであり、実際に成果物(`semaphore-495.json`)が生成されたことを確認した。**

`semaphore-495.json` の内容:

```json
{
  "schema_version": 1,
  "semaphore_task_id": 495,
  "template": "SEMI-SAFE:Cert_renew (only on Quory)",
  "playbook": "playbooks/cert_renew.yml",
  "job_status": "error",
  "investigated_at": "2026-08-01T05:36:34+09:00",
  ...
  "status": "new",
  "llm_rc": 0
}
```

生成順序は `semaphore-<id>` のディレクトリmtime昇順(473→474→476→479→480→482→495→496→497→498、実バンドルのmtimeとファイル名昇順が完全一致)で、1分毎に1件ずつ処理されている(AC4「1周期1件」・AC5「古い方から」がそのまま本番でも観測できた。契約範囲外だが同時に確認できた)。

### スキーマ検証(契約§7)

10件全ての `.json` を `ansible quory -m fetch` でscratch(`/tmp/claude-1000/.../scratchpad/post_deploy_obs/`)へ取得し、Pythonで必須フィールド14個(`schema_version`, `semaphore_task_id`, `template`, `playbook`, `job_status`, `investigated_at`, `observations`, `verdict`, `confidence`, `evidence_refs`, `known_condition`, `status`, `llm_rc`, `notes`)との突合を行った。

**結果: 10件すべてで欠落フィールド0・余剰フィールド0。** `status` は10件とも `"new"`、`llm_rc` は10件とも `0`(LLM呼び出し成功)。`investigated_at` はすべてRFC3339・JST(+09:00)形式。

### IC-040(生ログ転記なし、内部IP・認証情報なし)・IC-042(修正差分・被疑パスなし)の確認

取得した10件の `.json` + `.md`(計20ファイル)に対し以下をgrepで機械的に確認した。

- IPv4パターン(`([0-9]{1,3}\.){3}[0-9]{1,3}`): **0件ヒット**
- `password` / `token` / `secret` / `apikey` / `-----BEGIN`(秘密鍵ヘッダ) / `suspect_path` / unified diff記法(`--- a/` `+++ b/` `diff --git`): **0件ヒット**

さらに `semaphore-497.md` と `semaphore-473.json` の全文を目視確認した。`observations` / `notes` はいずれも「pve1がunreachable」「クラスタはquorate」「maintenance modeとして観測」等、証拠バンドルから読み取れる事実の要約であり、ログの行そのものの転記(タイムスタンプ付きの生の1行1行)は無い。`evidence_refs` はパスのみで内容の複製は無い。`notes` には `"model notes: 内部IPアドレスは出力から省略した"` 等、LLM自身がIC-040を意識した記述が明示的に含まれていた。**IC-040・IC-042いずれの違反も確認されなかった。**

## 観測2: 非通過側(AC2、時間を空けた2回観測)

1回目観測(2026-08-01 05:39頃、`semaphore-495.json` 生成の約3分後):

```
sha256: 583afb8b715251bbe2a2b0ab8e5a62550204ddee2eb2b18a8d706fd81dca6ebe
mtime (epoch): 1785530194
```

その後quoryに新規バンドルが投入されていないこと・タイマーが継続稼働していることを確認しつつ約100秒待機し、2回目観測(2026-08-01 05:42頃)を実施:

```
sha256: 583afb8b715251bbe2a2b0ab8e5a62550204ddee2eb2b18a8d706fd81dca6ebe  (完全一致)
mtime (epoch): 1785530194  (完全一致)
```

`_investigations/` のディレクトリ一覧も2回とも同一(新規ファイル無し、重複ファイル無し)。**この間、timerは複数回起動しており(後述`ExecMainStartTimestamp=05:43:04`)、`semaphore-495` は既に調査済みとして再投入されなかったことが確認できた。** AC2契約どおり、内容不変で観測した。

## 観測3: callbackが読み込まれていないこと(キューディレクトリ)

**直接観測は不能。** `/var/lib/homelab-recovery/incident-investigate/queue` は親ディレクトリ `/var/lib/homelab-recovery/incident-investigate` が `0750 yoshi:yoshi` であり、`ann`(quory接続identity)は `stat` すら実行できなかった:

```
$ ansible quory -m command -a "stat /var/lib/homelab-recovery/incident-investigate/queue"
stat: cannot stat '/var/lib/homelab-recovery/incident-investigate/queue': Permission denied (os error 13)
```

タスク指示に従い、**権限昇格・`sudo`は試みていない。** 代替として `ann` の権限で取得できる間接シグナルを確認した。

- **`ansible.cfg` にcallback関連行が存在しない**(quory上の実ファイル): `grep -n -i callback ansible.cfg` は `rc=1`(no match)で終了。
- quoryのgitヘッド: `b52aa4cf32cf75e5e1b6cb33155432c20d4c48f5`(2026-08-01T05:27:07+09:00)。配備反映後のコミットであることを確認(`git status --porcelain` も空、作業ツリーはクリーン)。

この2点は「callback pluginを無効化する設定が実際にquoryへ配備されている」ことの証拠であり、契約AC6の配備前検証(scratchでの対照実験、`2026-07-31_004_test_result.md`)と組み合わせれば「効かないはずの設定が効く形で配備された」ことの合理的根拠になる。ただし**キューディレクトリへ新規ファイルが現れていないことそのものの直接確認ではない**ため、これは代替であって同値ではない。

## 走査後の状態確認

### `systemctl is-failed homelab-incident-investigate.service`

5回、20秒間隔で観測した。結果は `inactive` または `activating` の往復で、**`failed` は一度も観測されなかった**。

```
1回目: inactive
2回目: activating
3回目: activating
4回目: inactive
5回目: inactive
```

`is-failed` はrc非ゼロ(1)を返すため `ansible -m command` 上は `FAILED` 表示になるが、これは「failedでない」ことを示すsystemctlの仕様であり、出力テキスト自体が `failed` でないことをもって非failedと判定した。

`systemctl show` での直接確認(2026-08-01 05:43時点、直近の起動):

```
ActiveState=inactive
SubState=dead
Result=success
ExecMainStartTimestamp=Sat 2026-08-01 05:43:04 JST
ExecMainExitTimestamp=Sat 2026-08-01 05:43:04 JST
ExecMainStatus=0
```

**成果物側の `status: failed` はゼロ件**(10件全て `status: "new"`、`llm_rc: 0`)。したがって「`is-failed` がfailedを返す一方で成果物に失敗調査が無い」という契約AC7/IC-038上の矛盾は発生していない。逆に「`is-failed` がfailedを一度も返さず、成果物にも失敗調査が無い」ことが整合している状態であり、突合の結果は**一致(矛盾なし)**。

### AC3(72時間閾値)

`reports/incidents/` の全バンドル一覧(`ls -1`)から、72時間窓の内外を突合した。

- 72時間超(観測時点2026-08-01 05:4x基準、閾値カットオフはおよそ2026-07-29 05:3x): `semaphore-466`(07-28 05:45)・`semaphore-467`(07-28 05:50)・`semaphore-469`(07-28 18:35)、および更に古い `semaphore-114`〜`semaphore-461` 等多数 → **いずれも `_investigations/` に対応する成果物なし**
- 72時間以内: `semaphore-473`(07-29 05:45、カットオフの約15分後)〜`semaphore-498`(08-01 00:10) → **10件すべてに成果物あり**

閾値の境界(`semaphore-469` は除外・`semaphore-473` は含む)が実バンドルのmtimeと整合しており、**古いバンドルが調査されていないことを本番で確認した。**

## 未実施・観測不能事項とその理由

1. **キューディレクトリへの新規キューファイル非生成の直接確認**: 権限上不能(上記)。代替として `ansible.cfg` の実配備確認とgit headの確認を行った。将来この点を直接確認する必要が生じた場合は、`yoshi` identityでの確認が要る(親Incidentの既存の教訓と同じ)。
2. **journalctlでの `homelab-incident-investigate.service` のログ内容確認**: `ann` は `adm`/`systemd-journal` グループに属さないため `journalctl -u ...` は空(`--q`無しの警告どおり)。`systemctl show` の集計フィールドで代替した。
3. **本セッションでは新規バンドルの投入(自然発生の新規失敗)は観測していない。** 今回処理された10件はいずれも配備前からの既存滞留分(72時間以内)であり、契約§9「実発火の観測は自然発生の失敗を待つ」の「配備後の新規失敗」自体はまだ発生していない。今回の観測は「滞留分の一括処理」の確認であり、「配備後に新規発生した失敗が拾われること」はこの観測の範囲外(今後のWatch対象)。

## 残存リスク

- キューディレクトリの直接観測ができないままであるため、「callbackが本当に一切実行されていない」ことの最終的な保証は間接証拠(`ansible.cfg` 実配備確認)に留まる。ゼロではないが、契約AC6の配備前対照実験(同一コードで2行の有無だけが分岐点であることを実測済み)と合わせれば残存リスクは小さいと判断する。
- 現時点でquoryに設置されている全バンドルが72時間以内に処理し切られたため(バックログ枯渇)、以後は新規失敗が発生するまで新しい観測機会が無い。次の実発火はWatch対象として自然発生を待つ。
- `status: failed` の成果物が今回の10件には1件も含まれなかったため、AC7/IC-038(失敗の可視化)そのものは配備前検証(`2026-07-31_004_test_result.md`)のfixtureでのみ確認済みであり、**本番の実失敗系での確認はまだ無い**。

## 後片付け

fetchしたファイルはすべて `/tmp/claude-1000/-home-yoshi-homelab-ansible/ee439bc9-7197-4dc5-8586-8b431421f8e4/scratchpad/post_deploy_obs/` 配下(scratch)に閉じている。quoryへは読み取り専用コマンド(`ls`/`cat`/`stat`/`sha256sum`/`systemctl show`/`git status`/`git log`/`grep`)のみ実行し、状態変更・権限昇格・`sudo`は行っていない。quoryの `git status --porcelain` は空(作業ツリー無変更)。リポジトリ(このファイル)への追加以外、作業ツリーへの変更は無い。`git add`/`commit`/`push`は行っていない。

---

## 追記(2026-08-01 06:0x、Coordinator観測): 自然発生した失敗での初発火

本文が「残存リスク」として挙げていた「配備後に自然発生した新規失敗での実発火はまだ観測できていない」は、**同日中に観測できた**。

| 項目 | 値 |
|---|---|
| 対象 | `semaphore-507`(`UN-SAFE:Proxmox Weekly Full Patch`、`job_status: error`) |
| バンドル生成(`summary.json` mtime) | 2026-08-01 06:05:11 JST |
| 調査完了(`investigated_at`) | 2026-08-01 06:06:45 JST |
| 所要 | **94秒** |
| 成果物 | `status: new` / `confidence: high` / `known_condition.suspected: true` |

**これは切り替え前から滞留していたバンドルではなく、配備(同日05:27頃)より後に発生した失敗である。** 「捕捉が5分周期でバンドルを作る → 毎分の走査が拾う」経路が、`task-time` の確定との競合を含めて本番で成立した。`docs/ai/status.md` の該当Watch行は削除した。

**残るのは `status: failed` の本番実測のみ**である(2026-08-01時点で本番の成果物11件はすべて `status: new`)。
