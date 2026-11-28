# 実測出力(2026-11-28、Yoshinobuが両nodeでrootとして実行。状態を変えない)

requirement 7章末「実測」の原文。解析関数のfixtureはこの出力をそのまま使う。

## pve1: `proxmox-boot-tool status` / `proxmox-boot-tool kernel list`

```text
Re-executing '/usr/sbin/proxmox-boot-tool' in new private mount namespace..
System currently booted with uefi
FD82-D827 is configured with: uefi (versions: 6.17.13-21-pve, 7.0.14-28-pve, 7.0.14-30-pve)
FD83-332D is configured with: uefi (versions: 6.17.13-21-pve, 7.0.14-28-pve, 7.0.14-30-pve)
Manually selected kernels:
None.

Automatically selected kernels:
6.17.13-21-pve
7.0.14-28-pve
7.0.14-30-pve
```

## pve2: `proxmox-boot-tool status` / `proxmox-boot-tool kernel list`

```text
Re-executing '/usr/sbin/proxmox-boot-tool' in new private mount namespace..
System currently booted with uefi
23F7-21A8 is configured with: uefi (versions: 6.17.13-21-pve, 7.0.14-28-pve, 7.0.14-30-pve)
Manually selected kernels:
None.

Automatically selected kernels:
6.17.13-21-pve
7.0.14-28-pve
7.0.14-30-pve
```

## pve2: `apt-get -s purge proxmox-kernel-6.17.13-21-pve-signed`

```text
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
The following packages were automatically installed and are no longer required:
  proxmox-kernel-6.17.13-11-pve-signed proxmox-kernel-6.17.13-13-pve-signed
  proxmox-kernel-6.17.13-14-pve-signed proxmox-kernel-6.17.13-15-pve-signed
  proxmox-kernel-6.17.13-18-pve-signed proxmox-kernel-6.17.13-19-pve-signed
  proxmox-kernel-6.17.13-4-pve-signed proxmox-kernel-6.17.13-7-pve-signed
  proxmox-kernel-7.0.12-1-pve-signed proxmox-kernel-7.0.14-11-pve-signed
  proxmox-kernel-7.0.14-12-pve-signed proxmox-kernel-7.0.14-14-pve-signed
  proxmox-kernel-7.0.14-15-pve-signed proxmox-kernel-7.0.14-16-pve-signed
  proxmox-kernel-7.0.14-17-pve-signed proxmox-kernel-7.0.14-19-pve-signed
  proxmox-kernel-7.0.14-2-pve-signed proxmox-kernel-7.0.14-20-pve-signed
  proxmox-kernel-7.0.14-23-pve-signed proxmox-kernel-7.0.14-24-pve-signed
  proxmox-kernel-7.0.14-25-pve-signed proxmox-kernel-7.0.14-26-pve-signed
  proxmox-kernel-7.0.14-4-pve-signed proxmox-kernel-7.0.14-5-pve-signed
  proxmox-kernel-7.0.14-6-pve-signed proxmox-kernel-7.0.14-8-pve-signed
  proxmox-kernel-7.0.2-2-pve-signed proxmox-kernel-7.0.2-6-pve-signed
  proxmox-kernel-7.0.6-2-pve-signed
Use 'apt autoremove' to remove them.
The following additional packages will be installed:
  proxmox-kernel-6.17.13-21-pve
The following packages will be REMOVED:
  proxmox-kernel-6.17.13-21-pve-signed*
The following NEW packages will be installed:
  proxmox-kernel-6.17.13-21-pve
0 upgraded, 1 newly installed, 1 to remove and 0 not upgraded.
Purg proxmox-kernel-6.17.13-21-pve-signed [6.17.13-21] [proxmox-kernel-6.17:amd64 ]
Inst proxmox-kernel-6.17.13-21-pve (6.17.13-21 Proxmox Debian Repository:stable [amd64])
Conf proxmox-kernel-6.17.13-21-pve (6.17.13-21 Proxmox Debian Repository:stable [amd64])
```

## pve2: `dpkg --simulate --purge proxmox-kernel-6.17.13-21-pve-signed`

```text
dpkg: dependency problems prevent removal of proxmox-kernel-6.17.13-21-pve-signed:
 proxmox-kernel-6.17 depends on proxmox-kernel-6.17.13-21-pve-signed | proxmox-kernel-6.17.13-21-pve; however:
  Package proxmox-kernel-6.17.13-21-pve-signed is to be removed.
  Package proxmox-kernel-6.17.13-21-pve is not installed.
  Package proxmox-kernel-6.17.13-21-pve-signed which provides proxmox-kernel-6.17.13-21-pve is to be removed.
 proxmox-kernel-6.17 depends on proxmox-kernel-6.17.13-21-pve-signed | proxmox-kernel-6.17.13-21-pve; however:
  Package proxmox-kernel-6.17.13-21-pve-signed is to be removed.
  Package proxmox-kernel-6.17.13-21-pve is not installed.
  Package proxmox-kernel-6.17.13-21-pve-signed which provides proxmox-kernel-6.17.13-21-pve is to be removed.

dpkg: error processing package proxmox-kernel-6.17.13-21-pve-signed (--purge):
 dependency problems - not removing
Errors were encountered while processing:
 proxmox-kernel-6.17.13-21-pve-signed
```

pve1の `apt-get -s purge` / `dpkg --simulate --purge` は、「no longer required」一覧が `6.17.13-11` / `-4` / `-7`、`7.0.2-2` を含まない点を除いてpve2と同じ出力だった。
