# Incident: 退役した世代の資格情報が ansy と本番ノードに残り、Phase 4 を生き延びていた

日付: 2026-08-06
状態: 解決済み
対象: ansy `/etc/recovery/` / authy・monnie の `recovery-slack` アカウント
種別: セキュリティ事故
原因分類: #運用考慮ミス

## 症状

ansy の撤去作業中の掃引(`find / -nouser -o -nogroup`)で、**削除済み UID 1003 が所有するディレクトリ `/etc/recovery/`** を発見した。中身は次のとおり(いずれも 2026-06-27 作成)。

| 内容 | 実体 |
|---|---|
| SSH 秘密鍵5本(ED25519、`0600`) | `id_status_ansy_{authy,monnie}` / `id_trigger_ansy_{authy,monnie,sophos_fw}` |
| `slack-listener.env`(`0600`) | `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` / `SLACK_AUTHORIZED_USER_ID` / `RECOVERY_QUORY_HOST` / **`CLAUDE_CODE_OAUTH_TOKEN`** |
| `claude-ws/.claude/settings.json` | 作業ディレクトリの残骸 |

UID 1003 は `recovery-slack` — **commit `9e0196b` で退役した、Claude Code ベースの Slack リスナー**(現行 `recovery-io` の前身)の実行ユーザーである。

そして**相手側にも残っていた**。

```
authy:/home/recovery-slack/.ssh/authorized_keys
  command="/usr/local/sbin/radius-healthcheck.sh",no-agent-forwarding,...
  ssh-ed25519 ... recovery-status-ansy-authy
```

fingerprint は `SHA256:ZXxEbgtlF/5bpVgin4kwj2LFljFLokh6ekCdQ/M/Gkg` で、**ansy 側の `id_status_ansy_authy` と完全一致**した。monnie も同型(`SHA256:TM30joZfNm57w715j+M3/91GmS0bVfCFolFkQn5wCd8`)。

**つまり ansy → authy / monnie の実行経路が、2026-08-03 の Phase 4 を生き延びて残っていた。**

### 各経路が実際に生きていたか

| 経路 | 相手側の認可 | 判定 |
|---|---|---|
| ansy → authy `recovery-slack` | **あり** | **生きていた。** ただし forced command が `radius-healthcheck.sh` に固定されており、能力は read-only の healthcheck 実行に限られる。書込も任意コマンドも不可 |
| ansy → monnie `recovery-slack` | **あり** | 同型 |
| ansy → authy / monnie `trigger` | `authorized_keys` が存在しない | 死んでいた |
| ansy → sophos-fw `trigger` | **配布経路が存在しない** | 一度も生きていない。旧 `recovery_trigger_setup.yml` に sophos-fw の play は無く、listener role にも配布記述が無い。sophos-fw は `admin` 以外のユーザーを作れない |

**`docs/ai/status.md` の「2026-08-03 に ansy から `id_rsa_sophos` を削除したため、ansy 側に実行手段は無い」は、sophos-fw については正しかった。** 誤っていたのは authy / monnie の側である。

## 原因

**世代を退役させたとき、配備済みの資格情報と相手側アカウントを消していない。**

`9e0196b` は `recovery_slack_listener` / `recovery_trigger` / `recovery_trigger_client` の3ロールと2 playbook を削除した。**しかし削除されたのは repo 側の定義だけで、既に配られていたものは残った。** playbook を消すと、その playbook が作ったものを消す手段も同時に失われる。

**Phase 4 の資格情報の数え上げがこれを拾えなかった理由は2つある。**

1. **置き場所の軸** — 掃引は `~/.ssh/` と `~ann/.ssh/authorized_keys` を見た。退役した世代は `/etc/recovery/` に置いており、**現行ロールが使わない場所**だった
2. **相手側ユーザーの軸** — 掃引は `root` / `ann` を見た。`recovery-slack` は third の名前空間であり、直積から丸ごと漏れた

2 は `docs/ai/memory/lessons/enumerate-credentials-that-reach-you-not-those-you-placed.md` が実務則の1点目として既に明記していたものである。**書かれていたが、適用されなかった。**

## 修正内容

**ansy 側**(2026-08-06)

- `/etc/recovery/` を削除(秘密鍵5本、`slack-listener.env`、`claude-ws/`)
- 削除前に**公開鍵の fingerprint 5件を控えた** — 相手側 `authorized_keys` の照合に要るため。順序は Lesson の実務則3点目(「相手側の受け口を消す → 到達しないことを測る → 自分側の資格情報を消す」)と逆になったが、fingerprint を保持することで照合手段は失わなかった

**相手側**(2026-08-06、Yoshinobu が実施)

- authy / monnie の `recovery-slack` アカウントを `userdel -r` で削除
- `trigger` は `authorized_keys` が存在せず対応不要
- sophos-fw は対応不要(配布経路が存在しなかった)

**`/usr/local/sbin/radius-healthcheck.sh` は削除していない。** 現行の `roles/radius_healthcheck` が **Ansible 経由で**(SSH forced command 経由ではなく)copy して実行しており、消すと `SAFE: Authy healthcheck` と月次の `ubuntu_vm_full_upgrade` が壊れる。**退役した入口だけを消し、現行が使う本体は残す**のが正しい切り分けだった。

## 確認方法

- ansy: `find / -xdev \( -nouser -o -nogroup \)` が **0件**(撤去前は9件)
- authy / monnie: `getent passwd recovery-slack` が空
- 照合に使った fingerprint は本ファイルに記録済み(公開鍵の指紋であり秘密ではない)

## `CLAUDE_CODE_OAUTH_TOKEN` の始末(完了)

3層すべてで閉じた。

| 層 | 対応 |
|---|---|
| ansy 上の平文 | `/etc/recovery/slack-listener.env` ごと削除 |
| vault の保管 | `vault_claude_code_oauth_token` を削除(commit `bc49625`)。**現行が参照する vault 変数はどれでもなかった** |
| **Anthropic 側の失効** | **Yoshinobu が、対話中の1セッションを除く全セッションを削除**(2026-08-06) |

**巻き添えは無い。** この環境に Claude の資格情報を使う定義は1つも無く、repo 内のヒット6件はすべて「2026-08-03 に `claude -p` 2本を廃止した」という経緯コメントである(無人の Claude セッションを1つも残さないという同日の決定どおり)。

**ファイルを消すこととトークンを失効させることは別である。** 本件では前者を先に済ませたため、その間トークンは生きていた。順序としては失効が先が望ましい。
