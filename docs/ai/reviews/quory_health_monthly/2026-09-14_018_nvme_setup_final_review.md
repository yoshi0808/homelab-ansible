## Code Review: quory NVMe CLI setup 最終再査読

### Summary

012要求・013計画・016/017のblocking 2件と現行playbook/role・015追記を照合した。対象0件の空成功と、時間経過後にAPT cacheを再更新する非冪等性は、今回の差分で解消したと判断する。

### Critical Issues

なし。

### Major Issues

なし（016/017の2件はclose）。

### Suggestions

なし。

### What Looks Good

- `playbooks/quory_nvme_setup.yml:52-70`のsetup完了factとlocalhost postflightにより、inventoryにquoryが存在しても`--limit localhost`でsetup playが0件となる経路を非0停止できる。`scripts/safe-ansible-check.sh playbooks/quory_nvme_setup.yml -i inventories/homelab/hosts.yml --limit localhost --check`をローカル限定で独立実行し、preflight `ok`、setup play `no hosts matched`、postflight失敗、rc=2を確認した。通常の引数なし起動ではpre/postflightがlocalhost、setupがquoryに到達し、role完了後のfactを確認する構造であり、正当な起動を遮断する条件は見当たらない。`--limit quory`ではlocalhost側のguardは対象外になるが、quoryのsetup playは対象となり、導入・readback経路を妨げない。
- `roles/quory_nvme_setup/tasks/main.yml:4-22`は`package_facts(manager: apt)`で現在の導入状態を読み、導入済みなら`update_cache: false`にする。APT moduleのcache更新分岐は`update_cache`または`cache_valid_time`が真のときだけであり、後者はもはや指定されていない。導入済み再実行は経過時間に依存せずcache更新を要求せず、`state: present`も変更不要になる。未導入時だけcache更新・導入を試み、途中失敗後の再実行でもその時点の導入状態から再判定する。
- ローカルの`ansible-doc`で`package_facts`と`set_fact`のcheck-mode supportがともにfullであることを確認した。aptはcheck modeで`cache.update()`を呼ばず、readback blockは通常実行に限定される。package_facts/apt/readbackの失敗は吸収されず非0となる。`ansible-playbook --syntax-check playbooks/quory_nvme_setup.yml`はrc=0。観測入口・既存Proxmox経路は未変更、専用templateは1件、schedule追加は無い。shell補間・機密露出・新規reconcileロジックの重複も見当たらない。

### 未確認事項

- 実quory・Semaphore APIには接触していない。AC-S1/S2の実機check→apply→CLI readback、AC-S3の月次health `--check`での`tool_unavailable`解消、AC-S4の実Semaphore template/schedule readbackは配備工程で未確認のまま。
- `nvme version`はCLI実行可否を示すが、実デバイスでの`id-ctrl`/`smart-log`成功は示さない。012のオープンクエスチョンとして維持する。

### Verdict

Approve（静的差分レビュー）。実機受入条件の成立を承認した意味ではなく、016/017のblocking解消を確認した判定。
