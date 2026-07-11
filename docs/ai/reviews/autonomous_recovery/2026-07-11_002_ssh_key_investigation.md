# recovery-exec investigate SSH publickey 拒否 — 原因調査

- 調査日時: 2026-07-11
- 担当: tester
- 種別: read-only
- 修復操作: 未実施

## 結論

原因は **2026-07-08 18:29 JST の tester_mode バッチテストで
`recovery_exec_setup.yml -l ansy` を通常実行した際、ansy 固有の recovery-exec 公開鍵が
monnie / pve1 / pve2 の `authorized_keys` を上書きしたこと**である。

target 側の fingerprint は現在すべて ansy の鍵と一致し、production の接続元である
quory の鍵とは一致しない。このため quory の `homelab-investigate-*` wrapper は対象側で
公開鍵認証を拒否される。

quory の秘密鍵が最近再生成された形跡はなく、mtime は investigate/action が6月28日、
PVE investigate が7月5日のままである。壊れた時刻は target authorized_keys の mtime と
バッチ実行記録が一致する **2026-07-08 18:29 JST** と確定できる。

## 1. Controller 側鍵の mtime / fingerprint

### quory（production 接続元）

| key | private/public mtime | fingerprint |
| --- | --- | --- |
| investigate | 2026-06-28 20:18:55 | `SHA256:qF9qwzK0yKfW1wB5vHDcsbXDoo1nZ8IWOyn5wk34onc` |
| action | 2026-06-28 20:18:56 | `SHA256:+vnpLtIb7HrwbTZE51694i0/72MY56C1SqkOY0pg54g` |
| investigate-pve | 2026-07-05 13:33:27 | `SHA256:PPTy2+6doy8okIKMcDpWG/wUVcV1LRxvP1P3l0pztyI` |

秘密鍵はすべて `recovery-exec:recovery-exec 0600`。公開鍵は `root:root 0644`。
7月8日以降に生成・変更された鍵はない。

### ansy（development 接続元）

| key | private/public mtime | fingerprint |
| --- | --- | --- |
| investigate | 2026-06-28 17:09:38 | `SHA256:MIsr1ltYxhP2PJC91yZZ5fRL4TI7G/pF2pdwyPfM+W4` |
| action | 2026-06-28 17:09:39 | `SHA256:wc+CdN/m9xItwsVOMq+jhAlEhzDl+TGov8raiuBngg0` |
| investigate-pve | 2026-07-05 13:25:36 | `SHA256:280n2KYiDsE/S++PQpzPr+IaCapWGPMAbjFAcEf8mcI` |

ansy と quory は同じコメント名を持つが、別々に生成された異なる鍵ペアである。

## 2. Target authorized_keys

ansy から通常の `ann` Ansible経路で、対象側を read-only 確認した。

| target | authorized_keys mtime | 登録 fingerprint | controller 一致先 |
| --- | --- | --- | --- |
| monnie | 2026-07-08 18:29:13 | investigate `MIsr1...`; action `wc+Cd...` | **ansy** |
| pve1 | 2026-07-08 18:29:18 | investigate-pve `280n2...` | **ansy** |
| pve2 | 2026-07-08 18:29:18 | investigate-pve `280n2...` | **ansy** |

全ファイルは `recovery-exec:recovery-exec 0600`。権限不備ではない。

monnie は ansy の investigate/action 2本、PVEノードは ansy の PVE investigate 1本を
正確に保持している。quory の fingerprint はいずれの authorized_keys にもない。

## 3. sshd 認証ログ

本調査時の quory からの拒否は target 側 journal に次の形式で残っている。

```text
monnie 07:32:57 Connection closed by authenticating user recovery-exec ... [preauth]
pve1   07:32:09/07:32:29 Connection closed by authenticating user recovery-exec ... [preauth]
pve2   07:32:29 Connection closed by authenticating user recovery-exec ... [preauth]
```

client 側の確定エラー:

```text
recovery-exec@<target>.internal: Permission denied (publickey).
```

sshd の現行ログレベルでは、拒否された鍵の fingerprint や詳細理由は journal に出て
いない。ただし target authorized_keys と両 controller 公開鍵を `ssh-keygen -lf` で
直接突合し、target が ansy 鍵だけを許可していることを確認できたため、原因判定に
曖昧さはない。

## 4. 2026-07-08 バッチとの時系列・コード確認

`docs/ai/reviews/tester_mode/2026-07-08_019_test_result.md` には次が記録されている。

```text
recovery_exec_setup.yml | -l ansy 通常実行 | OK |
dispatcher/action scripts、authorized_keys、PVE sudoers、known_hosts に drift 修正あり。
```

対象 authorized_keys の mtime はこの実行時刻と一致する。

role の鍵生成 task は `ssh-keygen ... creates: <private-key>` であり、既存秘密鍵があれば
再生成しない。実際に ansy/quory とも鍵 mtime は7月8日より前である。従って「バッチで
鍵そのものが再生成された」のではない。

問題となるコード経路:

1. `recovery_exec_setup.yml -l ansy` が ansy 上で role を実行。
2. `recovery_exec_setup_targets` の default は `true`。
3. `target_setup.yml` が、**現在 role を実行している controller** の `.pub` 3本を slurp。
4. target の authorized_keys template は `drift-safe` として内容を完全管理し、
   monnie は2本、pve1/pve2 は1本へ上書き。
5. ansy と quory は別鍵なので、production quory の鍵が target から消える。

`recovery_probe_setup.yml` と `recovery_push_setup.yml` は、この outbound investigate/PVE
authorized_keys を生成・配布しない。`recovery_push_setup.yml` が扱うのは target から
quory へ入る push 用 authorized_keys であり、今回の直接原因ではない。

## 5. 原因判定

| 問い | 判定 |
| --- | --- |
| quory 鍵が7/8に再生成されたか | いいえ。mtime/fingerprintは以前のまま |
| target authorized_keys はいつ変わったか | 2026-07-08 18:29:13〜18 |
| target はどの鍵を持つか | ansy の鍵のみ |
| production 接続元はどの鍵を提示するか | quory の別鍵 |
| 直接原因 | `recovery_exec_setup.yml -l ansy` が target setup を伴って実行された |
| publickey 拒否の開始 | authorized_keys 上書き直後の 2026-07-08 18:29 JST 以降 |

## 6. 修復案（今回は未実施）

### 即時修復

Yoshinobu の承認後、**quory 正式 checkout から production 用 role を実行**して、quory
の公開鍵を target へ再配布する。

```bash
cd /home/yoshi/homelab-ansible
ansible-playbook playbooks/recovery_exec_setup.yml -l quory
```

この playbook は既存秘密鍵を `creates:` で保持したまま、quory の `.pub` を slurp して
monnie/pve1/pve2 authorized_keys を正しい production fingerprint に戻す。実行後は
以下の read-only 確認が必要。

```bash
sudo -H -u recovery-exec homelab-investigate-monnie status
sudo -H -u recovery-exec homelab-investigate-pve1 cluster-resources
sudo -H -u recovery-exec homelab-investigate-pve2 cluster-resources
```

action key も ansy版へ上書きされているため、`homelab-recover-monnie` 相当の action 経路も
quory鍵へ戻す必要がある。ただし実 action は変更操作なので、修復後の確認方法は
Yoshinobu が判断する（公開鍵 fingerprint 突合だけなら read-only）。

### 再発防止

`recovery_exec_setup.yml -l ansy` が production target の authorized_keys を変更できない
よう設計を分離する。推奨候補:

1. ansy 実行時は `recovery_exec_setup_targets=false` を強制し、target 配布は quory 実行時
   のみに assert/condition で制限する。
2. controller ローカル setup と target credential deployment を別 playbook に分離する。
3. 少なくともテスト手順では `-l ansy -e recovery_exec_setup_targets=false` を必須化する。

target に ansy/quory 両方の鍵を併記する案は、authorized_keys を「必要最小限・正確な本数」
で drift-safe 管理する現行ポリシーを広げるため、単なる応急処置ではなく Yoshinobu の
設計判断が必要。production 実行元が quory のみなら、quory 鍵だけを再配布するのが最小。

## 実行した主な read-only 確認

```bash
stat -c ... /home/recovery-exec/.ssh/id_recovery_*
ssh-keygen -lf /home/recovery-exec/.ssh/*.pub
ansible 'monnie:pve1:pve2' -b -m shell \
  -a 'stat ... authorized_keys; ssh-keygen -lf authorized_keys'
ansible 'monnie:pve1:pve2' -b -m shell \
  -a 'journalctl ... ssh/sshd ...'
```

## 追記: Yoshinobu 承認後の修復実行

Yoshinobu の承認を受け、quory 正式 checkout から提案した production key 再配布を
実行した。

```bash
cd /home/yoshi/homelab-ansible
ansible-playbook playbooks/recovery_exec_setup.yml -l quory
```

playbook は `# tester-gate: risk-accepted` のため通常実行した。既存秘密鍵生成 task は
`creates:` により no-op で、quory の鍵 fingerprint は修復前から変化していない。

主な変更:

- monnie / authy の investigate/action dispatch script を quory 正式 checkout 版へ同期
- monnie / authy の authorized_keys を quory investigate/action keys へ更新
- pve1 / pve2 の investigate dispatch / sudoers を同期
- pve1 / pve2 の authorized_keys を quory PVE investigate key へ更新
- quory の Codex `config.toml` に drift 修正あり
- サービス再起動なし

### Read-only wrapper 疎通確認

以下を `sudo -H -u recovery-exec` で実行し、すべて成功した。

```bash
homelab-investigate-monnie status
homelab-investigate-pve1 cluster-status
homelab-investigate-pve2 cluster-status
```

- monnie: prometheus / grafana-server / loki / unpoller の4サービスを取得でき、すべて
  `active (running)`。
- pve1: 2ノード、quorate の cluster status JSON を取得。
- pve2: 同じ2ノードの cluster status JSON を取得。

publickey 拒否は解消した。

### 修復後 fingerprint

| target | authorized_keys mtime | fingerprint | quory と一致 |
| --- | --- | --- | --- |
| monnie | 2026-07-11 07:42:13 | investigate `qF9q...`; action `+vnp...` | yes |
| pve1 | 2026-07-11 07:42:17 | investigate-pve `PPTy...` | yes |
| pve2 | 2026-07-11 07:42:18 | investigate-pve `PPTy...` | yes |

完全 fingerprint:

```text
monnie investigate: SHA256:qF9qwzK0yKfW1wB5vHDcsbXDoo1nZ8IWOyn5wk34onc
monnie action:      SHA256:+vnpLtIb7HrwbTZE51694i0/72MY56C1SqkOY0pg54g
pve1/pve2:          SHA256:PPTy2+6doy8okIKMcDpWG/wUVcV1LRxvP1P3l0pztyI
```

修復前に登録されていた ansy fingerprint (`MIsr...`, `wc+Cd...`, `280n...`) は target
authorized_keys からすべて外れた。これにより 7月8日の上書き前と同じ「production
quory の鍵だけを target が許可する」状態へ復元した。

### 修復判定

**修復成功。** production quory の investigate 経路は monnie / pve1 / pve2 の全対象で
復旧し、authorized_keys も quory fingerprint と完全一致した。実 recovery action
（サービス restart）は安全上実行していないが、action 公開鍵の配置一致は read-only
fingerprint 比較で確認した。
