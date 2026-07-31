#!/bin/sh
# incident-sync-trigger — ansy(dev_nodes)に配備する、SSH forced command
# 専用の起動スクリプト。
#
# 呼び出し元: quoryのincident-investigate.py(roles/incident_investigate/
# files/incident-investigate.py の trigger_ansy_sync())。
# 設計の正本: docs/ai/reviews/incident_investigation_notify/
# 2026-08-01_001_requirement.md N5・N8・N9。
#
# N8「引数を一切取らない固定のアクション」: このスクリプトは
# $SSH_ORIGINAL_COMMAND を一切参照しない(読んでいる箇所が存在しない)。
# 接続元がSSHコマンドラインに何を書いても、ここで実行される内容には
# 一切反映されない — authorized_keysの `command=` がSSHサーバ側で
# 強制しているため、このスクリプト自身の中で改めて検証・拒否する必要すら
# 無い(そもそも渡ってこない)。
#
# 実行する内容は1つだけ、かつ即座に返る(--no-block): このoneshot unitの
# 実行完了(最大 incident_sync_timeout_start_sec 秒)を待たない。呼び出し元
# (incident-investigate.py)にとって重要なのは「起動を要求したこと」で
# あって「転送が完了したこと」ではない — 転送の成否はansy側の
# _sync/last-sync.json とSlack通知(roles/incident_sync/tasks/finalize.yml)
# が別途扱う。
set -eu
sudo /bin/systemctl start --no-block ansible-incident-sync.service
