# Incident: Codexのexecpolicy allowlistが境界として機能していない

日付: 2026-07-31
状態: 調査中
対象: `roles/recovery_exec`(`templates/codex-config.toml.j2`)、quory上のCodex実行経路(recovery-io → codex-exec-wrapper → codex exec)
種別: セキュリティ事故
原因分類: (判明後に記入)

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

## 原因

未判明。次のいずれかを切り分ける必要がある。

1. この版(0.145.0)ではconfig.tomlの `[execpolicy]` が実装上参照されない(`.rules` ファイルが正)。
2. execpolicyは承認の分類機構であり、`approval_policy="never"` では拒否として作用しない設計である。
3. 設定は有効だが、`codex exec` の非対話経路だけが例外である。

いずれであっても、**config.toml層のexecpolicyを安全境界の主として設計してはならない**という結論は変わらない。

## 未確認のこと(この記録の限界)

- **本番経路そのもの(recovery-io → `codex-exec-wrapper`)では試していない。** 観測は本番と同一内容の設定を複製した別 `CODEX_HOME` で行った。wrapperが注入するフラグ(`--sandbox workspace-write`、`approval_policy="never"`、`sandbox_workspace_write.network_access=true`)にexecpolicyを復活させるものは無いため同じ挙動と考えられるが、**推測である。**
- OpenAI側の一次資料(ドキュメント・ソース)でconfig.tomlの `[execpolicy]` の意味を確認していない。
- この状態がいつからかは不明。テンプレートのコメントは codex-cli **0.144.1** 時点で `sandbox_workspace_write.writable_roots` を `--strict-config doctor` で確認したと記しているが、**execpolicyの実効性を確認した記録はどこにも無い**。導入時から効いていなかった可能性がある。

## 修正内容

未着手。方針の候補は次の3つで、いずれもYoshinobuの判断を要する。

1. `.rules` ファイル方式が有効かを実測し、有効ならそちらへ移す。
2. execpolicyに依存せず、**能力の不在**で境界を作る(実行ユーザーを分ける / systemdのmount namespaceで該当wrapperを見せない / SSH鍵を持たせない)。
3. 現状を受け入れ、`AGENTS.md.j2` と関連文書から「execpolicyが唯一のwrapperだけを許可する」という記述を削る(**境界が無いことを正しく記録する**)。

**3は単独では採らない。** 少なくとも文書の記述と実態の乖離は解消する必要がある。

## 確認方法

未確定。修正後は「allow-listに無いコマンド(例: `id`)が拒否されること」と「許可したコマンドが通ること」の**両方**を観測して確認する。片方だけでは機構が効いた証明にならない。

## 参照

- `docs/ai/reviews/incident_auto_investigation/2026-07-31_002_u0_test_result.md`(一次記録)
- `docs/ai/memory/lessons/permission-boundaries-must-be-designed-not-prompted.md`
- `docs/ai/policies/incident_capture_policy.md` IC-018
- `roles/recovery_exec/templates/codex-config.toml.j2`、`roles/recovery_exec/templates/AGENTS.md.j2`
