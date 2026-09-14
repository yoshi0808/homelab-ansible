# Incident: 再起動後、Implementerへのagmsgメッセージが黙って届かなくなった

日付: 2026-09-14
状態: 解決済み
対象: agmsgのCodex monitor経路(ansy pane 1のImplementer)
種別: 動作不具合
原因分類: #運用考慮ミス

## 症状

ansy再起動後の最初のセッションで、CoordinatorからImplementerへ送った依頼が可視スレッドへ届かなかった。**送信側は成功する** — メッセージはagmsgのDBへ入り、`history.sh`にも現れ、Implementer自身が送るREADYは届く。届かないのは受信側だけで、Codexのペインは依頼を受け取らないままプロンプトで待ち続けた。エラーは出ない。

`delivery.sh status codex <project>` が唯一の手掛かりを出した。

```
Codex bridge: homelab/implementer not running (seat recorded: 01a09e77-...)
```

seatは記録済み、ペインもCodexプロセスも正常、mode=monitor。それでもbridgeが1つも動いていなかった。

## 原因

**`codex` がagmsgのshimではなく実バイナリに解決されていた。** bridgeはshim(`~/.agents/bin/codex` → `codex-shim.sh` → `codex-monitor.sh`)を通ったCodex起動でしか立ち上がらないため、shimを迂回した起動ではbridgeが存在せず、受信だけが成立しない。

PATHの順序が入れ替わった理由は2つが重なったものである。

1. `~/.local/bin/codex` は2026-09-12 12:40にCodex standaloneのインストーラが張ったsymlinkである。
2. `~/.bashrc` は `~/.agents/bin` をPATH先頭へ置くが、**login shellでは `~/.profile` の `~/.local/bin` ブロックがその後に走って前置し直す**ため、shimが負ける。

tmuxサーバはペインの環境の出どころであり、**今日の再起動で初めて(1)より後のPATHで起動した**。9/13までのセッションは9/12以前に起動したサーバの環境を引き継いでいたため、同じ設定のまま今日から症状が出た。

## 修正内容

- `~/.profile` の末尾で `~/.agents/bin` を前置し直した(`.local/bin` ブロックより後)。バックアップは `~/.profile.bak-20260914`。
- Implementerを `despawn.sh --force` → `spawn.sh --fresh` で立て直した。
- `docs/ai/context/operations/agent-messaging.md` §2「codex の monitor 配送が届く条件」の条件3を精緻化した。同節は既に「`~/.agents/bin` が PATH にある」ことを条件に挙げていたが、**PATHにあるだけでは足りず実バイナリより前である必要がある**ことと、**ペインの環境がtmuxサーバから来る**ことを書いていなかった。

## 確認方法

- `bash -lic 'type codex'` が `/home/yoshi/.agents/bin/codex` を返すこと。
- 立て直し後、`delivery.sh status codex /home/yoshi/homelab-ansible` が `homelab/implementer alive (pid ...)` を返すこと。
- 実際に依頼を再送し、pane 1が受領して作業に入ること(2026-09-14に実測。同じ依頼文で、bridge不全時は無反応、復旧後は即Working)。

## 残る不確かさ

`delivery.sh set off` / `set monitor` を打つ前の hooks の状態(Stop entry数)を記録していない。**今日より前の配送がどのモードで成立していたかは確かめられない。**
