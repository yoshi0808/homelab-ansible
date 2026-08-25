# 第2束フェーズ2(中2件)実装記録(2026-08-25)

対象: `2026-08-25_004_fix_scope.md`「第2束」2.「中2件」の2項目(S2-3 / P1-8・P5-3)。

## 変更ファイル一覧

- `docs/ai/roles/reviewer.md`
- `docs/ai/policies/cert_renew_cloudkey_policy.md`
- `docs/ai/policies/unifi_backup_fetch_policy.md`

## 項目ごとの充足

| 項目 | 対応 | 参照先の実在確認 |
|---|---|---|
| S2-3(重大度分類の正本新設) | `docs/ai/roles/reviewer.md`「成果物と返却先」の直後へ「## 重大度分類」節を新設。Critical/Major/Minor/Suggestionの4段階とblockingの意味、Verdict 3値(Approve / Request Changes / Needs Discussion)との対応を、fix_scopeの定義文どおりに記述。新しい語彙・段階は追加していない | `skills/code-review/SKILL.md`(Verdict 3値の出典)、`skills/ansible-correctness-review/SKILL.md:32`・`skills/document-norm-review/SKILL.md:116`・`skills/test-gap-review/SKILL.md:35`(いずれも「重大度…はreviewer.mdを正本とする」の指し先)が、新設節の見出し・内容と実際に一致することを確認した。4 Skill自体は無変更(元々reviewer.mdを指しており、指し先を変える必要がない) |
| P1-8/P5-3(CloudKey認証契約の一本化) | CCK-008(`cert_renew_cloudkey_policy.md`)を、ログインパス・TOKEN cookie・状態変更系の認証ヘッダー(Cookie/X-CSRF-Token/Origin)・ホスト名接続・`validate_certs: false`の正本と明記する1文を追加し、CSRFトークンの行に「CSRF導出は実装ごとに異なる」旨とUNIFI-007への相互参照を追記。UNIFI-007(`unifi_backup_fetch_policy.md`)側は、上記の重複規定文(ログインURL/ボディの再掲、TOKEN cookieの再掲、認証ヘッダーの再掲、`validate_certs: false`の再掲)をCCK-008へのポインタへ置換し、自分の差分であるCSRF導出(ヘッダー優先+JWT fallback)だけを詳細に残した。UNIFI-001の「共有」文言にも共有範囲・正本(CCK-008)への参照を追記 | CSRF導出の分岐が実装の実挙動であることを自分でも読んで確認: `roles/cloudkey_cert_deploy/tasks/deploy.yml:30-45`はJWTペイロードの`csrfToken`のみを使用(ヘッダーを見ない)、`roles/unifi_backup_fetch/tasks/main.yml:55-71`はレスポンスヘッダー(`X-CSRF-Token`優先、次点`X-Updated-CSRF-Token`)を先に見てJWTはfallback。fix_scope記載のfile:lineと一致。UNIFI側から削った各文は、削除前にCCK-008側の対応文の実在を逐語で確認済み: ログインパス/ボディ形状→CCK-008表の「ログイン \| POST /api/auth/login \| {username, password}」、TOKEN cookie→CCK-008「ログイン応答の`Set-Cookie`の`TOKEN`(JWT、有効2時間)を使う」、認証ヘッダー→CCK-008「状態変更系(POST/PUT/DELETE)には…Cookie: TOKEN=<JWT> / X-CSRF-Token: <csrfToken> / Origin: https://cloudkey.internal」、`validate_certs: false`→CCK-008「私設CA証明書のため`validate_certs: false`」。credential保管path(`inventories/vars/cloudkey.yml`)とアカウント種別(ローカルアカウント・2FA無効)はCCK-008に対応文が無いため削除せずUNIFI側に残置した(fix_scopeの一本化対象5項目に含まれない) |

両Policyの変更履歴表へ既存書式で1行追記した(CCK: v1.4、UNIFI: v1.5)。CCK/UNIFIいずれもルールID(CCK-xxx/UNIFI-xxx)の新設・退番は行っていない。

## 自己検証

- 重大度分類の定義が既存レビュー記録の実際の用法と矛盾しないか: `docs/ai/reviews/norm_docs_audit/2026-08-25_011_review_phase1.md`等の既存review記録がCritical/Major/Minor/Suggestionをこの意味で使っていることをfix_scope文言との一致で確認(fix_scopeの定義は2026-08-25にCoordinatorが実測のうえ確定したものであり、その定義をそのまま転記したため定義自体の齟齬はない)。Verdict 3値(Approve/Request Changes/Needs Discussion)は`skills/code-review/SKILL.md:30`の実在表記と一致させた。
- UNIFI側から削った各文について、CCK-008側の対応文の実在を上表「参照先の実在確認」欄で逐語突き合わせした(マーカーの実在だけで済ませていない)。
- 両Policyの記述が実装の実挙動と一致しているか: `roles/cloudkey_cert_deploy/tasks/deploy.yml`と`roles/unifi_backup_fetch/tasks/main.yml`を自分で読み、CSRF導出の分岐がfix_scope記載のfile:lineどおりであることを確認した(実ホストへは触れていない)。
- `python3 scripts/check-doc-consistency.py` → `[check1] OK (114 compared)` / `[check2] OK (8 compared)` / `[check3] OK (104 compared)`、exit 0。
- 重大度分類を指す4 Skill(code-review / ansible-correctness-review / document-norm-review / test-gap-review)は無変更のまま、reviewer.mdの新設節を指して実際に解決することを`grep -n "重大度"`で確認した。
- IPアドレス・秘密情報・トークン形式の実値は追加していない(diffに実値なし)。
- 変更対象は上記3ファイルと本記録のみで、他のリポジトリ内ファイルは変更していない(`git status --short`で確認)。実ホストへのansible/ssh/curlは実行していない。git add/commitは行っていない。

## 未解決事項

なし。2項目とも方向どおりに実装完了。第2束の残り(越境5件のうち未実施分があれば)は本記録の対象外。
