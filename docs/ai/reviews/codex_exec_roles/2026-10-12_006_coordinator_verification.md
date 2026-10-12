# Coordinatorの実機確認(repo内の変更分)

実施日: 2026-10-12

R5(repo外の変更)より前の状態で確かめた分である。AC6・AC7とR5適用後のAC1・AC5の再実行は、R5の実施後に別の記録へ書く。

## AC1・AC1b: 3つの役が指定どおりに起動する

`scripts/codex-role.sh` で3つの役を同時に起動し、出力の見出しを確かめた。

| 役 | 呼び出し | model | sandbox | reasoning effort | 起動指示のRole文書 |
|---|---|---|---|---|---|
| implementer | `--prompt <依頼> --output <絶対パス>` | gpt-5.6-terra | workspace-write | medium | `docs/ai/roles/implementer.md` |
| plan-reviewer | 同上 | gpt-5.6-sol | read-only | medium | `docs/ai/roles/reviewer.md` |
| auditor | `--case-dir docs/ai/reviews/ubuntu_full_upgrade_warning_drop --start-at <requirement>` | gpt-5.6-sol | read-only | medium | `docs/ai/roles/auditor.md` |

- 3つとも `OpenAI Codex v0.162.0`、`workdir: /home/yoshi/homelab-ansible` で動いた(`/usr/bin/codex`)。
- 3つのsession idが `~/.local/state/codex-role/` に記録された。
- Auditorは実際に監査を行い、`ubuntu_full_upgrade_warning_drop` の観測待ちが `docs/ai/status.md` に無いことを指摘した(`ubuntu_full_upgrade_warning_drop/2026-10-12_004_audit.md`)。status.mdへの追加は本案件のcommitに含めた。
- 継続(`--resume`)での値の付け直しは、計画査読の2回目・3回目(`_003`、`_004`)で、スクリプトと同じ引数を直接与えて確かめた(model `gpt-5.6-sol`、sandbox `read-only`)。スクリプト経由の継続は、偽のcodexのテストで引数を確かめている。

## AC4: Implementerが `git add` / `commit` / `push` を実行できない

使い捨てのgitリポジトリ(scratchpad配下、pushはローカルのbareリポジトリ宛て)で、Implementerと同じ設定(`gpt-5.6-terra`、workspace-write)のCodexに3つを実行させた。

| コマンド | 結果 |
|---|---|
| `git add a.txt` | 失敗(exit 128)。`.git/index.lock` を作れない — `Read-only file system` |
| `git commit -m test` | 失敗(exit 128)。同上 |
| `git push origin HEAD` | exit 0、`Everything up-to-date`。commitが作れないため送るものが無い。ref更新は `Read-only file system` で失敗 |

**`.codex/rules/default.rules` の `forbidden` は拒否として効かなかった。** 3つともコマンドとしては実行され、止めたのはsandboxである。2026-07-31のIncident(`docs/ai/memory/incidents/2026-07-31_codex-execpolicy-allowlist-not-enforcing.md`)と同じ性質である。

本物のrepoでCoordinatorの未pushのcommitを押し出せるかは、ネットワークに出られるかで決まるため、続けて確かめた(`scripts/codex-role.sh implementer` で起動)。

| コマンド | 結果 |
|---|---|
| `git ls-remote origin HEAD` | 失敗(exit 128)。`Could not read from remote repository` |
| `curl -sS -o /dev/null -w '%{http_code}' https://github.com` | 失敗(exit 6)。`Could not resolve host: github.com` |

**結論: AC4は満たす。ただし境界はrulesではなくsandboxである**(`.git` が読み取り専用、ネットワーク遮断)。ADR-016と `docs/ai/context/operations/codex-roles.md` §2 にこの前提で書いた。rulesのコメントも実態に合わせた。

## AC5: 差し戻しを `resume` で続けられる

Implementerの1回目の実装(`_005` の本体)に対し、Coordinatorが2点の不具合を見つけ、Implementerの同じセッション(`01a12ead-65d1-7ba2-8ae2-c4d078d5563f`)へ `codex exec resume` で差し戻した。

- 継続した `codex exec resume` では、`-` を明示して標準入力から差し戻しを渡した。
- Implementerは前回の作業ツリーの変更(`scripts/codex-role.sh` ほか)を前提に、指摘の2点だけを直し、テストを足し、実装記録へ差し戻し対応の節を追記した(`_005`「差し戻し対応」)。
- **差し戻した不具合の1つは、継続で依頼文が届かないことだった**(`codex exec resume` はPROMPT引数に `-` を渡さないと標準入力を読まない)。偽のcodexのテストでは検出できず、`--help` を読んで見つけた。テストは「`-` を受け取ったか」を検査する形に直した。

## AC2・AC3・AC4b・AC4c

`scripts/tests/codex_role/run-tests.sh`(偽のcodex)で確かめた(Implementer実施、Coordinatorが再実行してPASS)。AC3はstage後に `scripts/check-doc-consistency.py` の check4 が `OK (6 compared)` になることも確かめた。

## AC3b・AC3c

- AC3b: `git grep` で、現行の規範・Context・スクリプト・`.codex/rules` に、ansy内の `spawn.sh` / `despawn` / pane 1 / `AGMSG_SPAWNED` / Codexの役のagmsg配送を現行として書いた記述が残っていないことを確かめた(該当は `agent-messaging.md` の「ansy内のCodexの役はagmsgを使わない」という位置づけの1文だけ)。
- AC3c: ADR-016の「Decision」が、ADR-015のどの決定を置き換えるかを2点列挙している。ADR-015はこのcommitで変更していない。

## 範囲外として見つけたこと

- `.codex/rules/default.rules` は `ssh` と `ansible-playbook` も無条件に `allow` している。`codex exec` の経路ではネットワーク遮断のため実ホストへ届かないが、対話で動かすCodexには効く宣言である。本案件では扱わない。
- `.codex/rules/default.rules` は `bash scripts/oprc-submit.sh` を `allow` していた。OPREQの登録とOperatorへの通知はCoordinatorの行為なので、本案件で `forbidden` へ変えた(requirementのR3の趣旨に含めた)。

## 追記: ネットワーク遮断の明示が効くこと(差分レビュー `_007`・`_008` の未確認への対応)

`scripts/codex-role.sh` は2回目の差し戻しで、新規・継続とも `-c sandbox_workspace_write.network_access=false` を渡すようになった。本物の `codex` 0.162.0 がこのキーを解釈するかを確かめた。

- スクリプト経由でImplementerを起動し、`curl https://github.com` を実行させた。`Could not resolve host: github.com` で失敗し、rolloutの `turn_context` の `sandbox_policy.network_access` は `false` だった。役の記録は `implementer<TAB>medium` の新形式で残った。
- 既定値もfalseのため、上だけではキーが読まれた証拠にならない。同じキーに `true` を渡して `codex exec` を起動すると、`turn_context` の `network_access` が `true` になった。**キーは解釈されており、スクリプトの明示が設定ファイルの既定に優先する。**
