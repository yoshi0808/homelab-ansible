# Sandbox VM Operations Context

作成日: 2026-08-06

## 位置づけ

本書は使い捨て検証VM `sandbox` の使い方を扱う**非規範runbook**である。実ホストへの操作の許可・禁止・承認境界は [`docs/ai/roles/coordinator.md`](../../roles/coordinator.md)「実ホストへの非冪等操作の承認」が正本であり、競合時はそちらを優先する。採らないと決めた案の一覧は [`docs/ai/status.md`](../../status.md)「載せていないもの」が持つ。IP、認証情報、秘密情報の実値は記載しない。

## 1. 何のためのVMか

**ansy から到達できる、壊してよい実ホスト**である。これまで decoy(実ホストへ触れずに実行経路だけ通す仕組み)で代替してきた検証を、実際のホストで通すためにある。

- ansy / quory の双方から同じ `ann` 鍵で繋がる
- **監視対象ではない。** quory から定期的に何かを流すこともしない
- 承認境界では `monnie` / `ansy` と同じ「確認不要」側にある。家庭向けサービスを提供せず、内容はGitから再現可能か失っても停止を招かない
- Proxmox 側では HA へ `state: ignored` で登録されており、パッチ中は停止される。**常時稼働を前提にしない**

**恒久的な開発環境をここへ作らない。** 作り込むと壊すのが惜しくなり、使い捨てであること自体の価値が失われる。特定プロダクトの開発環境が要るなら別のVMを立てる。

## 2. production との乖離

**乖離しない仕組みが既に効いている。** `unattended-upgrades` が enabled かつ active で、Allowed-Origins に `-security` と `-updates` の両方を含む。Ubuntu のリリースも ansy / monnie と揃っている(2026-08-06 実測)。

したがって**パッケージを追随させるために何かをする必要はない**。逆に、スナップショットへ定期的に巻き戻す運用はこの追随を打ち消すため採らない。

## 3. 使い方 — sandbox インベントリ

```bash
ansible-playbook -i inventories/sandbox/hosts.yml --forks 1 <playbook>
```

**production の playbook を1行も書き換えずに sandbox へ向けられる。** インベントリは実ホスト名(`pve1` / `quory` / `authy` …)をそのまま持ち、**全員の `ansible_host` が sandbox を指す**形になっている。playbook から見た世界は production と同じ形で、違うのは全員の住所が同じことだけである。

この形にしてある理由は、名前が効く箇所がいくつもあるためである。

| 名前が効く箇所 | 例 |
|---|---|
| `groups[...]` を参照する assert | `recovery_probe_setup` が `groups['proxmox']` に pve1/pve2 が居ることを要求する |
| `hosts:` の literal 指定 | `incident_capture_setup` の `hosts: quory` |
| `delegate_to` が名前でホストを掴む | `recovery_exec` が `delegate_to: authy` |
| ホスト名をキーにした role 側の allow-list | `time_sync_ntp_reference_chrony_hosts` |

**既定は production のままである。** `ansible.cfg` の `inventory` は `inventories/homelab/hosts.yml` を指しており、sandbox インベントリは `-i` で明示したときだけ効く。付け忘れて sandbox へ行くことはなく、逆も無い。

**これは安全機構ではない。** ansy が pve1 / pve2 / authy / quory / sophos-fw へ届かないのは鍵が無いからであって、このインベントリのおかげではない。増やしているのは「試せる範囲」であって「守り」ではない。

### `--forks 1` は必須である

**複数のホスト名が同じ1台を指すため、Ansible が既定で行うホスト並列実行が「同じホストへの同時実行」になる。** 同じパスへ書きに行くタスクはここで壊れる。

実例(2026-08-06): `recovery_exec_setup` の SSH 鍵生成は `creates:` を持つが、**`creates:` は再実行を防ぐもので同時実行を防がない**。`ansy` と `quory` の2コンテキストが同時に「鍵は無い」と判定して両方 `ssh-keygen` を実行し、後発が既存ファイルを見つけて `Overwrite (y/n)?` で標準入力待ちになり、47分ハングした。

**production では起きない。** あちらは名前と実体が1対1なので、並列実行しても別々のホストを触る。**この形に固有の落とし穴である。**

## 4. 確かめられること・確かめられないこと

**確かめられる**のは、playbook のロジックが実ホスト上で意図どおり動くかである。`--check` と通常実行で挙動が変わるゲート(`when: not ansible_check_mode`)の検証がその典型で、decoy では原理的に通せない。reboot を挟んで play が再開するかどうかも通せる。

**確かめられない**ものは次のとおり。

- **「N台に別々の設定が入る」こと。** 全員が同じ1台なので、複数ホストを別々に設定する playbook は同じホストへ重ねて適用される
- **後続 play の挙動**(前の play が失敗したとき)。同じ1台なので、失敗ホストの除外が後続 play にも効く。`ubuntu_nightly` で実際に起きた — radius play が CRITICAL で落ち、monitoring play は走らなかった
- **Proxmox 固有の操作。** `qm` / `pvesh` は Ubuntu VM では落ちる。無害だが得るものも無い
- **production の前提を要する処理**(次節)

### production にあって sandbox に無いもの

ここで止まったら、gate の欠陥ではなく前提の欠落を疑う。

| 前提 | 影響を受ける例 |
|---|---|
| Semaphore(`/var/lib/semaphore`) | `recovery_exec_setup` / `incident_inspect_setup` が ACL 付与で停止する |
| CA 材料(ROOT CA 証明書) | `ca_trust_deploy` が `delegate_to` での slurp に失敗する |
| freeradius | `ubuntu_nightly` の radius play が成功側へ到達しない |

**足すかどうかは「環境を作り込まない」方針との兼ね合いで決める。** 1つ足すと次を足したくなる方向なので、その検証にどれだけの価値があるかを先に問う。

## 5. 壊したとき

**黙って直そうとせず、壊したと報告する。** 復旧はYoshinobuがバックアップから行う。中途半端に修復すると、バックアップ時点とも現状とも一致しない状態が残り、次に触る人が何を前提にしてよいか分からなくなる。

- ローカルバックアップ: 毎日、保持1週間
- Synology: 毎週、保持6か月
- **すぐ報告すれば直前の日次へ戻せる。** 放置するほど戻せる地点は粗くなる

**綺麗な状態が要るのは曜日ではなく、それを要求するテストを走らせる直前である。** そのときにオンデマンドで戻す。

**AIからバックアップの実施状況は確認できない**(Proxmox のバックアップジョブは ansy から見えない)。本節はYoshinobuの明示による。

## 6. 再現手段の無い変更を残さない

sandbox へ加えた変更のうち、**repo に再現手段があるものと無いものを区別する。** 古いバックアップから復元したとき、後者は手でやり直すことになる。

2026-08-06 時点で再現手段が無いもの: hostname を `ubuntu` から `sandbox` へ変えたこと、`/etc/hosts` のループバック別名を `<fqdn> <short>` の形へ揃えたこと(いずれも ansy からの ad-hoc 操作、commit `b20c43d`)。

ad-hoc で何かを変えたときは、ここへ足すか playbook 側へ持たせるかを決める。
