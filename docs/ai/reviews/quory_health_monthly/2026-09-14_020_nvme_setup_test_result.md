# quory NVMe取得ツール配備 — テスト結果

## Verdict

静的検証および安全な合成inventoryのnegative検証は **Pass**。実機受入は **Not Run / 未判定**。したがってAC-S1〜S4を実機成立済みとは判定しない。

## 実施した検証

| 結果 | コマンド／確認 | 観測 |
|---|---|---|
| Pass | `ansible-playbook --syntax-check playbooks/quory_nvme_setup.yml` | rc=0 |
| Pass | `bash scripts/check-tester-gate.sh` | `OK (63 playbooks)` |
| Pass | `python3 scripts/check-doc-consistency.py` | check1/2/3 OK |
| Pass | `git diff --check` | rc=0 |
| Pass | `ansible-lint playbooks/quory_nvme_setup.yml roles/quory_nvme_setup` | production profile、0 failure/0 warning |
| Pass | `python3 -m unittest discover -s tests -p 'test_*.py'` | 71/71 OK |
| Pass | `scripts/safe-ansible-check.sh playbooks/quory_nvme_setup.yml -i 'localhost,' --limit localhost --check` | rc=2。quory不在inventoryをpreflight assertが検出し、setup playへ進まない。localhost以外への接続なし |
| Pass | `scripts/safe-ansible-check.sh ...` から `--check` を除いた呼出し | wrapperがrc=2で拒否。Ansibleへ委譲されない |
| Pass | `ansible-doc` とsource inspection | `package_facts`/`apt`のcheck-mode supportはfull。readback blockは `when: not ansible_check_mode` + `tags: [destructive]`。`update_cache`はpackage未導入時だけ真 |
| Pass | catalog/source inspection | `playbooks/quory_nvme_setup.yml` は1件、README掲載あり、schedulesへの追加なし。health playbook/roleは差分なし |

## AC判定と未実施

- AC-S1: **部分Pass（local evidenceのみ）**。check-mode境界とquory不在fail-closedは確認したが、実quoryでの対象限定、導入見込み表示、rc=0、通知/report非生成はdeployment readback待ち。
- AC-S2: **部分Pass（source/static evidenceのみ）**。導入済み時のcache更新を避ける構造とCLI失敗のfail-closedを確認したが、実quoryへのapply、再実行、`nvme version`成功は未実施。
- AC-S3: **Not Run**。実quory setup後の月次health `--check`、`tool_unavailable`の消失、別原因への分類は未確認。
- AC-S4: **部分Pass（local catalog evidenceのみ）**。template 1件・schedule非追加・syntaxは確認したが、Semaphore実機readbackは未実施。

## 制限・残存リスク

実quory／実inventory／Semaphore API／本番Slack・Notionには接触していない。実ホスト名を含むdecoy inventoryも実行していない。APT package/cacheを変更する実適用は安全境界上禁止のためNot Run。`nvme-cli`導入後に実デバイスの `id-ctrl` / `smart-log` が成功するか、health collectorが `tool_unavailable` 以外の理由へ遷移するかは未確認であり、Yoshinobuの承認後の配備工程で確認が必要。
