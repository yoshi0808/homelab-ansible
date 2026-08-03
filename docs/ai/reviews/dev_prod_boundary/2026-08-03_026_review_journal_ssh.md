# Review: `journal-ssh` 追加 + class Q `deployed-hash` 対応表への `worktree-sync` 追加

日付: 2026-08-03 (JST)
対象: `git diff --cached`(9ファイル、commit前)
契約: `docs/ai/reviews/dev_prod_boundary/2026-08-03_008_phase3_check_catalog.md` §7(D7、2026-08-03承認)+ §0 不変条件 I-1〜I-7
背景: 同フォルダ `2026-08-03_023_test_result_phase4.md` 末尾 Coordinator 追記

## 確認した手段(状態を変えない確認のみ)

- `git diff --cached` の9ファイル全件を読んだ(`docs/ai/status.md`、契約書、実装5ファイル、AGENTS.md.j2)。
- 3つの dispatch 実装(class Q: `roles/dev_investigate/files/recovery-investigate-dispatch-quory.sh`、class G: `roles/recovery_exec/templates/recovery-investigate-dispatch.sh.j2`、class P: `roles/recovery_exec/templates/recovery-investigate-dispatch-pve.sh.j2`)の `journal-ssh` アームを、既存の `journal-unit` アームの実装(since_value マッピング、arity検査、`_is_valid_unit` 呼び出しの有無)と行単位で突き合わせた。
- `sudoers-recovery-exec-pve-target.j2` の新規1行を、既存5行(`journal-unit` 用)およびファイル冒頭のコメント(sudoの fnmatch は空白を跨ぐ空白結合文字列比較である旨)と突き合わせた。
- 2本の Codex 側 wrapper(`homelab-investigate.sh.j2` / `homelab-investigate-pve.sh.j2`)の `journal-ssh` アームの `argc` 判定を、同ファイル内の他アーム(`argc == 2` 等の既存慣習)と突き合わせた。
- `~/.ssh/config` を読み、`*-investigate` の4エイリアスが class G/P では同一ユーザー `recovery-exec` ・同一 dispatch スクリプトへ到達すること(Codex用 wrapper 経由でも Claude Code の直SSHでも同一ファイルが実行される)を確認した。class Q(`quory-investigate`)のみ別ユーザー `dev-investigate` ・別スクリプトであることを確認した。
- `roles/worktree_sync/defaults/main.yml` の `worktree_sync_script_path: /usr/local/sbin/worktree-sync.sh` を読み、`deployed-hash` 新規エントリのパスがrepo側の定義と一致することを確認した(契約書の「`unit-cat` の `ExecStart` で実測した」という主張はこちらでは検証していない=未確認)。
- `_is_valid_unit`(class Q の共有 enum)の行番号を grep し、`journal-ssh` アームがこの関数を一切呼んでいないことを確認した。
- bash の `case` パターンの順序・catch-all(`*)`)の位置を目視確認し、新規アームが既存アームより先にマッチして意図せずシャドーイングする経路がないことを確認した。

**未確認・実施していないこと**:
- §7.1 の実機 unit 実測表(pve1/pve2 の `ssh.socket` disabled、quory/monnie/authy の `ssh.socket` enabled)は Coordinator が dispatch 経由で測った値であり、**自分では確かめていない**。前提として使用した。
- 実ホストへの接続・実行は一切行っていない(指示どおり `ssh *-investigate` を含め未実施)。
- `sudo -n` が実際に成功するか(pve側のtty制約等)は実機依存であり未確認。

## Summary

`journal-ssh <window>` の追加と `deployed-hash` への `worktree-sync` 1件追加は、いずれも契約書 §7 の記述と実装が一致しており、read専用の不変条件(I-1〜I-7)を壊す変更は見当たらなかった。sudoers の追加行は既存5行と同一の書式・空白結合マッチングの前提で書かれており、dispatch側の argv(`--since "$since_value"`)と一致する。3 class の unit 選択子リテラル化・`_is_valid_unit` 共有enumの非侵襲・R11(Codex/Claude Code同一語彙)もすべて確認できた。Critical Issueは無し。

## Critical Issues

なし。

## Suggestions

| # | File | Line | Suggestion | Category |
|---|---|---|---|---|
| 1 | `docs/ai/status.md` | 51 | `journal-ssh` の観測待ちエントリで「配備は Yoshinobu の起動が要る」と書いているが、Semaphore テンプレートが quory 由来の pull で自動走行するのか、手動トリガが要るのかがこの1行からは読み取れない。次にこの行を消化する人が迷わないよう、次に quory 側で何が起きれば配備条件が満たされるか(pull → Semaphore テンプレート実行 の具体名)を一言足すと良い | 記録の明確化 |
| 2 | `roles/recovery_exec/templates/AGENTS.md.j2` | 48-55 / 113-120 | authy/monnie 向けの `journal-ssh` 説明文は完全に同一の静的テキストが2箇所(このファイル内)に複製されている。既存の他の記述(`journal-system`、`dmesg` 等)も同様の複製スタイルなので、既存パターンへの追随として妥当だが、将来 authy と monnie の SSH 起動方式が分岐した場合(現状は両方 `ssh.socket` enabled で一致)に片方だけ書き換えて他方を直し忘れるリスクがある点は認識しておくとよい | 保守性(将来リスク、blockingではない) |

## What Looks Good

- **書込語彙**: 新規3スクリプトの `journal-ssh` アームはいずれも `journalctl -u ... --since ... -n 300 --no-pager` のみで、`start`/`stop`/`restart`/`enable`、リダイレクト、`tee`/`rm`/`mv`/`cp` を含まない。AC9と同じ検査で新規の書込語彙はゼロ。
- **sudoers/dispatch argv一致**: pve側の新規sudoers行 `journalctl -u ssh.service -u ssh.socket --since * -n 300 --no-pager` は、dispatchの `sudo -n /usr/bin/journalctl -u ssh.service -u ssh.socket --since "$since_value" -n 300 --no-pager` と、空白結合文字列としてのfnmatch比較で一致する(`$since_value` が `-30 min` のように空白を含む1引数であっても、ファイル冒頭コメントが明記する「sudoは空白結合文字列としてfnmatchする」性質により1トークンの `*` で吸収される)。既存5行(`journal-unit` 用)と完全に同型。
- **operand設計**: 3 class すべてで unit 選択子(`ssh.service`/`ssh.socket`/`sshd@*`)はスクリプト内リテラルであり、operandはwindow1つのみ。quoryは`[[ -n "$p1" && -z "$p2" && -z "$p3" ]]`、pveは`[[ -n "$p1" && -z "$p2" ]]`、class Gは`read`で再パースし`-z "$window" || -n "$extra"`で検査 — いずれもwindow以外の追加トークンを拒否する。I-3の趣旨(operandからパスや選択子を組み立てない)と一致。
- **`_is_valid_unit` 非侵襲**: class Qの `journal-ssh` アームは共有unit enum配列を一切参照せず、独立したwindowのみの `case` で完結している。`status`/`journal-unit`/`unit-cat`/`deployed-hash` が依存する既存enumへの副作用は無い。
- **R11(Codex/Claude Code同一語彙)**: class G/Pは`~/.ssh/config`確認のとおりCodex用wrapper(`homelab-investigate*.sh.j2`)とClaude Code直SSH(`*-investigate`)が同一の`recovery-exec`ユーザー・同一dispatchスクリプトへ到達するため、実行内容の乖離は構造的に起きない。2本のwrapper側`journal-ssh`アームも追加されており、dispatch側だけ足してwrapper側が拒否する、逆にwrapper側だけ足りているという食い違いは見当たらなかった。class QはCodexが同一ホスト(quory)上で動作しSSH越しの対応物を持たない設計であり(既存`homelab-investigate-quory`のようなwrapperは存在せず、意図的にそうなっている)、AGENTS.md.j2にもquory自己投資チェックの節が無いことと整合している。
- **「空で返る」設計の妥当性**: §7.1の実測表(pve1/pve2はsocket activation無効、quory/monnie/authyは有効)に基づき、pveでは`sshd@*`を除外・他classでは含める、という非対称な実行内容(§7.2)は、起票理由(`journal-system`の`-p warning..err`絞り込みにより空が何の証明にもならなかった失敗)と同じ罠を再生産しない設計になっている。3 unit全てを問い合わせるclass Q/Gと、実在しない`sshd@*`を持ち込まないclass Pの判断はいずれも実測に基づいており、`journal-system`と異なり優先度フィルタも掛けていないため、空応答は「本当に活動が無い」ことの証拠として機能する設計である(実機での空応答自体は未確認)。
- **AGENTS.md.j2との整合**: 3ホストクラス分の説明文がそれぞれの実装(quory/monnie/authyは3ユニット併記、pveは2ユニットのみ・socket activation未使用の注記)と一致している。`journal-unit`と同一window enumである旨も明記されている。
- **`deployed-hash` `worktree-sync`追加**: パスは`roles/worktree_sync/defaults/main.yml`の`worktree_sync_script_path`と一致することを実際に読んで確認した。既存の`investigate-dispatch-quory`等と同型の1行追加であり、既存enumの他エントリへの影響は無い。
- **catch-all位置**: 3スクリプトいずれも`*)`のcatch-all denyは新規アームより後に位置し、新規パターン(`journal-ssh` / `journal-ssh\ *`)が既存の`journal-<svc>`系リテラルパターンと文字列的に衝突しないことを確認した。

## Verdict

**Approve**

blocking findingは無し。Suggestionsの2件はいずれも記録上の分かりやすさ・将来の保守性に関する軽微な指摘であり、承認を妨げるものではない。

---

## Coordinator の処置(2026-08-03)

| 指摘 | 処置 |
|---|---|
| Suggestion 1(`docs/ai/status.md` L51 — 配備条件が1行から読み取れない) | **反映した。** 「quory 側の pull は `worktree-sync.timer` が1分間隔で自動追随するので待つだけでよく、要るのは Semaphore から該当2 playbook のテンプレートを起動すること」と書き分けた。**Semaphore テンプレート名は repo 外のため書いていない** — 書けば正本を持たない値を status.md へ写すことになる(規律4) |
| Suggestion 2(`AGENTS.md.j2` の authy / monnie 説明文の重複) | **据え置く。** 指摘のとおり既存の `journal-system` / `dmesg` 等も同じ複製スタイルであり、今回の追加だけを別扱いにすると**このファイル内で書き方が2種類になる**。重複を畳むなら Jinja のループ化としてファイル全体をまとめて直す話で、`journal-ssh` の追加に相乗りさせる変更ではない。**将来 authy と monnie の SSH 起動方式が分岐したら、片方だけ直して他方を忘れうる**という指摘自体は正しく、その分岐は `unit-files` チェックで観測できる |

**Reviewer が「未確認」と明示した3点**(§7.1 の実機 unit 実測表、`sudo -n` の実挙動、実機での空応答)**は、いずれも配備前に検証する手段が無い。** unit 実測表は Coordinator が dispatch 経由で測った値であり(`ssh <host>-investigate "unit-files"`、5ホスト)、残る2点は `docs/ai/status.md` の Watch 行が引き継ぐ。
