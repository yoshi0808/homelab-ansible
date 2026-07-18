# CA root trust investigation (2026-07-19)

## 結論

`verify_ssl` 失敗の根本原因は、クライアントへ配布する trust anchor の定義漏れである。`deploy_ca_trust` は quory の `home_tls_ca.crt`（中間 CA）だけを `/usr/local/share/ca-certificates/home-tls-ca.crt` に配布し、自己署名ルート CA `radius_ca.crt` を配布していない。

monnie の配布済み中間 CA は quory の原本と fingerprint が一致し、`update-ca-certificates` のリンクおよび system bundle への収録も確認できた。ansy でも同じ depth/error を再現したため、monnie 固有の drift ではない。

分類は次のとおり。

- 主因: **definition omission** — trust role にルート CA の配布定義がない。
- 併発要因: **single-certificate gotcha** — 配布元・配布先とも「中間 CA 1 枚だけ」で、ルートを含む bundle ではない。
- 否定: **host drift** — 配布された中間 CA と update-ca の反映状態は定義どおりである。

## Repository evidence

- `roles/homelab_cert_renew/defaults/main.yml:8` は `cert_renew_ca_src_crt` を `/home/yoshi/.cert/ca/home_tls_ca.crt` に固定している。
- `roles/homelab_cert_renew/tasks/deploy_ca_trust.yml:4,12` はその 1 ファイルだけを `/usr/local/share/ca-certificates/home-tls-ca.crt` に配置する。
- 同 task にルート CA の copy 定義はない。
- 一方、`roles/cloudkey_cert_deploy/defaults/main.yml:21,23` は中間 CA `home_tls_ca.crt` とルート CA `radius_ca.crt` を別ファイルとして認識している。

## Live evidence

調査は Ansible 経由の read-only コマンドだけで実施した。証明書の一意な subject は以下で役割名に置換している。

### 1. quory の CA material

`/home/yoshi/.cert/ca/` には次の公開証明書が存在する。

| ファイル | PEM certificate 数 | Subject | Issuer | Basic Constraints | SKI / AKI | Self-signed |
|---|---:|---|---|---|---|---|
| `home_tls_ca.crt` | 1 | `<Intermediate-CA>` | `<Root-CA>` | critical, `CA:TRUE, pathlen:0` | SKI `3B:09:…:47:48`; AKI `1E:4D:…:88:57` | No |
| `radius_ca.crt` | 1 | `<Root-CA>` | `<Root-CA>` | critical, `CA:TRUE` | SKI = AKI `1E:4D:…:88:57` | Yes |

親子関係は、中間 CA の AKI とルート CA の SKI の一致、および `openssl verify -CAfile radius_ca.crt home_tls_ca.crt` の成功で確認した。中間 CA 単体の self-verify は error 20（local issuer 不在）で失敗し、ルート CA は自身を CAfile とした検証に成功した。

SHA-256 fingerprint は中間 CA が `14:51:…:4A:07`、ルート CA が `29:80:…:F6:F0`。ルート CA の OpenSSL subject hash は `a3e2b1a9` である。秘密鍵の内容は参照していない。

### 2. cloudkey が提示する chain

monnie から `openssl s_client` で確認した提示 chain は 3 枚で、順序は次のとおりだった。

1. `<cloudkey-leaf>` — issuer `<Intermediate-CA>`
2. `<Intermediate-CA>` — issuer `<Root-CA>`
3. `<Root-CA>` — issuer `<Root-CA>`（self-signed）

したがって、server-side の chain 欠落や並び順不正ではない。ただし、server がルート CA を提示しても、それだけで client の trust anchor にはならない。

### 3. monnie の trust store

- `/usr/local/share/ca-certificates/home-tls-ca.crt` は PEM certificate 1 枚のみで、内容は `<Intermediate-CA>`。
- SHA-256 fingerprint は `14:51:…:4A:07` で quory の中間 CA 原本と一致する。
- subject hash `778fe839` に対し、`/etc/ssl/certs/778fe839.0 -> home-tls-ca.pem` が存在する。
- `/etc/ssl/certs/ca-certificates.crt` は全 122 枚。そのうち subject が `<Intermediate-CA>` の証明書は 1 枚、subject が `<Root-CA>` の証明書は 0 枚。
- ルート CA の subject hash `a3e2b1a9` に対応する `/etc/ssl/certs/a3e2b1a9.*` も存在しない。

つまり `update-ca-certificates` は配布された中間 CA を正常に取り込んでいるが、取り込むべきルート CA 自体が配布されていない。

### 4. system CAfile による leaf verify

monnie で cloudkey の leaf を取り出し、次の条件で検証した。

```text
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt <leaf>
```

結果:

```text
error 2 at 1 depth lookup: unable to get issuer certificate
verification failed
VERIFY_RC=2
```

depth 1 は `<Intermediate-CA>`。その issuer である `<Root-CA>` を system CAfile から見つけられないことを直接示している。`s_client` に system CAfile と CApath を明示した場合も、同じ depth 1 / error 2 だった。

### 5. 別ホストでの比較

ansy でも system CAfile/CApath を明示した `openssl s_client -verify_return_error` を実行し、次を再現した。

```text
depth=1 <Intermediate-CA>
verify error:num=2:unable to get issuer certificate
Verify return code: 2 (unable to get issuer certificate)
S_CLIENT_RC=1
```

異なる managed host で同じ issuer lookup failure が発生するため、monnie の局所的な破損・更新漏れではなく、共通の trust 配布定義に起因する。

## Root-cause statement

quory には自己署名ルート CA が存在し、cloudkey も leaf → intermediate → root の順で chain を提示している。しかし client trust role は中間 CA 1 枚だけを配布している。monnie の system bundle にルート CA が存在しないため、OpenSSL は depth 1 の中間 CA から trusted root へ chain を完結できず、error 2 で失敗する。

この調査では設定変更、証明書配布、reload、restart、commit は実施していない。
