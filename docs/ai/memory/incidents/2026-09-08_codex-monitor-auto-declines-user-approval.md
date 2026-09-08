# Incident: Codex monitorが人間向け承認を自動拒否する

日付: 2026-09-08
状態: 解決済み
対象: agmsg Codex monitor bridge / Codex app-server共有thread
種別: 動作不具合
原因分類: #運用考慮ミス #テスト不足

## 症状

スマホアプリからCoordinatorへcommit/pushを明示的に依頼した後、
`git commit`の承認UIが一度も表示されず、実行側には即時に
`Rejected("rejected by user")`が返った。Yoshinobuは拒否操作をしていない。

bridgeログには同時刻に次が記録されていた。

```
codex-bridge: auto-declining an approval request (headless bridge, see #299)
```

commit/pushはYoshinobuがansyの通常シェルから実行し、commit `3bd3616`が
`origin/main`へ到達した。

## 原因

直接原因は、同じthreadを購読するagmsg Codex monitorのheadless bridgeが、
app-serverの承認要求へスマホクライアントより先に`decline`を返すことである。
bridgeには無人turnを`waitingOnApproval`のまま残さないための自動拒否処理が
以前からあり、直接のスマホ対話turnでも購読中のbridgeが同じ要求を受け取る。
したがって、monitorとの共有threadでCLI承認UIを必須にする構成は成立しない。

`.codex/rules/default.rules`は2026-09-06のcommit `b450a4a`で導入され、
`git commit` / `git push`を`prompt`へ分類した。しかし導入後の同日16:25、
Codex CLI 0.153.2のagmsg monitorセッションで、承認を経たcommit `fa5b687`と
pushが成功している。このため、rules導入を症状発生の直接原因とする以前の説明は
撤回する。現在もsymlinkは実体へ解決でき、execpolicy検査は両コマンドを
`prompt`、`git status`を`allow`と判定している。

失敗したセッションはCodex CLI 0.153.4だったため、0.153.2へ一時的に戻して
同じmonitor構成を再起動し、スマホから直接`git commit --dry-run`を依頼した。
0.153.2でも承認UIは表示されず、bridgeログに同じ自動拒否が記録された。
これによりCLI更新が直接原因という仮説は棄却した。過去に0.153.2とmonitorで
commit/pushが成功した時点との条件差は特定できていないが、現行構成の失敗原因と
恒久対応の判断には影響しない。

## 修正内容

agmsg bridgeを変更する案はYoshinobuの意向により採用しない。
Yoshinobuの明示承認を会話で得る既存の人間ゲートを正本とし、Codexでは
`.codex/rules/default.rules`の`git commit` / `git push`を`allow`へ変更して、
同じ判断への到達不能な追加UI確認を要求しない。`~/.codex/config.toml`と
agmsgの実装は変更しない。切り分けのため一時的に0.153.2へ戻したランチャーは、
最新の0.153.4を使う構成へ戻す。

## 確認方法

調査中の確認として、rulesのsymlink解決、execpolicyの判定、過去セッションの
CLIバージョンとcommit/push成功記録、現在セッションの即時拒否記録を照合した。

同じmonitor構成をCodex 0.153.4で再起動し、execpolicyが`git commit` / `git push`を
`allow`と判定することを確認した。stage済み差分がある状態で`git commit --dry-run`を
実行し、追加ASKなしで正常終了した。再起動後もスマホから同じthreadの会話を継続できて
いる。会話上の承認なしにCoordinatorがcommit/pushしないことはPolicyとRoleの運用で
担保する。

rules変更直後、変更前から動いている0.153.2セッションで`git commit --dry-run`を
再試行すると、rules単体のexecpolicy判定が`allow`であるにもかかわらず即時拒否された。
起動済みセッションには変更が反映されていないため、この結果は修正の否定材料にせず、
0.153.4でmonitorを再起動した後の再試行結果を採用した。
