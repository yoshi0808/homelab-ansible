# 2026-07-11 Proxmox patch apply 所要時間差の調査

- 調査日: 2026-07-11
- 担当: tester
- 種別: read-only
- 対象: pve2 / pve1 の `apt-get -y dist-upgrade`

## 結論

所要時間差の主因は **ダウンロード速度の差**。パッケージ内容や node 側の install /
initramfs 処理性能ではない。

両ノードは全く同じ5パッケージ、同じ257 MBを処理した。しかし pve2 は
`4分43秒 / 909 kB/s`、pve1 は `31秒 / 8,190 kB/s` で download した。
download 時間差は252秒で、playbook 観測の全体差約240秒を単独で説明できる。

download 後の dpkg/install 区間は逆に pve2 が47秒、pve1 が58秒であり、pve2 の
処理性能が遅かった事実はない。

## 対象レポート

quory の保存レポート:

```text
reports/proxmox-patch/20260711T074728_pve2_apply.json
reports/proxmox-patch/20260711T075906_pve1_apply.json
```

両方とも:

- `result: SUCCESS`
- pre/post healthcheck: `OK`
- reboot: 実施済み
- reboot trigger: installed kernel `7.0.14-4` と旧 running kernel `7.0.14-2` の不一致
- remove: なし

## パッケージ内容の比較

両ノードの transaction は完全一致した。

```text
3 upgraded, 2 newly installed, 0 to remove and 0 not upgraded
```

| 種別 | package | version / size |
| --- | --- | --- |
| upgrade | postfix | `3.10.12-0+deb13u2`, 1,609 kB |
| new | proxmox-kernel-6.17.13-15-pve-signed | `6.17.13-15`, 125 MB |
| upgrade | proxmox-kernel-6.17 | `6.17.13-15`, 12.6 kB metapackage |
| new | proxmox-kernel-7.0.14-4-pve-signed | `7.0.14-4`, 131 MB |
| upgrade | proxmox-kernel-7.0 | `7.0.14-4`, 13.1 kB metapackage |

両ノードとも:

```text
Need to get 257 MB of archives.
After this operation, 2,021 MB of additional disk space will be used.
```

pve-qemu / ZFS packageの更新はない。重量級要素は2本の signed kernel package
（合計約256 MB）で、これも両ノード共通。

## ダウンロード比較

| node | archive | apt fetch result | 平均速度 |
| --- | ---: | ---: | ---: |
| pve2 | 257 MB | 4分43秒 | 909 kB/s |
| pve1 | 257 MB | 31秒 | 8,190 kB/s |

pve1 は pve2 の約9倍の平均 download 速度だった。

playbook が記録した command 開始と apt history の開始を突合すると、apt history の
`Start-Date` は download 完了後、dpkg transaction 開始時刻に相当する。

| node | command 開始 | download/dpkg境界 | transaction終了 | download区間 | dpkg区間 |
| --- | --- | --- | --- | ---: | ---: |
| pve2 | 07:47:41 | 07:52:24 | 07:53:11 | 4分43秒 | 47秒 |
| pve1 | 07:59:16 | 07:59:48 | 08:00:46 | 約32秒 | 58秒 |

この分解では pve2 の全体約5分30秒、pve1 の全体約1分30秒と一致する。

## install / initramfs 処理

両ノードの `/var/log/apt/term.log` には同じ処理が同じ順序で記録されている。

```text
Setting up proxmox-kernel-7.0.14-4-pve-signed ...
update-initramfs: Generating /boot/initrd.img-7.0.14-4-pve
Setting up postfix ...
Setting up proxmox-kernel-6.17.13-15-pve-signed ...
update-initramfs: Generating /boot/initrd.img-6.17.13-15-pve
Setting up proxmox-kernel-6.17 ...
Setting up proxmox-kernel-7.0 ...
Processing triggers for man-db ...
Processing triggers for postfix ...
```

両ノードとも2 kernel分の initramfs を生成した。pve2 だけの追加 kernel / ZFS /
pve-qemu / initramfs 工程はない。dpkg区間も pve2 の方が11秒短いため、disk/CPU性能が
全体差の原因という説明とは逆の観測である。

dpkg database のファイル数は pve2 が134,345、pve1 が103,842で pve2 の方が多いが、
その差を含めても transaction 実時間は pve2 の方が短い。今回の4分差には寄与していない。

## 実行後確認

read-only `uname -r`:

```text
pve1: 7.0.14-4-pve
pve2: 7.0.14-4-pve
```

両ノードとも新 kernel で正常に再起動済み。

## 原因分類

| 候補 | 判定 | 根拠 |
| --- | --- | --- |
| パッケージ内容の差 | 否定 | package/version/count/size/initramfs工程が完全一致 |
| ダウンロード | **主因** | 同じ257 MBが283秒対31秒。差252秒 |
| 処理性能 | 否定 | download後はpve2=47秒、pve1=58秒 |

## 補足

本調査で確定できるのは「apt archive download が遅かった」までである。なぜその時点の
pve2 が909 kB/sだったか（瞬間的な mirror/network path/帯域競合等）は、保存された
apt reportだけではさらに分解できない。ただし patch所要時間差の直接原因は定量的に
確定しており、node の package workload や install 性能ではない。

## 実行した主な read-only 確認

```bash
cat reports/proxmox-patch/20260711T074728_pve2_apply.json
cat reports/proxmox-patch/20260711T075906_pve1_apply.json
uname -r
sed -n '/Start-Date: 2026-07-11  07:/,/End-Date:/p' /var/log/apt/history.log
grep ... /var/log/apt/term.log
```

