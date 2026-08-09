# Agent Messaging (agmsg) Operations Context

作成日: 2026-08-09

## 位置づけ

本書は、Coordinator(Claude Code)から **codex 側の Reviewer へ依頼を通すための連絡経路**を扱う**非規範runbook**である。各Roleの責務・権限・成果物は `docs/ai/roles/<role>.md` が、承認境界は [`docs/ai/roles/coordinator.md`](../../roles/coordinator.md)「実ホストへの非冪等操作の承認」が正本であり、競合時はそちらを優先する。IP、認証情報、秘密情報の実値は記載しない。

## 1. 構成

agmsg 本体・team定義・メッセージDBは、いずれも**リポジトリの外**(`~/.agents/skills/agmsg/`)にある。upstream は `github.com/fujibee/agmsg`。**導入版はここへ写さない** — `scripts/version.sh` が持つ。

team `homelab` に2者が登録されている。

| 識別子 | type | project |
|---|---|---|
| `claude` | `claude-code` | `/home/yoshi/homelab-ansible` |
| `reviewer` | `codex` | 同上 |

**成果物をagmsgのメッセージだけに残さない。** 監査証跡は `docs/ai/reviews/<target>/` 配下のファイルであるという `docs/ai/core.md` の定めは、依頼先がcodexでも変わらない。メッセージDBはリポジトリ外にあり、`git log` からも案件記録からも辿れない。

## 2. codex 側へ配送が届く条件

**次の4つが全部揃って初めて届く。1つでも欠けると、エラーを出さずに配送だけが成立しない。**

1. delivery mode が `monitor`(`delivery.sh set monitor codex <project>`)
2. シムが存在する(`drivers/types/codex/codex-shim-install.sh install` → `~/.agents/bin/codex`)
3. `~/.agents/bin` が PATH にある。**`~/.bashrc` の非対話ガードより上に置くこと** — 末尾へ追記しても非対話シェルは冒頭で `return` するため無言で効かない
4. codex の「Hooks need review」プロンプトで hook を信頼済みである。未信頼だと hook が走らず、bridge があっても配送はセッションへ入らない

2 が欠けると `spawn.sh` は `type.conf` の `cli=codex` を PATH で解決して素の codex を起動する。**spawnは成功を返し、ペインは開き、codexは正常に動く。** boot promptで渡した仕事はこなすので、「後から送ったメッセージだけが届かない」という形で現れる。

4 の信頼は hooks ファイルの**内容**に対して与えられる。`.codex/hooks.json` が変われば再び聞かれる。

## 3. `alive` は配送の成立を保証しない

`delivery.sh status` が出す `Codex bridge: <team>/<name> alive (pid ...)` は、**hook未信頼で配送が届かない間も出続けた**。信頼を与えた前後で、この表示は一度も変わっていない。

**返事が来ないとき、`alive` を健全の根拠にしない。** 確かめるのは次の2つである。

- `history.sh <team>` の既読マーク — `●` が未読、`○` が配送済み
- 相手ペインの実際の反応(`tmux capture-pane -p -t <pane>`)

## 4. spawn と despawn

```bash
spawn.sh codex <name> --team <team> --split h --fresh --boot-prompt "<依頼文>"
despawn.sh <team> <from> <name> [--force]
```

- **`--fresh` を省くと、記録済みスレッドを `resume` する。** 古い transcript を再生した状態でプロンプトに止まり、新しい boot prompt は実行されない
- codex には spawn の readiness handshake が無く、`--no-wait` が常に暗黙に効く
- `--force` で畳むと transcript は残らない。**後から原因を調べる必要があるものは、畳む前に `tmux capture-pane` で控える**

## 5. 権限の層

codex 側には2つの層があり、どちらもリポジトリ外にある。**症状が似ているので取り違えない。**

| 層 | 実体 | 何を決めるか |
|---|---|---|
| 承認ルール | `~/.codex/rules/default.rules` | コマンドを許可するか、都度プロンプトを出すか |
| sandbox | `~/.codex/config.toml` の `[sandbox_workspace_write]` | 書き込んでよいパス |

**この2層は、Coordinator側の `.claude/settings.json`(`permissions` / `autoMode`)に対応する。** 両者を非対称にしない — 一方だけを広げると、Role文書が同じことを定めていても実効的な能力が食い違う。

## 6. 依頼文

型は [`skills/subagent-briefing/SKILL.md`](../../../../skills/subagent-briefing/SKILL.md) に従い、ここへ複製しない。codex 固有として書き添えるのは次の2つである。

- **成果物の返し先** — agmsg で返させるのか、`docs/ai/reviews/<target>/` へ書かせるのか
- **リポジトリを変更してよいか**

後者は宣言させるだけでは足りない。**`git status --short --untracked-files=all` で作業ツリーを見て確認する。** 相手の最終報告に「変更していない」と書かれていることは、変更していないことの証明ではない。

なお、リポジトリ直下の `AGENTS.md` から `docs/ai/core.md` への連鎖は、何も渡さなくても codex 側が自力で辿る(2026-08-09 実測)。共通原則を依頼文へ複製する必要はない。
