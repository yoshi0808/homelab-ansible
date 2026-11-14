# Proxmox Watch 稼働バージョン v2 キー一覧

このページはコードブロックだけで構成する。読み手は先頭ブロックの`state: complete`だけを有効なスナップショットとして扱う。`updating`は途中失敗または更新中であり、本文を読まない。

## ヘッダ

| キー | 意味 | 値域 |
|---|---|---|
| `schema_version` | 書式の版 | `2` |
| `state` | 更新原子性の状態 | `updating` / `complete` |
| `updated_at` | 完全な本文を確定した時刻 | `+09:00`付き ISO 8601、`updating`中は`unknown` |
| `status` | 5ノードを集約した結果 | `ok` / `partial` / `error`、`updating`中は`unknown` |
| `node_count` | 固定対象数 | `5` |

## ノードブロック

順序は`pve1`、`pve2`、`quory`、`authy`、`monnie`で固定する。

| キー | 意味 | 値域 |
|---|---|---|
| `node` | inventory上のノード名 | 上記5値 |
| `status` | そのノードの収集結果 | `ok` / `unreachable` / `error` |
| `os` | OSと版 | `debian-<version>` / `ubuntu-<version>`、取得不能は`unknown` |
| `role` | 読み手の該当判定用の固定役割 | pve1/pve2=`pve`、quory=`qdevice`、authy=`radius`、monnie=`monitoring` |
| `repo` | 有効なPVE apt repository | `enterprise` / `no-subscription` / `test`（複数はカンマ区切り）、非PVEは`n/a`、取得不能は`unknown` |
| `kernel_running` | `uname -r` | 文字列、取得不能は`unknown` |
| `kernel_installed` | dpkg版比較で最新の起動可能カーネル実体の版 | 文字列、取得不能は`unknown` |
| `kernel_reboot_required` | 新カーネルまたは`/run/reboot-required`による再起動要否 | `true` / `false`、取得不能は`unknown` |
| `services_restart_required` | 削除済みライブラリを保持するプロセス | 先頭は`count=N; ライブラリ -> プロセス[, プロセス]`、2行目以降は各`ライブラリ -> ...`。`none` / `unknown`、上限超過時の末尾は`(+N more)` |
| `last_apply_at` | pveの直近apply report時刻 | patch reportのJST基本形式を変換した`+09:00`付き ISO 8601 / `unknown`、非PVEは`n/a` |
| `last_apply_result` | 直近apply reportの結果 | `SUCCESS` / `FAILED` / `unknown`、非PVEは`n/a` |
| `reboot_required` | reportの`reboot_trigger`から導いた直近apply時の要否 | `true` / `false` / `unknown`、非PVEは`n/a` |
| `reboot_done` | reportの再起動実施値 | `true` / `false` / `unknown`、非PVEは`n/a` |
| `last_apply_upgraded` | 直近apply以降のapt upgrade | `パッケージ 旧->新`のカンマ区切り / `none` / `unknown`、非PVEは`n/a`。上限超過時は末尾`(+N more)` |
| `vms_on_old_qemu` | 起動後のQEMU更新を反映していないVM | running VMの`/proc/<pid>/exe`が` (deleted)`なら数える`N (VMID,VMID)` / `0` / `unknown`。版文字列は比較しない。非PVEは`n/a` |
| `pve_manager` | `pve-manager`版 | 文字列 / `unknown`、非PVEは`n/a` |
| `collected_at` | そのノードの収集時刻 | `+09:00`付き ISO 8601 / `unknown` |
| `package_count` | package blockの`part`行を除く行数 | 非負整数。到達不能・収集errorは`0` |

`status: unreachable`または`error`では、`node`、`status`、既知の`role`、`package_count: 0`以外を`unknown`にし、package blockは出さない。古い値を残さない。

## パッケージブロック

各ノードの直後に0個以上置く。node blockとpackage blockはいずれもNotionの1 rich-text content上限より小さい1,900文字に収める。node blockが長くなる場合は`services_restart_required`、続いて`last_apply_upgraded`を`(+N more)`で短縮する。

| キー / 行 | 意味 | 値域 |
|---|---|---|
| `part` | package blockの通番 | `i/n` |
| `<package name>` | installed版と、異なるときだけcandidate版 | `<installed>` または `<installed> (candidate <candidate>)` |

PVEでは、installed版またはcandidate版がProxmox originのinstalled packageを全件載せる。ただし版ごとの`proxmox-kernel-<ABI>-pve` / `-signed`実体は除外し、kernel meta packageは残す。Debian固定一覧も載せる。Ubuntuではkernel meta packageと固定一覧のinstalled分を載せる。

`n/a`はそのノード種別に意味を持たないキーだけに使う。`none`は取得成功した空集合、`unknown`は取得不能・不正値・report不在を表す。
