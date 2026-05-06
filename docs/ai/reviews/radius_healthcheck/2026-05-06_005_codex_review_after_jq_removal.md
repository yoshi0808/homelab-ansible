# radius_healthcheck jq依存除去後レビュー

## 1. 総評

jq 依存は実装対象から外れています。

`roles/radius_healthcheck/tasks/main.yml` には jq の事前確認が残っておらず、`roles/radius_healthcheck/files/radius-healthcheck.sh` も jq を呼ばず、Python 標準ライブラリの `json.dumps` で JSON を生成する形に変更されています。`apt install jq` や package module による jq 導入処理もありません。jq への言及は過去レビュー文書内に残るだけで、現在の実装前提にはなっていません。

JSON 出力も、`journalctl` や `chronyc tracking` の複数行、ダブルクォート、バックスラッシュ、改行を Python の JSON encoder がエスケープするため、jq 版より堅い構成です。現時点でテスト実行を止める修正必須事項はありません。

一方で、`systemctl is-active freeradius || echo "inactive"` は、サービスが inactive / failed の場合に `inactive\ninactive` や `failed\ninactive` のような値を作る可能性があります。health 判定自体は critical になるため致命的ではありませんが、レポートの値が汚れるので修正推奨です。

## 2. jq依存の除去状況

- `roles/radius_healthcheck/tasks/main.yml` に `which jq` / `command -v jq` / jq 未導入時の fail は残っていない。
- `roles/radius_healthcheck/files/radius-healthcheck.sh` は jq を呼んでいない。
- `apt install jq`、`ansible.builtin.apt`、`ansible.builtin.package` などで jq を導入する処理はない。
- `authy` 側に jq をインストールする前提は、現在の実装対象には残っていない。
- `rg` で確認した範囲では、jq への言及は `docs/ai/reviews/radius_healthcheck/2026-05-06_002_codex_review.md` と `2026-05-06_004_codex_review_after_reimplement.md` の過去レビュー文書内のみ。

## 3. JSON出力の安全性

`python3` と標準ライブラリ `json` を使っているため、JSON エスケープは妥当です。

- `journal_errors_raw` の複数行は環境変数経由で Python に渡され、`json.dumps` により `\n` としてエスケープされる。
- `chronyc tracking` の複数行、ダブルクォート、バックスラッシュも `json.dumps` が valid JSON として処理する。
- `journal_error_count` は shell 側で数値化した値を Python 側で `int()` にしており、JSON では number として出る。
- `systemctl`, `ss`, `journalctl`, `freeradius -v`, `chronyc tracking` が失敗しても、基本的には fallback 値や空文字を使うため JSON 構造は壊れにくい。

注意点として、JSON 生成は `python3` の存在に依存します。ただし、このリポジトリの `ansible.cfg` は `interpreter_python = /usr/bin/python3` であり、Ansible 管理対象として Python 3 前提は妥当です。より厳密にするなら shell 内の呼び出しを `python3` ではなく `/usr/bin/python3` に寄せるか、対象 OS の前提として Python 3 を明記するとよいです。

## 4. 良い点

- jq の事前確認 task が削除され、authy に jq を入れる前提がなくなった。
- shell は収集と JSON 整形のみで、warning / critical / fail 判定は混ざっていない。
- warning / critical / fail 制御は `roles/radius_healthcheck/tasks/main.yml` 側にある。
- `Run radius healthcheck` は `changed_when: false` で、確認コマンド実行自体を changed 扱いにしていない。
- restart / reload / reboot / patch / upgrade はない。
- apt / package module による追加パッケージ導入はない。
- 秘密鍵、証明書秘密鍵、認証情報を読む処理はない。
- `freeradius` service active、1812/udp、1813/udp、journal の 1 時間以内 ERROR/FATAL、FreeRADIUS version、`chronyc tracking` の要求項目を満たしている。
- 初回除外項目の `radtest`、証明書ディレクトリ確認、設定ファイル構文チェックは実装されていない。
- report 保存先は `reports/radius-health/` で、保存処理は `delegate_to: localhost` / `become: false` になっている。
- inventory は `inventories/homelab/hosts.yml` 方針に沿い、`authy` は `authy.internal` の名前ベース指定になっている。
- `ansible.cfg` も `inventories/homelab/hosts.yml` を見るようになっており、旧 `inventories/lab.ini` / `inventories/prod.ini` 依存は見当たらない。

## 5. 修正必須

修正必須事項はありません。

このままテスト実行してよい状態です。

## 6. 修正推奨

1. `systemctl is-active` の fallback を整理する

   - 該当箇所: `roles/radius_healthcheck/files/radius-healthcheck.sh:8`
   - 現在は `freeradius_service_active=$(systemctl is-active freeradius 2>/dev/null || echo "inactive")`。
   - `systemctl is-active` は inactive / failed などの状態文字列を stdout に出したうえで non-zero を返すことがあるため、値が `inactive\ninactive` や `failed\ninactive` になる可能性がある。
   - 修正方針は、まず `systemctl is-active ... || true` で出力をそのまま収集し、空の場合だけ `unknown` や `inactive` を入れる形がよい。
   - これは JSON 破壊や判定漏れには直結しないため、テスト前の必須修正ではない。

2. Python 3 前提を明確化する

   - 該当箇所: `roles/radius_healthcheck/files/radius-healthcheck.sh:44`
   - `python3` がない環境では JSON が出ず、Ansible 側の空 stdout fail になる。
   - Ansible 管理対象として Python 3 前提は妥当だが、より明確にするなら `/usr/bin/python3` を使うか、requirements / README に Python 3 前提を明記するとよい。

3. 非 JSON stdout 時の fail メッセージ改善

   - 該当箇所: `roles/radius_healthcheck/tasks/main.yml:21-23`
   - 空 stdout は検出できるが、非 JSON stdout の場合は `from_json` の例外になる。
   - `block` / `rescue` で stdout の一部を出すと、将来の調査がしやすい。

## 7. 今回は修正不要だが将来検討

- `journal.errors` を文字列ではなく配列にして、report 側で扱いやすくする。
- `chronyc tracking` の出力を構造化し、Ansible 側で同期異常 warning を追加する。ただし、今回の要求は収集なので現時点では不要。
- FreeRADIUS service 名を default 変数化する。現要求では `freeradius` 固定で問題ない。
- script 配置による changed を避けたい場合は、一時実行方式や配置 role 分離を検討する。

## 8. 実行可否判断

このままテスト実行してよい

jq 依存は実装から外れており、authy に jq をインストールする前提も残っていません。JSON 生成は Python 標準の `json.dumps` により、複数行や特殊文字にも強い構成です。

## 9. Claude Code への追加再実装依頼が必要か

不要です。

追加で改善するなら、以下の短い依頼で十分です。

```text
radius-healthcheck.sh の systemctl is-active 収集で、inactive / failed 時に値が二重化しないようにしてください。
warning / critical 判定は引き続き Ansible tasks 側に置き、shell は収集と JSON 整形のみにしてください。
```

ただし、これはテスト実行前の必須再実装ではありません。

## 10. 実行前にユーザーが確認すべきこと

以下を確認してください。

```bash
ansible-inventory -i inventories/homelab/hosts.yml --graph
```

```bash
ansible -i inventories/homelab/hosts.yml radius_servers -m ping
```

```bash
ansible -i inventories/homelab/hosts.yml radius_servers -b -m command -a 'python3 --version'
```

```bash
ansible-playbook -i inventories/homelab/hosts.yml playbooks/radius_healthcheck.yml --check
```

jq の確認コマンドや jq インストールは不要です。
