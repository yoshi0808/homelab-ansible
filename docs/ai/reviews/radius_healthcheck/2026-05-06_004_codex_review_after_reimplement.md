# radius_healthcheck 再レビュー

## 1. 総評

前回 Codex レビューで指摘した主要点は、おおむね解消されています。

`radius_servers` は `inventories/lab.ini` ではなく `inventories/homelab/hosts.yml` に移され、`authy.internal` の名前ベース指定になっています。shell は引き続き収集と JSON 整形のみで、warning / critical / fail 制御は Ansible tasks 側にあります。restart / reload / reboot / patch / upgrade などの変更操作、radtest、証明書確認、設定構文チェックも混入していません。

ただし、`jq` 未導入時の扱いは「Ansible 側で事前 fail する」形になったため改善していますが、shell 単体としては `jq` がない場合に valid JSON を返せません。また、`inventories/homelab/hosts.yml` が既存の予定コメントを丸ごと置き換えて `radius_servers` のみになっているため、今後 `proxmox` / `control_nodes` / `dev_nodes` も同じ inventory に集約するなら構成上の注意点があります。

## 2. 前回指摘の解消状況

| 指摘 | 解消状況 | コメント |
|---|---|---|
| `inventories/lab.ini` ではなく `inventories/homelab/hosts.yml` を使う | 解消 | `inventories/lab.ini` から `radius_servers` が消え、`inventories/homelab/hosts.yml:4-7` に `authy` / `ansible_host: authy.internal` が定義された。 |
| IP 直書きを避け、名前ベースにする | 解消 | `authy.internal` が使われており、IP アドレス直書きはない。 |
| shell は判断せず、収集と JSON 整形のみ | 解消 | `roles/radius_healthcheck/files/radius-healthcheck.sh` 内では yes/no や count の収集値整形はあるが、warning / critical / fail 判定はしていない。 |
| warning / critical / fail 制御を Ansible tasks 側に置く | 解消 | `roles/radius_healthcheck/tasks/main.yml:37-50` で分類し、`101-104` で critical 時 fail している。 |
| check 系として read-only を守る | 概ね解消 | shell のコマンドは read-only。Ansible の script copy と report 保存はあるが、`core.md` で許容される配管・保存処理の範囲。 |
| report 保存先を `reports/radius-health/` にする | 解消 | `roles/radius_healthcheck/defaults/main.yml:2` が `{{ playbook_dir }}/../reports/radius-health`。 |
| localhost への report 保存を delegate する | 解消 | `roles/radius_healthcheck/tasks/main.yml:75-88` で `delegate_to: localhost` / `become: false`。 |
| `jq` 未導入時に JSON parse が壊れる問題 | 概ね解消 | `roles/radius_healthcheck/tasks/main.yml:2-12` で `jq` を事前確認して分かりやすく fail するようになった。ただし shell 単体では依然として `jq` なしで valid JSON を返せない。 |
| UDP 1812 / 1813 の listen 判定が粗い | 解消 | `ss -H -lun` と local address/port の末尾 `:1812` / `:1813` を見る形に改善された。 |
| script 配置で changed になり得る | 未解消だが許容 | `copy` タスクは初回や差分時に changed になり得る。`core.md` は `/usr/local/sbin/` への copy を許容しているため、今回は修正必須ではない。 |

## 3. 良い点

- `playbooks/radius_healthcheck.yml:3` が `radius_servers` を対象にしており、`core.md` の管理対象グループ方針に合っている。
- `inventories/homelab/hosts.yml` に `authy` が追加され、`ansible_host: authy.internal` になったため、前回の inventory 指摘は解消されている。
- `inventories/lab.ini` への `radius_servers` 追加は残っておらず、旧構成への追加依存は避けられている。
- shell は `systemctl`, `ss`, `journalctl`, `freeradius -v`, `chronyc tracking` の収集に留まり、秘密鍵、証明書秘密鍵、認証情報を読んでいない。
- `jq` の事前確認が Ansible tasks 側に追加され、未導入時に `from_json` の分かりにくい失敗へ進みにくくなった。
- `healthcheck_raw.stdout` の空チェックが追加され、空出力時の原因追跡が前回よりしやすい。
- report は control node 側へ保存される構成で、保存先も要求仕様に合っている。
- 初回除外項目の `radtest`、証明書ディレクトリ確認、設定ファイル構文チェックは実装されていない。
- restart / reload / reboot / patch / upgrade などの変更操作はない。

## 4. 修正必須

現時点で、テスト実行を止めるほどの修正必須事項はありません。

ただし、実運用前には `inventories/homelab/hosts.yml` をこの内容で正本にしてよいか確認してください。現在の diff では、既存の予定コメントを削除して `radius_servers` のみを定義しています。現時点で実体が未定義だったファイルを具体化しただけなら問題ありませんが、この inventory に `proxmox` / `control_nodes` / `dev_nodes` も集約する予定なら、後続で追記が必要です。

## 5. 修正推奨

1. `which jq` より `command -v jq` を使う

   - 該当箇所: `roles/radius_healthcheck/tasks/main.yml:2-7`
   - `which` は多くの環境で使えますが、POSIX shell の組み込みではありません。
   - Ansible の `command` で確認するなら、`cmd: command -v jq` の方が意図が明確です。
   - ただし、現状でも実用上は大きな問題ではありません。

2. `from_json` 失敗時のメッセージはまだ改善余地がある

   - 該当箇所: `roles/radius_healthcheck/tasks/main.yml:28-35`
   - 空 stdout は検出できますが、非 JSON の stdout が返った場合は `from_json` の例外になります。
   - 必須ではありませんが、`block` / `rescue` で stdout の先頭を出して fail すると、将来の調査が楽になります。

3. `inventories/homelab/hosts.yml` の全体構成を早めに固める

   - 該当箇所: `inventories/homelab/hosts.yml:1-7`
   - 今回の radius_healthcheck だけなら十分ですが、`core.md` の例では `proxmox`, `control_nodes`, `dev_nodes`, `radius_servers` を同じ inventory に置く想定です。
   - 後続作業で既存の `lab.ini` と二重管理にならないよう、移行方針を決めておくとよいです。

## 6. 今回は修正不要だが将来検討

- `chronyc tracking` の出力を構造化し、Ansible 側で同期異常を warning にする。ただし、今回の要求は収集なので現時点では不要。
- FreeRADIUS の service 名を default 変数化する。現在の要求は `freeradius` 前提なので現時点では不要。
- `journal_errors_raw` を文字列ではなく配列として JSON に入れる。現状でも valid JSON なので必須ではない。
- script 配置による changed を避けたい運用にするなら、`ansible.builtin.script` の一時実行方式や、配置 role と healthcheck role の分離を検討する。

## 7. 実行可否判断

このままテスト実行してよい

理由は、前回の修正必須だった inventory 方針と `jq` 未導入時の分かりにくい失敗が解消され、要求仕様外の変更操作も混入していないためです。

## 8. Claude Code への追加再実装依頼が必要か

不要です。

追加で直すなら軽微な改善として、`which jq` を `command -v jq` に変更する、非 JSON stdout 時の fail メッセージを改善する、程度です。テスト実行前に必須の再実装は不要です。

## 9. 実行前にユーザーが確認すべきこと

以下を確認してください。

```bash
ansible-inventory -i inventories/homelab/hosts.yml --graph
```

```bash
ansible -i inventories/homelab/hosts.yml radius_servers -m ping
```

```bash
ansible -i inventories/homelab/hosts.yml radius_servers -b -m command -a 'command -v jq'
```

```bash
ansible-playbook -i inventories/homelab/hosts.yml playbooks/radius_healthcheck.yml --check
```

注意点として、`--check` では `/usr/local/sbin/radius-healthcheck.sh` の copy タスクが changed 予定として表示される可能性があります。これは現実装の構成上あり得る挙動で、healthcheck の判定処理自体が変更操作をしているという意味ではありません。
