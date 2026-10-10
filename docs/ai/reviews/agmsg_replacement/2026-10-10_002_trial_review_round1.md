# 試行: 計画Reviewer(codex exec、1回目)の最終メッセージ

`codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium -s read-only`、session id `01a12580-af9a-7200-a806-7a398a45f211`。原文のまま転記。

## Code Review: agmsg置き換え棚卸し

### Summary

Major 4件のblocking findingがあります。特に、発端の因果説明、DEVREQのpull可否、remote経路の構成、Slack移行時の安全境界は、候補判断前に修正が必要です。

### Blocking findings

1. **Major — `despawn.sh --force` が外れない理由をPID 1の生存判定に帰しているが、現行コードと食い違う**

   棚卸しは、PID 1が生存扱いになるため `spawn.sh --fresh` と `despawn.sh --force` の双方でlockが外れないとしています。[inventory:7](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:7)

   PID 1をagent PIDとして拾い、lockを生存扱いする経路自体は確認できました。[resolve-project.sh:297](/home/yoshi/.agents/skills/agmsg/scripts/lib/resolve-project.sh:297) [instance-id.sh:442](/home/yoshi/.agents/skills/agmsg/scripts/lib/instance-id.sh:442)

   しかし現行v1.3.1の`despawn.sh --force`は、その生死判定でlock解放を拒否する処理ではありません。記録されたpaneのteardownを確認した後、lock ownerを読み、明示的にreleaseします。[despawn.sh:116](/home/yoshi/.agents/skills/agmsg/scripts/despawn.sh:116) [despawn.sh:128](/home/yoshi/.agents/skills/agmsg/scripts/despawn.sh:128)

   したがって、`--force`が失敗したなら、placement record不在、pane teardown未確認、terminal driver失敗など、別の停止条件を実際の出力から特定する必要があります。`spawn --fresh`がPID 1 lockで止まることと、`despawn --force`の失敗原因を分離してください。

2. **Major — `oprc-replies.py`でDEVREQ全般をpullできるという主張が誤っている**

   棚卸しはOPRES/DEVREQをclient経由で取得できるとし、それをSlack案の返信経路にも使っています。[inventory:42](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:42) [inventory:66](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:66)

   実装がclientから取得するのは、引数で渡されたpending OPREQ IDに`in_reply_to`が一致する回答だけです。[oprc-replies.py:18](../../../../scripts/oprc-replies.py:18) [oprc-replies.py:56](../../../../scripts/oprc-replies.py:56)

   一方、DEVREQはOPREQへの返信に限らず、Operatorが単独発行できます。[operator-request-channel.md:39](../../../../docs/ai/context/operations/operator-request-channel.md:39) このstandalone DEVREQは既知OPREQとの突合では発見できず、現状はagmsg inbox側の通知に依存します。

   「返信DEVREQ」と「standalone DEVREQ」を分け、後者の発見・通知・再取得手段を候補ごとに示す必要があります。

3. **Major — B経路の構成と撤去影響から、ansy側sync engineとrepo内の依存実装が抜けている**

   付随設備はquory側sync engineだけを挙げています。[inventory:40](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:40) しかし5日停止Incidentの対象はansy側sync engineです。[2026-09-02 incident:5](../../../../docs/ai/memory/incidents/2026-09-02_agmsg-sync-engine-dead-for-five-days.md:5)

   repo内にも次の直接依存があります。

   - SessionStart文脈へansy側sync状態を載せる処理。[session-context.py:59](../../../../scripts/session-context.py:59) [session-context.py:125](../../../../scripts/session-context.py:125)
   - agmsgのteam・send・remote statusが無ければOPREQ登録前に停止するwrapper。[oprc-submit.sh:55](../../../../scripts/oprc-submit.sh:55) [oprc-submit.sh:72](../../../../scripts/oprc-submit.sh:72)
   - 両teamのagmsg inboxを読む受信処理。[oprc-replies.py:48](../../../../scripts/oprc-replies.py:48)
   - server用playbook、nginx/ufw/systemd watcher、Docker volume・secret。[agmsg_server_setup.yml:22](../../../../playbooks/agmsg_server_setup.yml:22) [agmsg_server main.yml:19](../../../../roles/agmsg_server/tasks/main.yml:19)

   `roles/agmsg_server/`等を「まだ確かめていない」とするだけでは、候補の影響比較に不足します。[inventory:74](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:74) ansy/quory双方のruntimeと、wrapper・hook・Context・Role・テスト・playbookまで依存表を作る必要があります。

4. **Major — OPREQ+Slack案が、現行の安全境界を満たすか評価されていない**

   現行remote経路はE2EEであり、サーバは平文を持ちません。[agent-messaging.md:116](../../../../docs/ai/context/operations/agent-messaging.md:116) またcross-team送信は、文面を提示してYoshinobuの同意を得る境界を持ちます。[agent-messaging.md:123](../../../../docs/ai/context/operations/agent-messaging.md:123) [agent-messaging.md:127](../../../../docs/ai/context/operations/agent-messaging.md:127)

   Slack案は「68件を置換できる」と結論していますが、次が未整理です。[inventory:66](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:66)

   - OPREQ、OPRES、返信DEVREQ、standalone DEVREQそれぞれの通知方向と受信者
   - Slackへ載せる要旨・IDの情報分類、保存・閲覧範囲
   - DLP、schema検証、非権限メッセージとしての扱い
   - 登録と通知の原子性、通知失敗、再送・重複時の挙動
   - 現行の送信前同意をどこで維持するか

   現行DLPは判定不能時に通さない設計です。[operator-request-channel.md:70](../../../../docs/ai/context/operations/operator-request-channel.md:70) 安全境界を定義せず「Bに当たる」と判定するのは早計です。

### Non-blocking findings

1. **Minor — Incident全件を同じ「状態ずれ」型にまとめる根拠がない**

   [inventory:58](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:58)の総括に対し、09-08はheadless bridgeが承認要求へ先にdeclineする決定的な競合動作です。[09-08 incident:24](../../../../docs/ai/memory/incidents/2026-09-08_codex-monitor-auto-declines-user-approval.md:24) また09-12は直接原因が未判明です。[09-12 incident:12](../../../../docs/ai/memory/incidents/2026-09-12_new_session_reset_socket.md:12)

   「状態ずれ」「設計上の競合」「原因未確定」に分けた方が、置換で解消できる障害と残る障害を判別できます。

2. **Suggestion — direct Codex案は、現時点では「当たる」ではなく条件付きとする**

   棚卸し自身が、権限・承認フローの同等性を未確認としています。[inventory:64](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:64) [inventory:71](../../../../docs/ai/reviews/agmsg_replacement/2026-10-10_001_inventory.md:71)

   現行はRole別model指定、Implementerの継続的な差し戻し対応、計画Reviewer/Auditorのfresh独立性を要求します。[coordinator.md:20](../../../../docs/ai/roles/coordinator.md:20) [coordinator.md:41](../../../../docs/ai/roles/coordinator.md:41) これらを`codex exec/resume`またはpluginで再現できることが確認されるまでは、適合判定を条件付きにするのが妥当です。

### 確認済み・未確認

確認済み:

- Role割当、A/B経路の本文分離、Operator非自動起動、serverのDocker/nginx/ufw/E2EE構成、Incident表の個別状態は概ね現物と一致。
- ローカルagmsgはv1.3.1。
- 着手時・返却時とも作業ツリーはclean。ファイル変更なし。
- メッセージ件数は指示どおり未照合。

未確認:

- fujibee/agmsg#1490、最新v1.5.3の実装、herdrの機能・ライセンス。repo外ホストへ接続していないため未確認。
- 10/10当日の実コマンド出力、placement record、gitignoredの`new-session.sh`現物。
- quory側の現在の実効状態。
- Slack通知基盤の実在・権限・配送保証。

### Verdict

**Request Changes** — blocking findingsの解消後に再査読が必要です。