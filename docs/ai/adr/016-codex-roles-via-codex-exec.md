# ADR-016: Codexの役をagmsgのpane常駐から `codex exec` の呼び出しへ移す

**Status:** Accepted

## Context

ADR-015は、Codexの役を次の起動経路で動かすと決めた。

- Implementer: tmux pane 1に常駐し、agmsgでCoordinatorとやりとりする。
- 計画ReviewerとAuditor: 案件ごとにagmsgの `spawn.sh` でfresh起動し、終わったら `despawn.sh` で畳む。

この経路は、agmsgのseat・actasロック・Codexのbridgeに依存する。2026-08-16から2026-10-10までに、この依存が原因のIncidentが9件起きた(`docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md`)。2026-10-10には、Implementerが `--reset` 後に3回続けて起動しなかった。原因は、agmsgがCodexのsandbox内で取ったロックの持ち主をPID 1と記録し、永久に「生存」と判定したことにある。最新版のagmsgでも直っていない。

2026-10-10〜12に、計画ReviewerとImplementerを `codex exec` で動かす試行をした。依頼・差し戻し・結果の受け取りがCoordinatorの呼び出しの中で完結し、seat・ロック・pane・bridgeを使わずに実用になった(`docs/ai/reviews/agmsg_replacement/`、`docs/ai/reviews/codex_exec_roles/`)。

決めるべきことは、Codexの役をどの経路で起動するかである。ansyとquoryの経路(team `homelab-ops`、CoordinatorとOperator)は本ADRの対象外とする。

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| agmsgを最新版へ上げて続ける | 起動経路を変えなくてよい | PID 1のロックは最新版でも直っていない。seat・bridgeの状態ずれ型の不具合が続く |
| herdr(エージェント向けの端末多重化)へ移す | paneの管理とエージェントの状態把握に向く | pane常駐の形は残り、配送の仕組みを別に要る。公開から日が浅く、手元で試していない |
| **`codex exec` / `codex exec resume` でCoordinatorが呼び出す** | **seat・ロック・pane・bridgeが無くなる。** Codexへ指示できるのが呼び出したCoordinatorだけになる | 呼び出しと呼び出しの間にCodexのプロセスは生きていない。`resume` はモデルとsandboxを引き継がない |

## Decision

Yoshinobuの承認(2026-10-12)により、Codexの役(Implementer・計画Reviewer・Auditor)は `scripts/codex-role.sh` から `codex exec` で起動する。ADR-015のうち、次の決定を置き換える。

- 「Implementerはtmux pane 1に常駐する」 → 案件ごとに `codex exec` で起動し、差し戻しは `codex exec resume` で同じセッションへ続ける。
- 「計画ReviewerとAuditorはagmsgでfresh起動して畳む」 → 案件ごと(Auditorはクローズ時に1回)に `codex exec` で起動する。

ADR-015のそれ以外の決定(どの役をどちらのCLIへ置くか、計画ReviewerをCodexへ残す理由、モデルとeffortの値)は変えない。

`scripts/codex-role.sh` は次を固定する。

| 役 | model | effort | sandbox | 継続 |
|---|---|---|---|---|
| Implementer | `gpt-5.6-terra` | medium(案件ごとにhighへ上げられる) | workspace-write | 可 |
| 計画Reviewer | `gpt-5.6-sol` | medium | read-only | 可 |
| Auditor | `gpt-5.6-sol` | medium | read-only | 不可 |

- 実行するバイナリは `/usr/bin/codex`(`roles/codex_update_check` が週次で更新するnpm global)に固定する。PATHの先頭にあるagmsgのshimを経由しない。
- 依頼文の先頭に、役とRole文書を読ませる起動指示を付ける。
- session idを、それを作った役に結びつけて記録し、違う役での継続を拒否する。計画ReviewerとImplementerが別identityであることを、引数1つで破れないようにする。
- Auditorへは、案件フォルダと読み始める場所しか渡せない。

計画ReviewerとAuditorはread-onlyで動くため、成果物のファイルを書けない。最終メッセージを `--output` で受け取り、Coordinatorが案件フォルダへ原文のまま転記する。

## Trade-off Analysis

- **境界はsandboxが担う。** 2026-10-12の実測で、`codex exec`(approval `never`)では `.codex/rules/default.rules` の `forbidden` が、sandbox内で動くコマンドを拒否しなかった(`git add` は実行され、`.git` が読み取り専用のため失敗した)。Implementerが `git add` / `commit` できないのは、sandboxが `.git` を読み取り専用にしているからである。`git push` がリモートへ届かないのは、ネットワークが遮断されているからである(DNSが引けず、`git ls-remote` も失敗した)。ネットワークの遮断は `~/.codex/config.toml` の既定に頼らず、`scripts/codex-role.sh` が `sandbox_workspace_write.network_access=false` を毎回明示する。Implementerによる `.codex/rules/default.rules` の書き換えは拒否された。rulesは、対話で動かすCodexに対する宣言として残す。
- **呼び出しの間にプロセスが生きていない。** Implementerの作業は1回の呼び出しの中で完結させる。会話の文脈は `resume` で引き継がれる(実測で、差し戻しが前回の作業ツリーの変更を前提に正しく続いた)。
- **`resume` は設定を引き継がない。** 継続のたびにモデル・effort・sandboxを付け直す必要があり、`scripts/codex-role.sh` が必ず付ける。
- **常駐のpaneが無くなる。** Implementerの作業の様子を端末で眺めることはできなくなる。呼び出しの出力はCoordinatorが受け取る。

## Consequences

- ansyのtmuxはpane 0(Coordinator)だけになる。`new-session.sh` はImplementerを起動しない。
- agmsgのteam `homelab` は使わなくなる。Coordinatorの席はteam `homelab-ops` だけになり、セッション開始のhookが受信の監視を自分で始められる。
- `scripts/codex-role.sh` の役ごとのmodel・effortと、`docs/ai/roles/coordinator.md` の配分表の一致は、`scripts/check-doc-consistency.py` のcheck4が検査する。
- Codexのsandboxの書き込み可の場所から、agmsgのディレクトリを外す。Implementerがhomelab-opsへメッセージを送れないようにするためである。
- 過去のADRと案件記録は当時の判断として書き換えない。
