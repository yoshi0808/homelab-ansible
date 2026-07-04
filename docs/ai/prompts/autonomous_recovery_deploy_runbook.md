# 自律復旧パイプライン デプロイ手順書

対象ロール: `recovery_exec`, `recovery_io`, `recovery_probe`
参照: `docs/ai/prompts/autonomous_recovery_policy.md`

---

## 前提

- **quory = 本番**。`recovery-io`・`recovery-probe`はsystemdで有効化され、OS起動時に自動的に立ち上がる。
- **ansy = 開発**。同じroleを配置できるが、`recovery-io`・`recovery-probe`はどちらも既定で無効(配置のみ、手動起動が原則)。
- `recovery-io`・`recovery-probe`をansy/quoryで**同時に稼働させない**こと。前者はSlackの`@Homelab`メンションをどちらが受けるか競合し、後者はpull監視が重複する。ansyで手動テストする場合は、事前にquory側の状態を確認すること。
- `recovery-exec`は常駐プロセスではないため、この制約の対象外。

---

## 1. `recovery_exec` デプロイ

```bash
# quory 本番: target側(authy/monnie)のauthorized_keys設定も含めて実行
ansible-playbook playbooks/recovery_exec_setup.yml -l quory

# ansy 開発: target側のauthorized_keysに触らないよう明示的にfalseを指定(変数の既定値はtrue)
ansible-playbook playbooks/recovery_exec_setup.yml -l ansy \
  -e recovery_exec_setup_targets=false
```

**注意**: `recovery_exec_setup_targets`は既定`true`で、authy/monnieの`authorized_keys`は実行元ホストが生成した鍵2本で毎回上書きされる(drift-safe設計、`authorized_keys.j2`)。quoryで本番鍵を配った後にansyで`-e recovery_exec_setup_targets=false`を付けずに実行すると、authy/monnie側がansyの鍵に置き換わり、**quoryの本番investigate/recover経路が切断される**。ansyからauthy/monnieへの実疎通がどうしても必要な場合のみ明示的にtargets=trueで実行し、検証後は必ずquoryで再実行してauthorized_keysを本番鍵に戻すこと。

内部で自動実行される内容:

- 対象ホスト(quory/ansy): `recovery-exec`ユーザー作成 / SSH鍵2本(investigate/action)生成 / wrapperスクリプト配置 / `homelab-monitoring-{pause,resume,status}`配置 / Codex config + AGENTS.md配置
- authy/monnie: `recovery-exec`ユーザー作成(着地専用) / dispatch・actionスクリプト配置 / authorized_keys登録(投稿investigate/action鍵のみ、drift-safe) / sudoers配置

`-e recovery_exec_setup_targets=false`でauthy/monnie側のセットアップをスキップできる(対象ホストのローカル変更のみ検証したい場合)。

---

## 2. Codexブラウザ OAuth認証(デプロイ先ホストごとに1回)

```bash
sudo -H -u recovery-exec codex
```

ブラウザでOAuthフローを完了後 `Ctrl+C` で抜ける。トークンは`~/.codex/auth.json`に残るため、そのホストでは以後再実行不要(リブートしても消えない)。**quory・ansyそれぞれで個別に認証が必要**(トークンはホスト単位)。

---

## 3. OS権限確認

```bash
# Codexトークン: 0600 recovery-exec所有、nobodyからはPermission denied
sudo stat /home/recovery-exec/.codex/auth.json
sudo -u nobody cat /home/recovery-exec/.codex/auth.json

# SSH秘密鍵: 同上
sudo stat /home/recovery-exec/.ssh/id_recovery_investigate
sudo stat /home/recovery-exec/.ssh/id_recovery_action
sudo -u nobody cat /home/recovery-exec/.ssh/id_recovery_action

# recovery-execからann鍵・vault passが読めないこと(境界確認)
sudo -u recovery-exec cat /home/yoshi/.ssh/id_ann
sudo -u recovery-exec cat /home/yoshi/.ansible/vault/homelab_vault_pass
```

期待結果:
- `stat`対象(auth.json, investigate鍵, action鍵): `0600`+専用ユーザー所有であること
- `cat`対象(nobody/recovery-execからの越境読み取り): 全て`Permission denied`であること

---

## 4. SSH疎通確認(investigate鍵)

**quory上で実行すること。** ansy上で実行する場合、ansyの鍵がauthy/monnie側に登録されている必要があり(§1の`recovery_exec_setup_targets=true`実行時のみ)、本番quory鍵と排他関係になる点に注意。

```bash
sudo -H -u recovery-exec ssh -T \
    -i /home/recovery-exec/.ssh/id_recovery_investigate \
    -o StrictHostKeyChecking=yes \
    recovery-exec@authy.internal status

sudo -H -u recovery-exec ssh -T \
    -i /home/recovery-exec/.ssh/id_recovery_investigate \
    -o StrictHostKeyChecking=yes \
    recovery-exec@monnie.internal status
```

---

## 5. `recovery_io` デプロイ(Slack入口)

```bash
# quory: 自動起動ON
ansible-playbook playbooks/recovery_io_setup.yml -l quory -e recovery_io_service_enabled=true

# ansy: 配置のみ(自動起動しない)
ansible-playbook playbooks/recovery_io_setup.yml -l ansy
```

デプロイ後の確認:

```bash
sudo systemctl status recovery-io   # quoryでは Active: active (running)
```

---

## 6. `recovery_probe` デプロイ(pull型監視)

```bash
# quory: 自動起動ON
ansible-playbook playbooks/recovery_probe_setup.yml -l quory -e recovery_probe_service_enabled=true

# ansy: 配置のみ
ansible-playbook playbooks/recovery_probe_setup.yml -l ansy
```

デプロイ後の確認:

```bash
sudo systemctl status recovery-probe   # quoryでは Active: active (running)

# 読み取り専用、アクションなしで全対象のprobe結果を確認
sudo -H -u yoshi python3 /usr/local/sbin/recovery-probe.py --once
```

全対象が`OK`(またはmute中ならその旨)であることを確認する。`FAIL`が出た場合は原因調査の間`sudo homelab-mute set <target> <分> <理由>`で一時的に抑制する(`set`/`clear`はroot必須、`status`は不要)。`host`名の設定ミス(短縮名はOS DNSで解決できない)など、設定変更直後は特に注意して確認すること。

---

## 7. Codex単体スモークテスト(Slackなし)

```bash
sudo -H -u recovery-exec /usr/local/bin/codex-exec-wrapper exec \
    --cd /var/lib/recovery-exec/workspace \
    "authy の freeradius のステータスを確認してください"
```

期待動作: Codexが`homelab-investigate-authy status`を呼び出し、結果を日本語でターミナルに出力する。

---

## 8. Slackからの動作確認(任意)

```
@Homelab authy の freeradius を調べてください
```

---

## イレギュラー対応

### OAuthトークン期限切れ時の再認証

```bash
sudo -H -u recovery-exec codex
# ブラウザOAuthフロー完了後 Ctrl+C
```

### targetノード(authy/monnie)が停止中だった場合の再セットアップ

復旧後、本番(quory)側で再実行する。

```bash
ansible-playbook playbooks/recovery_exec_setup.yml -l quory
```

`recovery_exec_setup_targets`は既定`true`のため、target側の設定が自動で再適用される。

ansyでの開発中に同じ状況が起きた場合は、`-l ansy -e recovery_exec_setup_targets=false`のまま(target側は再セットアップされない)にするか、意図的にansy鍵を検証したいときだけ`targets=true`で実行し、**検証後は必ずquoryで再実行してauthorized_keysを本番鍵に戻す**こと。

### ansyで一時的にrecovery-io/recovery-probeを手動起動する場合

対象serviceを`recovery-io`または`recovery-probe`に読み替えて実行する(2つ同時に検証する場合はそれぞれ個別に実施)。

```bash
sudo systemctl start <recovery-io|recovery-probe>
sudo systemctl status <recovery-io|recovery-probe>   # Active: active (running) であること
```

検証が終わったら、起動した方を必ず停止する。

```bash
sudo systemctl stop <recovery-io|recovery-probe>
sudo systemctl is-active <recovery-io|recovery-probe>   # inactive であることを確認
```

quory側と同時稼働させないこと。
