# Codexの役の起動 Operations Context

作成日: 2026-10-12

## 位置づけ

本書は、ansyのCoordinatorがCodexの役(Implementer・計画Reviewer・Auditor)を起動して結果を受け取る手順の runbook である。禁止・義務はこの手順に閉じる(`docs/ai/context-classification.md`「Operations Context」「Policyとの境界」)。どの役をどのCLIへ置くか、モデルとeffortの値は `docs/ai/roles/coordinator.md`、起動経路の決定は ADR-016、各Roleの責務・権限・成果物は `docs/ai/roles/<role>.md`、承認境界は [`docs/ai/policies/execution_boundary_policy.md`](../../policies/execution_boundary_policy.md) が正本であり、競合時はそちらを優先する。quoryのOperatorとの経路は `docs/ai/context/operations/agent-messaging.md` が扱う。

## 1. 起動は `scripts/codex-role.sh` だけから行う

```bash
scripts/codex-role.sh implementer   [--effort high] --prompt <依頼文> --output <最終メッセージの書き出し先>
scripts/codex-role.sh plan-reviewer --prompt <依頼文> --output <書き出し先>
scripts/codex-role.sh implementer   --resume <session id> [--effort high] --prompt <差し戻し> --output <書き出し先>
scripts/codex-role.sh plan-reviewer --resume <session id> --prompt <再査読の依頼> --output <書き出し先>
scripts/codex-role.sh auditor --case-dir docs/ai/reviews/<target> --start-at docs/ai/reviews/<target>/<file> --output <書き出し先>
```

- **`codex` を直接呼ばない。** PATHの先頭はagmsgのshim(`~/.agents/bin/codex`)で、その先はstandaloneの古い版である。スクリプトは `/usr/bin/codex`(`roles/codex_update_check` が更新するnpm global)を固定で呼び、shimを通るなら止まる。
- **`codex exec resume` は、初回のモデルとsandboxを引き継がない**(2026-10-10実測。再開すると `~/.codex/config.toml` の既定へ戻る)。スクリプトは継続のたびに同じ値を付け直す。
- 新規起動のたびに、session idとそれを作った役・effortを `~/.local/state/codex-role/` に記録する(Codexが非0で終わっても、session idが取れれば記録する)。継続のときに役が違えば、`codex` を呼ぶ前に止まる。effortは記録の値が使われる。標準出力の `codex-role session id:` 行が、次の `--resume` に渡す値である。
- スクリプト自身が入力を拒否したときの終了コードは64で、Codexの終了コードと区別できる。
- `--output` は、呼び出したときのカレントディレクトリを基準に絶対パスへ直される。書き出し先はCoordinatorのscratchpadにする。
- Auditorは案件フォルダと読み始める場所しか受け付けず、継続もできない(`docs/ai/roles/auditor.md` の依頼文の制限)。

## 2. 効いている境界はsandboxである

| 層 | 実体 | `codex exec`(approval `never`)での効き方 |
|---|---|---|
| sandbox | 役ごとの `-s` / `sandbox_mode`、`~/.codex/config.toml` の `[sandbox_workspace_write]` | **境界として効く。** workspace-writeでも `.git` は読み取り専用になる。ネットワークは、スクリプトが `sandbox_workspace_write.network_access=false` を毎回明示して遮断する(設定ファイルの既定に頼らない) |
| 承認ルール | `~/.codex/rules/default.rules`(**repo の `.codex/rules/default.rules` への symlink**) | sandbox内で動くコマンドを拒否しない |

2026-10-12の実測(`docs/ai/reviews/codex_exec_roles/`):

- rulesで `forbidden` にした `git add` / `git commit` は実行され、`.git` が読み取り専用のため失敗した。`git push` も実行され、ネットワークが無いためリモートへ届かない(`git ls-remote origin` も `curl https://github.com` も名前解決で失敗した)。
- Implementerが `.codex/rules/default.rules` を書き換えようとすると、`writing outside of the project; rejected by user approval settings` で拒否された(1件の観測)。rulesの変更はCoordinatorが行う。

**承認ルールは repo にあるが、`~/.codex/config.toml` は無い。** 前者は `.codex/rules/default.rules` として追跡され `git log` で追えるが、**後者は Ansible 管理外で repo からは配備されず、`git` にも現れない。** config.toml を変えたことは案件記録に残す。

**Ansible を扱わせるなら `~/.ansible/tmp` が writable_roots に要る**(Yoshinobu、2026-08-22 に追加)。`ansible-playbook` は既定の一時ディレクトリをここへ作るため、無いと**コードを評価する前に停止する**。

**writable_roots にagmsgのディレクトリを入れない。** 入れると、Implementerがagmsgの `send.sh` でquoryのOperatorへメッセージを送れる。quoryへ送るのはCoordinatorだけである(`agent-messaging.md` §5)。

## 3. 依頼文と成果物

型は [`skills/subagent-briefing/SKILL.md`](../../../../skills/subagent-briefing/SKILL.md) に従い、ここへ複製しない。役の起動指示(「あなたは<役>です。`docs/ai/core.md` と<Role文書>を読む」)はスクリプトが付けるので、依頼文に書かなくてよい。Codex固有として書き添えるのは次の2つである。

- **成果物の置き場** — Implementerは案件フォルダへ書ける。計画ReviewerとAuditorはread-onlyで書けないため、`--output` の最終メッセージをCoordinatorが案件フォルダへ原文のまま転記する。
- **リポジトリを変更してよい範囲**

後者は宣言させるだけでは足りない。**`git status --short --untracked-files=all` で作業ツリーを見て確認する。** 相手の最終報告は、変更していないことの証明にも、**依頼文で列挙した範囲に収まっていることの証明にもならない。**

**本物の `codex` を呼ぶテストを依頼しない。** Implementerのsandboxの中から `codex` を入れ子で起動させない。実機での確認はCoordinatorが行う。

なお、リポジトリ直下の `AGENTS.md` から `docs/ai/core.md` への連鎖は、何も渡さなくても codex 側が自力で辿る。**役を渡さずに起動すると、Codexは `AGENTS.md` に従って役を尋ねて止まる**(2026-10-12実測)。
