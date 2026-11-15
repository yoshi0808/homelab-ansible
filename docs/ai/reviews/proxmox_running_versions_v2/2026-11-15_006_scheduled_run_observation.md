# 定期実行の観測(2026-11-15 07:00)

観測日: 2026-11-15(Coordinator)

## 07:00 の定期実行

- 確認手段: Notion「Proxmox Watch: 稼働バージョン」ページを Notion MCP の fetch で読んだ(読み取りのみ)。
- ヘッダ: `schema_version: 2` / `state: complete` / `updated_at: 2026-11-15T07:00:13+09:00` / `status: ok` / `node_count: 5`。
- 5ノードとも `status: ok`。`collected_at` は 2026-11-15T07:00:10〜11+09:00。
- pve1 / pve2: `package_count: 143`、パッケージブロックは `part: 1/3`〜`3/3`。`services_restart_required` は `count=1; /usr/lib/x86_64-linux-gnu/libz.so.1.3.1 -> ...`(pve1 `(+7 more)`、pve2 `(+9 more)`)。`last_apply_upgraded` は 11/14 の apply で上がった4パッケージ(libcares2、vim-common、vim-tiny、zlib1g)を `旧->新` で表示。`last_apply_at` は `+09:00` 付き ISO 8601。
- quory / authy / monnie: `kernel_running: 7.0.0-43-generic`、`kernel_reboot_required: false`、`services_restart_required: none`、apply 系のキーは `n/a`。authy の systemd に `(candidate 259.9-0ubuntu0.1)`。
- 前日(手動実行 #1858)からの変化: authy は 2026-11-14 21:16 に `update-notifier-common` の導入後に再起動され(Yoshinobu 操作、Coordinator が `kernel-status` / `stale-libs` / `status` で確認)、`services_restart_required` が `none` になった。quory・monnie の `kernel_reboot_required` も `false` になっている(再起動の経緯は本観測の範囲外で未確認)。

判定: 定期実行は v2 書式で成功している。

## 読み手(Proxmox Watch 定期タスク、07:55)

- 2026-11-14 夜、読み手は Yoshinobu 経由で、当時のページを翌朝と同じ規則で試し読みし、`package_count` と各ノードの行数の一致、`part` の連続、`count=N` と行数の一致を報告した(Yoshinobu が会話へ貼った読み手の回答)。
- 2026-11-15 07:55 の実行結果(Coordinator が Proxmox Watch DB の対処メモを Notion MCP の SQL で読んだ。読み取りのみ):
  - 16件のエントリに `[2026-11-15 版比較]` の行が足されており、いずれも「稼働バージョンページ v2(updated_at 2026-11-15T07:00:13+09:00、state: complete / status: ok)」を出典にしている。
  - パッケージの版との比較が行われている。例: PSA-2026-00088-1(libpve-guest-common-perl 6.0.7 / libpve-storage-perl 9.1.15 / qemu-server 9.2.15 が修正版以上)、PSA-2026-00089-1、00092-1、00093-1、00094-1、00095-1、00100-1 で「対応済の可能性が高い」。前日まではいずれも「版が載っておらず直接比較不可」だった。
  - 「Proxmox origin は全件掲載」を根拠に、一覧に無いパッケージ(proxmox-backup-server、proxmox-datacenter-manager、libmime-tools-perl 等)を「PVE ノードには未インストールのため非該当の可能性」と判定している(PSA-2026-00086/87/91/96/97/98/99-1)。
  - Ubuntu 3台の `kernel_running` / `kernel_installed` を使って CVE-2026-98432 を判定している。
  - CVE-2026-99284 では、メタパッケージ `proxmox-kernel-7.0` に candidate 表示が無いことから「新しいカーネルはまだ来ていない」と判定している。

判定: 読み手は v2 を読めており、v2 で足した情報(パッケージの版、候補版、ノードの種別)を判定に使っている。
