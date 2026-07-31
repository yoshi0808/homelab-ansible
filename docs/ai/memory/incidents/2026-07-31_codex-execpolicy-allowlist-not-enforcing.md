# Incident: Codexのexecpolicy allowlistが境界として機能していない

日付: 2026-07-31
状態: 原因判明・対応中
対象: `roles/recovery_exec`(`templates/codex-config.toml.j2`)、quory上のCodex実行経路(recovery-io → codex-exec-wrapper → codex exec)
種別: セキュリティ事故
原因分類: 設定機構の誤認 — 存在しない設定キーを安全境界として設計していた

## 症状

`roles/recovery_exec/templates/codex-config.toml.j2` は `[execpolicy] default_policy = "deny"` を置き、`homelab-*` の各wrapperだけを `policy = "allow"` として列挙している。同roleの `AGENTS.md.j2` は「All commands are wrapper scripts. The execpolicy allows ONLY these scripts.」と書き、`docs/ai/policies/incident_capture_policy.md` IC-018 は「禁止はpromptの文言で表現せず書込allowlistで強制する」と定めている。**このallowlistが、実際にはコマンド実行を阻止していない。**

2026-07-31、新規案件の着手前実測(`docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md`)で観測した。

- quory上で、本番の `/home/recovery-exec/.codex/config.toml` と**同一内容**の設定を独立した `CODEX_HOME` へ複製し、`codex exec`(codex-cli 0.145.0、`approval_policy="never"`)を起動した。
- allow-listに一切無いコマンド `id` を実行させたところ、**拒否されず成功した**(`uid=...(recovery-exec)` が返った)。
- `--profile` で層を重ねる / `-c` で `execpolicy.*` を上書きする / 専用 `CODEX_HOME` の config.toml へ直接書く、の3機構すべてで、基底が許可している `homelab-mute-status` を拒否させることもできなかった。
- `-c` によるオーバーライド機構自体は機能する(`-c 'model=...'` はbannerとAPIリクエストまで伝播した)。したがって記法の誤りではない。

Coordinatorによる裏取り(2026-07-31、read-onlyのみ):

- ネイティブバイナリ(`.../codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`)には `execpolicy` の文字列が実在する。**キー名が廃止・改名されて無視されているわけではない。**
- 同バイナリに埋め込まれたCLIヘルプに `--ignore-rules`「Do not load user or project execpolicy `.rules` files」がある。**この版のexecpolicyは `.rules` ファイルで与える機構**であり、config.tomlの `[execpolicy]` テーブルが同じ意味を持つかは確認できていない。
- 同ヘルプに「proposed execpolicy amendment」という文言があり、execpolicyが**承認フローに属する分類機構**である可能性を示す。`approval_policy="never"` の非対話実行では「承認が要る」が「拒否」ではなく「そのまま実行」に落ちると辻褄が合う。

## この経路に現在も効いている境界(観測に基づく範囲)

allowlistが効いていないことは、この経路が無防備であることを意味しない。次は別レイヤであり、今回の観測では損なわれていない。

- `--sandbox workspace-write` によるファイルシステム制限(codex自身のbwrap層)
- `no_new_privileges` により sudo が無条件にブロックされること(既存の実測記録あり)
- 各ターゲット側のSSH forced command(`homelab-investigate-*` / `homelab-recover-*` が到達できる操作の実体はターゲット側で固定されている)
- sudoers が recovery-io → `codex-exec-wrapper` の1本だけを許していること

**変わったのは「recovery-execとして実行できるローカルコマンドが `homelab-*` に限られている」という前提**である。実際には任意のローカルコマンドが実行できる。

## 原因(2026-07-31、実測により確定)

**config.tomlの `[execpolicy]` はこの版に存在しないキーである。** execpolicyの実体は Starlark で書く `.rules` ファイルであり、`--rules` / user・project の探索 / `--ignore-rules` で扱う。TOMLテーブルは読まれず、`default_policy = "deny"` は最初から何も意味していなかった。

さらに、**`.rules` へ移しても当初意図した allowlist は作れない。** 実測した言語仕様:

| 観測 | 内容 |
|---|---|
| ルール生成関数 | `prefix_rule(pattern=[...], decision=...)` のみ。`match` / `pattern` はグローバルに存在しない(`Variable ... not found`) |
| decisionの値域 | `allow` / `prompt` / `forbidden` の3つだけ。`deny` は `error: invalid decision: deny` |
| catch-all | **書けない。** 空patternは `pattern cannot be empty`、`"*"` はリテラル扱いで `id` に一致しない |
| 未一致コマンド | `{"matchedRules":[]}` を返し **decisionが付かない**(unverified)。既定denyにはならない |
| pattern の別形 | `[["id","whoami"]]` の選択肢形は機能する(いずれも具体名の列挙であり、任意コマンドは表現できない) |
| `codex exec` の承認 | 承認系フラグが**1つも無い**。承認ベースの既定deny(`AskForApproval::UnlessTrusted`)は非対話経路では到達不能。U0で `approval_policy="untrusted"` が効かなかった観測と整合する |

つまりexecpolicyは**列挙したコマンドを許可/禁止/承認要求へ分類する機構**であって、列挙外を既定で塞ぐ機構ではない。**この版で `homelab-*` だけを許す境界は、execpolicyでは原理的に構成できない。**

## 未確認のこと(この記録の限界)

- **本番経路そのもの(recovery-io → `codex-exec-wrapper`)では試していない。** 観測は本番と同一内容の設定を複製した別 `CODEX_HOME` で行った。wrapperが注入するフラグ(`--sandbox workspace-write`、`approval_policy="never"`、`sandbox_workspace_write.network_access=true`)にexecpolicyを復活させるものは無いため同じ挙動と考えられるが、**推測である。**
- `codex execpolicy check` は**ポリシーファイルの静的評価器**であり、runtimeのローダ(どのパスを探索するか、組込みルールが加わるか)まで測ったわけではない。上表の言語仕様は静的評価で確定した事実だが、「`prompt` / `forbidden` が `codex exec` で実際に拒否になるか」はモデル呼び出しを伴う実行でしか確かめられず、**未測定**である(方針上blocklistを採らないため測っていない)。
- OpenAI側の公式ドキュメントは参照していない。根拠はすべてバイナリのCLIヘルプと実測である。
- この状態がいつからかは不明。テンプレートのコメントは codex-cli **0.144.1** 時点で `sandbox_workspace_write.writable_roots` を `--strict-config doctor` で確認したと記しているが、**execpolicyの実効性を確認した記録はどこにも無い**。導入時から効いていなかった可能性が高い。

## 修正内容

段階的に実施した(2026-07-31、Yoshinobu「対応お願いします」→「順を追って対応」)。

**第1段 — 文書と実態の乖離の解消(同日)。**

- `roles/recovery_exec/templates/AGENTS.md.j2` — 「The execpolicy allows ONLY these scripts.」という**強制の主張を削除**し、「列挙されたコマンドだけを呼べ、無ければ止まって報告せよ」という**指示**に置き換えた。Codexへ渡すpromptに「機構が止めてくれる」と書かないため。**逆に「実際には止まらない」とも書いていない** — promptは期待を述べる場所であり、実効性の記録は設定と一次記録が持つ。
- `roles/recovery_exec/templates/codex-config.toml.j2` — 実測結果を配備先へ出力されるコメントとして明記し、`[execpolicy]` テーブルは一旦**残した**(`.rules` 方式が未評価だったため)。

**第2段 — 原因の確定と、死んだ設定の除去(同日、上記「原因」節の実測後)。**

- `roles/recovery_exec/templates/codex-config.toml.j2` — `[execpolicy]` テーブルを**削除**した。存在しないキーであることが確定し、「未評価だから残す」という保留理由が消えたため。意図と経緯は本Incidentが持つ。残した場合、次に設定を読む人がふたたび境界と誤認する。
- `docs/ai/policies/autonomous_recovery_policy.md` — AR-069 / AR-071 / AR-073 を実態へ改訂した(下表)。
- **配備は行っていない。** 変更が quory へ反映されるのは commit / push と quory での `git pull --ff-only` の後に `playbooks/recovery_exec_setup.yml` を実行した時点である(同roleに handler は無く、テンプレート更新で `recovery-io` が再起動されることはない)。設定の削除は挙動を変えない(元から読まれていない)ため、配備の緊急性は無い。

| 条項 | 改訂前 | 改訂後の趣旨 |
|---|---|---|
| AR-069 | execpolicyはdefault denyとし、限定wrapper群だけを許可する | **execpolicyを防御層として数えない。** 実行できるlocal commandの範囲は境界ではなく、wrapper群の列挙はCodexへの指示として `AGENTS.md` が持つ |
| AR-071 | VM rebootとHA failoverはCodex execpolicyへ含めず、pull経路にだけ許可する | 両者を隔てているのは **push経路にwrapperが存在しないこと**(能力の不在)であると明記する |
| AR-073 | sandboxとexecpolicyを別の防御層として扱う | 実在する層 — **sandbox / `no_new_privileges` / target側forced command / sudoers** — を列挙する形へ置き換える |

## 採った方針(2026-07-31 Yoshinobu決定)

**境界の主を「能力の不在」へ一本化し、execpolicyの復活は追わない。**

- 却下: `.rules` を blocklist として導入する案。allowlistにならず、**効かない検査が誤った安心を生む**(`docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`、および pre-commit のパスgrep検査で同型の判断をした前例)。
- 却下: quory側でmount namespaceを作り込み `/usr/local/bin` を絞る案。`/bin/sh` と `/usr/bin` は codex / node の動作に要るため残り、得られるのは「他のwrapperを見せない」までで、任意コマンド実行そのものは塞げない。コストに見合わない。
- 採用: 失ったのは「任意のlocal commandが打てない」という性質だけであり、recover系wrapper自体は元からallow側にあって到達できた。**実害を縛っているのはtarget側のforced commandである。** したがって境界の再建は新規案件を立てず、既に `docs/ai/status.md` Next にある「**Codexの調査面を広げ、SSH鍵配布を縮小する**」を本体として扱う。

## 確認方法

`codex execpolicy check` がこの機構の**決定論的な評価器**である(モデル呼び出しを伴わない)。

```
codex execpolicy check --rules <FILE> --pretty <COMMAND> [ARGS...]
```

許可されたコマンドは `"decision": "allow"` を返し、どのルールにも一致しないコマンドは `{"matchedRules": []}` を返す(decisionが付かない = unverified)。**この「decisionが付かない」状態が拒否ではないことが、本Incidentの中核である。**

将来この経路へ何らかのコマンド制限を再導入する場合は、「制限対象が拒否されること」と「許可対象が通ること」の**両方**を観測すること。片方だけでは機構が効いた証明にならない(2026-07-31のU0は通過側しか観測できず、それが「絞れていない」という結論の根拠になった)。

## 調べ直すときの足場(2026-07-31に踏んだ回り道)

- **`/usr/bin/codex` は Node のラッパー**(`../lib/node_modules/@openai/codex/bin/codex.js` へのsymlink、46バイト)。ここに `strings` をかけても何も出ない。**この構造はNodeSourceのnodejsを入れてnpm globalでcodexを入れているため**(2026-07-31 Yoshinobu。導入経緯は `docs/ai/reviews/codex_update_check/` が持つ。週次の自動更新も同じ経路で、`roles/codex_update_check`)。したがって版が上がるとネイティブ実体のパスも入れ替わりうる — **パスを決め打ちで記録せず、都度 `find`/`grep -rl` で辿ること。**ネイティブ実体は
  `/usr/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex` にあり、**`execpolicy` の文字列はこちらに実在する**(=キー名が廃止・改名されて無視されているわけではない)。
- 同バイナリに埋め込まれたCLIヘルプが一次資料として使える。`--ignore-rules`(「Do not load user or project execpolicy `.rules` files」)と「proposed execpolicy amendment」の文言はここから得た。
- **`codex execpolicy` は `codex --help` のCommands一覧に現れない。** 直接 `codex execpolicy --help` を叩くと出る。同種の隠しサブコマンドがある前提で探すこと(`strings` に `ExecPolicyCheckCommand` として現れていた)。
- `codex features list` が feature flag の状態を一覧する。`exec_permission_approvals` / `request_permissions_tool` は *under development* で false、`request_rule` は *removed*。**承認まわりの機構が版によって出入りしている**ことがここから読める。
- 設定キーが有効かを `--strict-config` で確かめる手は、サブコマンドによっては使えない(`codex features` は `--strict-config is not supported` を返す)。**「弾かれなかった=認識されている」と読まないこと。** 本件で `[execpolicy]` が存在しないキーだと気づくのが遅れた一因である。

## 参照

- `docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md`(一次記録)
- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`
- `docs/ai/policies/incident_capture_policy.md` IC-018
- `roles/recovery_exec/templates/codex-config.toml.j2`、`roles/recovery_exec/templates/AGENTS.md.j2`
