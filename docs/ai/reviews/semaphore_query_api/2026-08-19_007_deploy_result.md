# result: quory 配備(`homelab-semaphore-query` の API 移行)

実行: Yoshinobu(quory 上、2026-08-19 朝)
手順: `2026-08-19_006_deploy_procedure.md`
対象 commit: `0196087`

## 結論

**配備は成立した。受入条件は AC10 を除いてすべて満たしている。**

Semaphore ジョブは **#758 / #759 / #760〜#762** の5本、いずれも正常終了。

## 受入条件

| AC | 結果 |
|---|---|
| AC1〜AC4、AC7、AC8 | **ansy で実測済み**(`2026-08-19_002_implement.md` §4) |
| **AC5** dispatch が無変更で動く | **満たす**。`ssh quory-investigate "semaphore-query recent-failed 3"` が版上げ前と同じ3件(675 / 631 / 607)を返す。`task-time` / `task-hosts` / `task-errors` も通る |
| **AC6** incident capture の復旧 | **満たす**(§「最も直接的な証拠」) |
| **AC9** `incident_investigate_run_user` がトークンを読める | **満たす**。quory 上で `homelab-semaphore-query task-time 675` が6フィールドを返す |
| **AC10** LLM が先読みファイルを読む | **未確認。次に incident 調査が実際に走るまで確定しない** |

配備物3件(`semaphore-query` / `incident-capture-collector` / `incident-investigate`)の sha256 は、`deployed-hash` と repo 側でいずれも一致した。

## 最も直接的な証拠

`homelab-incident-capture.service` の journal に、配備をまたぐ遷移が残っている。

```text
10:00  status=2/INVALIDARGUMENT   失敗
10:05  status=2/INVALIDARGUMENT   失敗
10:10  status=2/INVALIDARGUMENT   失敗
10:15  Deactivated successfully   成功
10:20  Deactivated successfully   成功
```

**収集器は5分ごとに失敗し続けており、配備を境に緑になった。** 2026-08-18 20:29 の版上げから約14時間、本番の証拠収集が動いていなかったことになる。手動実行でも `ExecMainStatus=0` を確認した。

**これは同時に2つを裏づける** — ①壊れていたことが推論ではなく実測であること ②直っていること。**そして収集器は黙って壊れていなかった**(非ゼロ終了・run report・heartbeat の `has_errors`)。

## 旧 ACL

`/var/lib/semaphore` に named-user エントリは1つも残っていない(`user::rwx` と `mask::---` のみ)。3識別子とも撤去された。**撤去は各 role が自分の分だけを行う**ため、5本すべてを流すまで完了しない。

## 手順の欠陥(実行中に判明し、手順書へ反映済み)

| # | 何が起きたか |
|---|---|
| 1 | **`dev_investigate_setup`(id=36)を配備リストから落としていた。** Coordinator が pre-commit の「配備が要る」出力をそのまま配備リストにしたため。**あの検査はカタログに載る `copy` 配備物しか見ず**、この role の変更は `tasks` / `defaults` の ACL だけだった。**配備の要否は `git diff --stat` で見る** |
| 2 | **step 0 に実行ディレクトリを書いていなかった。** quory には複数のチェックアウトがあり(Semaphore はジョブごとに `/opt` へ自分で clone する)、別のリポジトリの commit を見て判断できてしまった |
| 3 | **unit 名を推測で書いた**(`incident-capture.service`)。実際は `homelab-incident-capture.service`。**存在しない unit へ `systemctl show` すると既定値の `0` が返る**ため、「Unit not found」の直後に `0` が並んで成功に見える |

## 新設された観測の穴

**`acl-status semaphore-db` は、この配備以降ずっと `Permission denied` を返す。** `dev-investigate` が `/var/lib/semaphore` への traverse を失ったためで、**能力が消えたことの証拠であって異常ではない。**

ただし **「`semaphore.db` に ACL が付け直されていないか」を開発側から観測する手段は失われた。** ACL を消すのが目的である以上、実害は小さいが、**付け直されても分からない**という性質は記録しておく。

## recovery-exec 側の経路も通った(2026-08-19)

**`roles/recovery_exec/templates/AGENTS.md.j2` の Semaphore 節は今回の差分で書き換えたが、配備まで一度も実行していなかった。** Slack 経由で recovery-exec の Codex へ直近の失敗ジョブを尋ね、**dispatch 経由で見えるものと完全に一致する3件(675 / 631 / 607、playbook・状態・時刻とも)** が返った。

これで3つが同時に確定した。

1. `recovery-exec` のトークン ACL が効いている
2. **`workspace-write` + `network_access = true` の Codex sandbox から API へ到達できる**(incident-inspect 側の `read-only` とは設定が違う)
3. 書き換えた `AGENTS.md` の記述で、LLM が実際に正しく使える

**incident-inspect 側の AC10 はこれでは埋まらない。** sandbox の種類が違い、あちらは通信を塞いだうえで先読みファイルを読ませる設計である。

## 残るもの

**AC10 のみ。** 次に Semaphore ジョブが失敗して incident 調査が動いたとき、その成果物で Semaphore の情報が引用できているかを見る。
