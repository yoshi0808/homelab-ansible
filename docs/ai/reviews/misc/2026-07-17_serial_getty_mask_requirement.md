# Ubuntu VM の serial-getty@ttyS0 mask（agetty 無限リスタート抑止）— 要求仕様

- 日付: 2026-07-17
- 起案: claude / 承認: Yoshinobu（2026-07-17、Ansible mask 方式）
- 前提調査: `docs/ai/reviews/misc/2026-07-17_terminal_attr_error_investigate.md`

## 目的

Ubuntu VM で `serial-getty@ttyS0.service` の agetty が、実体のないシリアルバックエンド(`uart:unknown`)に対して端末属性取得に失敗し、`Restart=always` で約10秒ごとに再起動して `failed to get terminal attributes: Input/output error` を吐き続けている。Proxmox VM の console は Web(noVNC/SPICE)経由で serial-getty は不要のため、これを stop + mask してノイズを止める。

## スコープ

- 対象: Ubuntu VM（ansy / monnie / quory / authy）。pve1/pve2 は対象外（別プラットフォーム・今回の症状は Ubuntu VM）。
- 新規の小 role or playbook（例 `playbooks/serial_getty_mask.yml`）で `serial-getty@ttyS0.service` を **stop + mask**（`systemd: name=serial-getty@ttyS0.service state=stopped masked=true` 相当）。冪等。
- 可逆: `unmask`(+必要なら start) で原状復帰できる手順を implement に明記。

## 実施・確認

1. 冪等な stop + mask。既に masked なら changed=false。
2. tester-gate 分類を付与（サービス停止を伴うが、監視対象サービスではない＝recovery probe は monnie:3000 / authy:22 等を見ており serial-getty には非依存。mute は不要と判断。ただし分類は「無条件 APPLY 可」にはせず dry-run 前提）。
3. pre-deploy(tester read-only): 各ノードで `serial-getty@ttyS0` の現状（active/enabled/masked）と、**実シリアル console を使っていないこと**（`uart:unknown`、serial0 依存の console access が無い）を確認。実シリアル console を使うノードがあれば mask 対象から除外する（本 homelab では uart:unknown 確認済みで該当なしの見込み）。
4. mask 後、agetty プロセスが消え、`failed to get terminal attributes` の新規ログが止まることを Loki `{job="ubuntu-nodes", host=~"ansy|monnie|quory|authy"}` で確認（今日追加した収集経路の実益検証も兼ねる）。

## 制約

- serial-getty 以外のサービス・設定に触れない。GRUB/cmdline は変更しない（本件は mask のみ。根本の console=ttyS0 除去は別途）。
- 秘密・IP をリポジトリに書かない。APPLY は人間ゲート。

## Next step files

- docs/ai/reviews/misc/2026-07-17_serial_getty_mask_requirement.md（本ファイル）
- docs/ai/reviews/misc/2026-07-17_serial_getty_mask_implement.md（implementer が作成）
