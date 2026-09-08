# Incident: Codex monitorが人間向け承認を自動拒否する

日付: 2026-09-08
状態: 調査中
対象: agmsg Codex monitor bridge / Codex app-server共有thread
種別: 動作不具合

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

未判明。

今回の即時拒否と同時刻に、agmsg Codex bridgeが承認要求へ自動的に
`decline`を返したことはログで確認できている。bridgeには無人turnを
`waitingOnApproval`のまま残さないための自動拒否処理が以前から存在する。
ただし、同じ処理が以前の対話turnでも発火していたか、現在だけ発火するように
なったかは未確定であり、agmsgを原因とは断定しない。

`.codex/rules/default.rules`は2026-09-06のcommit `b450a4a`で導入され、
`git commit` / `git push`を`prompt`へ分類した。しかし導入後の同日16:25、
Codex CLI 0.153.2のagmsg monitorセッションで、承認を経たcommit `fa5b687`と
pushが成功している。このため、rules導入を症状発生の直接原因とする以前の説明は
撤回する。現在もsymlinkは実体へ解決でき、execpolicy検査は両コマンドを
`prompt`、`git status`を`allow`と判定している。

失敗した現在のセッションはCodex CLI 0.153.4である。0.153.4の実体は
2026-09-06に配置され、ansy再起動後の現在のセッションで使われている。
旧app-serverが再起動まで残っていた可能性、CLI更新または接続構成の変化により
承認要求の配送順が変わった可能性はあるが、いずれも現時点では仮説である。

## 修正内容

未修正。agmsg bridgeを変更する案はYoshinobuの意向により採用しない。
`.codex/rules/default.rules`、`~/.codex/config.toml`、agmsgの実装は変更していない。
Codex CLI / app-serverのバージョンと接続構成の差を切り分ける。

## 確認方法

調査中の確認として、rulesのsymlink解決、execpolicyの判定、過去セッションの
CLIバージョンとcommit/push成功記録、現在セッションの即時拒否記録を照合した。

原因を確定した後、同じmonitor構成で`git commit` / `git push`の承認UIが表示され、
Yoshinobuの許可時だけ実行されることと、通常のagmsg往復が継続することを確認して
`解決済み`へ更新する。
