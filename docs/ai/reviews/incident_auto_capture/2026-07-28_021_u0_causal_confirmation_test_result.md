# U0 — 因果モデルの実機確認(read-only)test_result

- 作成: 2026-07-28 Tester(subagent)
- 対象計画: `docs/ai/reviews/incident_auto_capture/2026-07-28_018_acl_mask_plan.md` §1(因果モデル)、§4 U0
- 実行環境: ansy(接続元) → `ansible quory -m command ...`(すべて `-b` 付き)
- 変更操作: **ゼロ。** `getfacl` / `stat` / `ls | wc -l` / `systemctl status` のみ実行した。timer/serviceの起動・停止、設定変更、ファイル作成・削除・移動、`ansible-playbook` の実行は一切行っていない。`git config` 等の変更もしていない。

---

## 1. 観測事実(O1〜O6)

### O1 — `getfacl` on `reports/incidents/`(兄ディレクトリ)

実行コマンド:
```
ansible quory -m command -a "getfacl /home/yoshi/homelab-ansible/reports/incidents" -b
```

出力:
```
# file: home/yoshi/homelab-ansible/reports/incidents
# owner: yoshi
# group: homelab-ansible
user::rwx
user:recovery-exec:rwx
group::r-x
mask::rwx
other::r-x
default:user::rwx
default:user:recovery-exec:rwx
default:group::r-x
default:mask::rwx
default:other::r-x
```

**事実**: `mask::rwx`。`user:recovery-exec:rwx` に `#effective:` の注記は無い(=named-userエントリの実効権限がmaskで切り詰められていない)。

**期待値との比較**: 期待どおり(`mask::rwx`、`#effective:` 注記なし)。**一致。**

### O2 — `getfacl` on `reports/incidents/_spool/`

実行コマンド:
```
ansible quory -m command -a "getfacl /home/yoshi/homelab-ansible/reports/incidents/_spool" -b
```

出力:
```
# file: home/yoshi/homelab-ansible/reports/incidents/_spool
# owner: yoshi
# group: homelab-ansible
user::rwx
user:recovery-exec:rwx	#effective:r-x
group::r-x
mask::r-x
other::r-x
default:user::rwx
default:user:recovery-exec:rwx
default:group::r-x
default:mask::rwx
default:other::r-x
```

**事実**: `mask::r-x`。`user:recovery-exec:rwx` に `#effective:r-x` の注記が付いている(named-userのrwxがmaskでr-xへ切り詰められている)。**default ACL側は `default:mask::rwx` のまま**(計画§1.2の「default ACLはこの問題に無関係」という記述と整合)。

**期待値との比較**: 期待どおり(`mask::r-x`、`user:recovery-exec:rwx #effective:r-x`)。**一致。**

### O3 — `stat` on `_spool` のctime

実行コマンド:
```
ansible quory -m command -a "stat -c '%a %n %y %z' /home/yoshi/homelab-ansible/reports/incidents/_spool" -b
```

出力:
```
755 /home/yoshi/homelab-ansible/reports/incidents/_spool 2026-07-28 05:50:21.206310425 +0900 2026-07-28 05:50:21.206310425 +0900
```

**事実**: `%a`(モードビット)= 755(mask::r-xを反映、O2と整合)。`%y`(mtime)と `%z`(ctime)がともに **2026-07-28 05:50:21.206310425 +0900**。

**期待値との比較**: 期待は「2026-07-28 05:50:20 前後(T1のspool書込時刻と一致)」。実測は05:50:21で**1秒以内の差**。**一致とみなす。**

### O4 — `_spool/1785185420-30cddc4d.json` のowner

実行コマンド:
```
ansible quory -m command -a "stat -c '%U %G %n' /home/yoshi/homelab-ansible/reports/incidents/_spool/1785185420-30cddc4d.json" -b
```

出力:
```
yoshi yoshi /home/yoshi/homelab-ansible/reports/incidents/_spool/1785185420-30cddc4d.json
```

**事実**: owner = `yoshi`、group = `yoshi`。

**期待値との比較**: 期待は owner = `yoshi`。**一致。**(ファイル自体もまだ削除されずに残っている = AC1未達の証拠でもあり、C4「生きた検証材料として温存する」の前提が現時点でも保たれている。)

### O5 — `spool-1785185420-*` バンドルの件数

実行コマンド:
```
ansible quory -m command -a "sh -c 'ls -d /home/yoshi/homelab-ansible/reports/incidents/spool-1785185420-* 2>/dev/null | wc -l'" -b
```

出力:
```
21
```

**事実**: 21件。

**期待値との比較**: 期待は「11件より増えている」。実測21件。**一致(進行中の証拠として確認できた)。** 計画C4の「11という数字を固定しない」との指示どおり、この21も暫定値として扱い、後続単位(U6)で再計数すべき値として記録する。

### O6 — `homelab-incident-capture.service` の現況

実行コマンド:
```
ansible quory -m command -a "systemctl status homelab-incident-capture.service --no-pager -l" -b
```

出力(抜粋):
```
× homelab-incident-capture.service - Homelab incident evidence bundle collector (Step 1 / R2)
     Loaded: loaded (/etc/systemd/system/homelab-incident-capture.service; static)
     Active: failed (Result: exit-code) since Tue 2026-07-28 07:35:08 JST; 1min 25s ago
    Process: 74819 ExecStart=/usr/bin/flock -n -E 75 /run/lock/homelab-incident-capture.lock /usr/bin/python3 /usr/local/sbin/incident-capture-collector.py (code=exited, status=2)
    Main PID: 74819 (code=exited, status=2)
7月 28 07:35:08 quory systemd[1]: homelab-incident-capture.service: Main process exited, code=exited, status=2/INVALIDARGUMENT
7月 28 07:35:08 quory systemd[1]: homelab-incident-capture.service: Failed with result 'exit-code'.
```

**事実**: `Active: failed`、直近の失敗は `07:35:08 JST`(観測実行時刻の約1分25秒前)。exit code = 2。`ansible` コマンド自体は `systemctl status` が非ゼロを返すため rc=3 の "FAILED" 表示になったが、これは `systemctl status` の仕様どおりの挙動であり、コマンド実行自体は成功して出力を得ている(read-onlyの範囲内)。

**期待値との比較**: 期待は「`failed` 継続」。**一致。** かつ、5分毎のtimer稼働により観測時点でも継続的に失敗し続けていることが確認できた(進行中であることの直接証拠)。

---

## 2. 因果モデルへの判定

**確認できた。** O1〜O6のすべてが計画§1の因果モデルの期待値と一致した。特に判定を分けるO1・O2がいずれも「一致」であったため、モデルを崩す/反証する材料は今回の観測では得られなかった。

判定根拠を要約する:

- O1(兄`reports/incidents/`は`mask::rwx`で正常)とO2(`_spool/`は`mask::r-x`で異常、named-userの実効権限が`#effective:r-x`へ切り詰められている)の対比は、計画§1.5「`_spool/`だけがrole外の書き手(T1)を持つために壊れる」という説明と整合する。両ディレクトリとも同じ`mode: "0755"`を持つが、兄は壊れておらず`_spool/`だけ壊れているという非対称性が現物で再現された。
- O3(ctime ≈ 05:50:21)はO2のmask崩壊と同一のタイムスタンプであり、計画§1.4の時系列表(「07-28 05:50:20 T1が初のspoolレコードを書く」と「同時にchmod 0755が発火」)と符合する。chmodによってmaskが書き換わった瞬間とディレクトリのctime更新が一致することは、「T1のディレクトリ作成タスク(`file`, `mode: "0755"`)がchmodを発火させた」という主張の直接的な裏付けになる。
- O4(owner=yoshi)は、T1の実行identity(`become: false`のquory本番実行ユーザ)がこのディレクトリに対してchmodを実行できる権限を持っていたことの傍証として機能する。owner権限があればchmodは許可されるため、「なぜT1のchmodが成功したのか」という疑問に整合的な答えを与える。
- O5(21件、11件から増加)とO6(`failed`継続、直近の失敗が観測直前)は、障害が過去の一時的事象ではなく現在進行中であることを示しており、これから行う修正(U1〜U6)の対象がまだ実在することを確認した。

**留保**: 本観測は「現在の状態が因果モデルと矛盾しないこと」を確認したものであり、「T1のchmodがmaskを壊した」という因果そのものを直接観測(例えばchmod実行の瞬間をリアルタイムでtraceする等)したわけではない。ctimeの一致(O3)は強い状況証拠だが、真の意味での実験的検証(T1を発火させてmaskがrwxからr-xへ落ちる瞬間を観測する)は計画のU5 T8/T9が担う。U0の役割(コード変更前の因果モデルの成否確認)としては十分な一致が得られた。

---

## 3. 観測できなかった項目とその理由

なし。O1〜O6のすべてを計画どおりに実行し、すべて期待値と一致した。`journalctl` や `homelab-semaphore-query` など、`-b` が必要な既知の制約に該当するコマンドは今回の観測項目(O1〜O6)には含まれておらず、使用しなかった。

---

## 4. 安全境界の遵守

- 実行したコマンドは `getfacl`、`stat`、`ls -d ... | wc -l`、`systemctl status` の4種のみ。いずれも読み取り専用。
- timer/serviceのstart/stop/restart/enable、設定変更、ファイルの作成・削除・移動、`ansible-playbook` の実行は一切行っていない。
- `git config --global safe.directory` 等の設定変更、`git commit` / `git push` は行っていない。quory作業ツリーの `git status` にも触れていない(本観測の範囲外のため実施不要と判断)。

---

## 5. 後続単位への申し送り

- U0の結論は「因果モデルは確認できた」。U1・U2(Implementer)は計画§2〜§4のとおり着手してよい状態にある(本Testerの立場からブロック理由なし)。
- O5で21件(11件から増加)を確認した。U6(後始末)の着手時点でこの件数はさらに増えている前提で、C4「11という数字を固定しない」の指示どおり再計数が必要である。
- O6で確認した直近の失敗時刻(07:35:08 JST)は、5分間隔のtimerが観測直前まで継続的に失敗し続けていることを示す。U5の実施前提(サービスは`failed`のまま)は現時点で成立している。
