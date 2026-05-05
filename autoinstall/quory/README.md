# quory autoinstall

Ubuntu Server 26.04 用の autoinstall 設定です。

quory は Proxmox クラスタ用の監視、quorum、Ansible 実行端末として使う想定ですが、この autoinstall では OS インストールと SSH 接続可能な状態までを対象にします。

## 作成される状態

- hostname: `quory`
- fqdn: `quory.internal`
- user: `yoshi`
- `yoshi` は sudo 権限あり
- SSH は公開鍵認証のみ
- SSH パスワードログインは禁止
- root の SSH ログインは禁止
- DHCP で IPv4 アドレスを取得
- 最大サイズのディスクへ Ubuntu Server をインストール
- `unattended-upgrades` は有効
- 更新適用後の自動再起動は無効

## 注意事項

この設定はインストール対象ディスクを初期化します。

`storage.layout.match.size: largest` により、検出された最大サイズのディスクがインストール先になります。既存データがある VM や物理マシンでは、実行前に対象ディスクを必ず確認してください。

## SSH 公開鍵

`user-data` 内の以下を実際の公開鍵に置き換えてください。

```yaml
ssh_authorized_keys:
  - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI_REPLACE_WITH_YOSHI_PUBLIC_KEY yoshi@quory"
```

## 配信方法

このディレクトリで HTTP サーバを起動します。

```bash
./serve-autoinstall.sh
```

デフォルトでは `<listen-address>:8080` で `user-data` と `meta-data` を配信します。

## GRUB カーネルパラメータ

Ubuntu Server インストーラの GRUB で、起動エントリに次のカーネルパラメータを追加してください。

```text
autoinstall ds=nocloud-net;s=http://ansy.internal:8080/
```

指定 URL の末尾 `/` は必要です。

## インストール後の確認

DHCP で割り当てられた IP アドレスを確認し、公開鍵でログインします。

```bash
ssh yoshi@<quory-ip-address>
```

ログイン後、必要に応じて Ansible で監視、quorum、実行端末としての追加設定を行います。
