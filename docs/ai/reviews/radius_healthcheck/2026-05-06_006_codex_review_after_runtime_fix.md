# radius_healthcheck runtime fix review

## 1. 総評

今回の runtime fix は妥当です。

`ss -H -lun` の local address/port は今回の出力前提では `$4` を見るのが正しく、1812/udp と 1813/udp の listen 判定が実行結果と一致する方向に修正されています。FreeRADIUS version も `grep -m1` で 1 件に絞る形になり、二重出力を避ける意図に合っています。report ファイル名の日時参照も `ansible_facts['date_time']['iso8601_basic_short']` に変更されており、deprecation warning 解消として妥当です。

`core.md` の責務分離にも違反していません。shell は収集と JSON 整形のみで、warning / critical / fail 制御は Ansible tasks 側にあります。read-only 制約に反する restart / reload / reboot / patch / upgrade などもありません。

テスト結果も `Status: OK`, `Criticals: []`, `Warnings: []` とのことで、このまま commit してよい状態です。

## 2. 良い点

- `roles/radius_healthcheck/files/radius-healthcheck.sh` は引き続き収集と JSON 整形のみで、warning / critical 判定を shell 側に持ち込んでいない。
- UDP port 判定が `awk '{print $4}'` に修正され、`ss -H -lun` の local address/port を見る意図と合っている。
- port 判定は `grep -qE ':1812$'` / `':1813$'` で末尾 port を見ており、単純な部分一致より安全。
- FreeRADIUS version 収集は `grep -m1 -oE 'Version [0-9][0-9.]+' | awk '{print $2}'` で 1 件に絞られており、二重出力対策として妥当。
- JSON 生成は Python 標準の `json.dumps` で行われており、複数行やクォートを含む journal / chrony 出力でも JSON が壊れにくい。
- `roles/radius_healthcheck/tasks/main.yml` で warning / critical / fail 制御を行っており、責務分離に沿っている。
- `ansible_facts['date_time']['iso8601_basic_short']` への変更は、`gather_facts: true` の playbook 前提と整合している。
- report 保存は `delegate_to: localhost` / `become: false` で control node 側に行われる。
- restart / reload / reboot / patch / upgrade、package install、radtest、証明書確認、設定構文チェックは混入していない。
- 秘密鍵や証明書秘密鍵の中身、認証情報を読む処理はない。

## 3. 修正必須

修正必須事項はありません。

今回確認した範囲では、runtime fix による重大な副作用は見当たりません。

## 4. 修正推奨

1. 実行生成 report JSON の commit 対象を明確にする

   - `reports/radius-health/authy_20260506T185405.json` と `reports/radius-health/authy_20260506T190045.json` が未追跡で存在する。
   - healthcheck 実行ログとして残す運用なら commit してもよいが、通常は実行ごとの生成物は commit 対象から外す方が扱いやすい。
   - 今回の実装 commit では、少なくとも意図せず report JSON を混ぜないように確認するのがよい。

2. `systemctl is-active` の fallback は将来整理するとよい

   - 該当箇所: `roles/radius_healthcheck/files/radius-healthcheck.sh:8`
   - `systemctl is-active` は inactive / failed の文字列を stdout に出したうえで non-zero を返すことがあり、`|| echo "inactive"` により値が二重化する可能性がある。
   - 今回のテストでは問題化しておらず、active 時は問題ないため commit 前の必須修正ではない。

## 5. 今回は修正不要だが将来検討

- `journal.errors` を文字列ではなく配列にして、report 側で扱いやすくする。
- `chronyc tracking` の出力を構造化し、Ansible 側で同期異常 warning を追加する。
- FreeRADIUS service 名を default 変数化する。
- 実行ごとの report JSON を Git 管理しない方針なら、`reports/radius-health/*.json` を ignore するか、保存先を Git 管理外にする。

## 6. commit可否

このままcommitしてよい

## 7. 理由

今回の runtime fix は、実行時に見つかった問題に対して局所的で妥当な修正です。

UDP 1812 / 1813 の listen 判定は `ss -H -lun` の local address/port 列を見るようになり、FreeRADIUS version の二重出力も 1 行目の version 抽出で解消されています。Ansible facts の参照も `gather_facts: true` と整合しており、deprecation warning 解消として自然です。

また、shell と Ansible tasks の責務分離、read-only 制約、report 保存先、localhost delegate、秘密情報を扱わない方針はいずれも維持されています。

commit 時は、実装・inventory・レビュー文書など意図したファイルだけを staging し、テスト実行で生成された `reports/radius-health/*.json` を含めるかどうかは別途判断してください。
