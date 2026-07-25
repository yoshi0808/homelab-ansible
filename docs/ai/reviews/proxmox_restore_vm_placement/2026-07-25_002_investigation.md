# proxmox_restore_vm_placement external reachability gate調査

## 1. 調査範囲

- requirement: `2026-07-25_001_requirement.md`
- review: `2026-07-25_004_review.md`
- snapshot HEAD: `d3d175778b35e31035135b592acbf81f5d5d198b`
- 対象: role tasks / defaults、新規固定Python helper
- 比較対象: `roles/recovery_probe/files/recovery-probe.py`の`external_reachable()`
- 未実施: 実playbook、実機、外部HTTP、recovery action

## 2. 現状とgate境界

旧roleはHA-managed VMのnode配置と`running`だけを待ち、直後に`proxmox_healthcheck`をincludeしていた。VM processの`running`はSophos Firewall guest内のrouting / DNS回復を保証しない。

gateは既存の`when: not ansible_check_mode`かつ`tags: [destructive]`のblock内で、HA復帰wait後、healthcheck前へ置く。target nodeへhelperを一時転送して同nodeで実行し、alwaysで削除する。check modeではgate / healthcheckとも未実行で、reportの`PLAN_ONLY`を維持する。

## 3. HTTP判定とcredential境界

helperは`urllib.request.Request(url, method="HEAD")`を使う。正常responseまたは`HTTPError`はstatusに関係なく`REACHABLE`、`URLError` / socket timeout / transport `OSError`はretryableな`UNCONFIRMED`とする。redirectは追わず、3xx response自体をHTTPErrorとしてreachableにする。

openerは空の`ProxyHandler({})`、HTTP / HTTPS handler、no-redirect handlerだけから構成する。proxy環境、netrc、Basic / Digest authentication handler、credential storeを参照しない。header、body、auth optionも追加しない。URLはHTTP(S) DNS-nameだけを許し、userinfo / IP literalをAnsibleとhelperの双方で拒否する。URLはshellでなくcommand `argv`の1要素として渡す。

## 4. monotonic deadline / budget

defaultsはrequest timeout 5秒、poll interval 15秒、overall timeout 300秒である。helperは`time.monotonic()`で`deadline = started + overall`を一度だけ確定し、各requestへ`min(request_timeout, remaining)`、各sleepへ`min(poll_interval, remaining)`を渡す。

この方式はresponse速度に依存しない。networkなしのfake clock / opener test結果は次のとおりである。

| case | 実HTTP回数 | elapsed | overshoot |
|---|---:|---:|---:|
| DNS等の即時failure、既定値 | 20 | 300.0秒 | 0 |
| 各requestが5秒timeout、既定値 | 15 | 300.0秒 | 0 |
| HTTPError response | 1 | 0.0秒 | 0 |
| overall 7 / request 5 / poll 15の即時failure | 1 | 7.0秒 | 0 |
| 同overrideのrequest timeout | 1 | 7.0秒 | 0 |

attemptsは`opener.open()`直前だけincrementするため実HTTP回数と一致する。Ansibleはtiming値のinteger / 正数と`overall >= request`を算術前にassertし、helperも正数 / budget関係を再検証する。pollがoverallより長いoverrideでもsleepをremainingへcapし、budget不足や大幅overshootを作らない。

## 5. failure / report

network exhaustionはhelperがrc=0で`{"status":"UNCONFIRMED", ...}`をstdoutへ返す。AnsibleがJSONのstatus / attempts / elapsedと`elapsed <= overall + 1`を検証し、`UNCONFIRMED`を専用failへ確実に流す。専用failはHA復帰済み、Sophos経由外部到達性未確認、healthcheck停止、人間による`playbooks/recovery_vm_reboot.yml -e target=sophos-fw`手動実行案内を含む。

helperのconfiguration / code / JSON異常はrc非0またはassert failureとなり、既存outer rescueへ流す。recovery actionのinclude / import / command / subprocessはない。reportにはhelperが返した実attemptsとmonotonic elapsedを追加し、check modeは`NOT_RUN` / 0 / 0のままとする。

## 6. 編集・検査計画

編集は許可されたrole tasks / defaults / helper / 002 / 003の最大5 pathだけとする。fake unit、Python compile、syntax-check、ansible-lint、yamllint、gate順序、credential handler、report、実値、scope、`git diff --check`を静的に確認する。実playbookはTester工程へ残す。
