# tmux freeze / agmsg launcher 調査記録（2026-07-22）

- 記録日: 2026-07-22
- 担当Role: `techlead2`
- 対象: ansy上のCodex monitor、agmsg launcher、共有app-server、tmux応答不良
- 状態: agmsg updateと全Codexペイン再起動後のbaseline採取済み。原因は単一要因へ確定せず、工程要因・リソース要因・リモート接続相関を分けて継続観察する。

## 結論

2026-07-22のtmux応答不良時には、`codex-bridge-launcher.sh`名のプロセスが瞬間的に90〜114件観測され、2コア環境でload averageが32前後まで上昇していた。当初はdispatcher世代交代による永続role childの蓄積を主因候補としたが、追加観測により大量部分は、7個のrole childが0.3秒周期で実行するpipeline・command substitutionの短命subshellである可能性が高いと判明した。dispatcher世代とrole child寿命の不一致による孤児化はコード上の二次的リスクとして残るが、今回の90〜114件をそのまま永続リーク数と解釈しない。

agmsg updateと全7 Codexペインの再起動・復旧後、2026-07-22 21:41 JSTの安定側snapshotではlauncher名プロセス9、`bridge.js` 7、load average 7.01 / 8.97 / 17.06まで低下した。launcher 9件の安定構成はdispatcher 1、role child 7、採取瞬間の短命subshell 1と整合する。ただし、後者の内訳は同snapshotでPID・PPID・starttimeを再分類した実測ではなく、総数と現行設計からの推定である。

Phase 7 Process Incidentで指摘した3 Roleの重複調査、完全直列フロー、中間成果物とpollingの過多は、同等規模案件の相対比較で約2時間15分から約20分へ短縮されたことから、工程上の要因として引き続き有効である。一方、両計測はlauncher負荷が存在した同じ環境上で行われたため、絶対時間にはリソース逼迫による水増しが含まれ得る。Process Incidentは工程要因だけでなく、agmsg launcher由来のリソース要因との複合要因として再解釈する。

macOS / iPhoneからのリモート接続は2026-07-22 21:34 JSTに全て切断された。切断後にload averageは低下したが、再起動後の時間経過でも説明できるため、この1点だけではリモート切断の寄与を分離できない。リモート接続を直接原因とは確定せず、今後の再発有無と接続状態を対応付けて観察する。

## agmsg versionと対象component

update後のsource clone `/home/yoshi/agmsg` はcleanな`main`で、HEADは`3f87d60324b9f2a0fc66b5426798e3708dd5496f`。installed copyの`VERSION`は`v1.1.10-1-g3f87d60`である。対象ファイルはinstalled copyとsource cloneでSHA-256が一致した。

| component | path（`/home/yoshi/.agents/skills/agmsg/`からの相対） | 最終変更commit | installed SHA-256 |
|---|---|---|---|
| Codex monitor launcher | `scripts/drivers/types/codex/codex-monitor.sh` | `2f947650189d7d27d77fe00612abcbad0b4bf3c8` | `4a34545b3795ef489fff9611ac13cc3294a4d9bb470589ebe5dec5bc4b3e0558` |
| SessionStart driver | `scripts/drivers/types/codex/_session-start.sh` | `89be0221d7fe07bf24d81091ca30590505fb78e7` | `eb940ff741127661aeb702b9b6c5f58aeb331a322562c3290464d8fd72a9fa60` |
| bridge launcher | `scripts/drivers/types/codex/codex-bridge-launcher.sh` | `89be0221d7fe07bf24d81091ca30590505fb78e7` | `522dc4e090553c4d66e3661cf8669d3a50cf264f7488b6138e130df0cc26d56b` |
| storage helper | `scripts/lib/storage.sh` | `89be0221d7fe07bf24d81091ca30590505fb78e7` | `f22f4977c7cb7f7d4c37ea60f3e34559dcb95f9b68ae7737c6d6f5498ffa32ca` |

ここで「最終変更commit」は各pathに対する`git log -1`の結果であり、package全体のHEADとは別である。`codex-shim.sh`の最終変更commitは`684401239e632178b1318b40393d06f5198766ca`だが、本表のlauncherは調査対象となった`codex-monitor.sh`を指す。

## 時系列

時刻はJSTで記載する。UTCのagmsg時刻はJSTへ+9時間している。

1. 調査開始時、launcher名プロセス約90件に対しbridge実体は7件だった。追加snapshotではlauncher名が109〜101件の間で短時間に増減し、role別launcherの親子chain、`anon_pipe_read`、zombieも観測された。
2. 初期仮説は、dispatcher世代交代ごとに7 role childが再生成され、共有app-serverを寿命として持つ旧childが残る「約12世代×7 role」の永続supervisorリークだった。コード上、dispatcherの`known_pairs`はprocess-localで、role childに専用lockがなく、childがdispatcherではなく共有app-serverの寿命に結び付く構造は確認できた。
3. 21:18〜21:23頃の追加観測で、launcher名の大半は`etimes=0`で激しく増減し、同一roleのlauncher親子も短命だった。Bashのpipeline・command substitutionは親scriptと同じargvを持つsubshellを生成するため、argvだけの件数を永続child数と数えた初期解釈を撤回した。
4. 主仮説を、dispatcher 1とrole child約7がそれぞれ0.3秒周期で全identity・role-session・SQLite・`awk`・`sort`等を反復するfork stormへ変更した。2コア、load average 32.28 / 32.62 / 29.45、task 862という逼迫と整合する。role child孤児化は、今回の大量件数の確定原因ではなく二次的な設計リスクとして分離した。
5. 同時に、source clone `/home/yoshi/agmsg` が2026-06-29のcommitで止まり、`origin/main`より98 commit遅れていたことが判明した。runtimeのinstalled copyはsource cloneより新しかったため、古いcloneへ修正を直書きせず、source同期を先に行う方針へ切り替えた。
6. 21:23 JST、`origin/main`の`3f87d60`までsourceを同期し、`install.sh --update`を完了した。installed versionは`v1.1.10-1-g3f87d60`となった。ただし稼働中processは再起動まで旧processのままで、直後もlauncher 43、load average 33.42だった。updateだけの効果と再起動・process整理の効果は切り分けられていない。
7. Yoshinobu承認後、7 identityのgraceful despawnを試みたがlive actas lockがなく登録だけがclearされた。force despawnもplacement recordがなく失敗した。対象ペインがagmsg `spawn.sh`ではなく`new-session.sh`の直接tmux起動で作られていたためである。再join後、7ペインを`tmux respawn-pane`のkill optionで同時強制再起動した。
8. 再起動事故として、全7ペインがremote app serverへ接続できず起動に失敗した。共有app-server（旧PID 7635）がreviewerペイン配下のchild processであり、そのペイン停止に巻き込まれて停止したためだった。
9. reviewerペインを`codex /agmsg actas reviewer`相当で先に手動起動し、新しい共有app-server（PID 3192951）を生成した。その後、残り6ペインを順次手動起動して復旧した。全7ペインの復旧完了は21:32 JST台と推定される。
10. 全ペイン同時respawn直後はlauncher 114、load average 32.36だったが、20秒後はlauncher 30・load 9.77、40秒後はlauncher 8・load 11.19へ収束した。21:41 JSTにはlauncher 9、bridge 7、load average 7.01 / 8.97 / 17.06で、1分・5分平均は事故時より大幅に低下し、15分平均は過去負荷を残しつつ下降中だった。
11. Yoshinobuは21:34 JSTにmacOS / iPhoneからのリモート接続を全て切断した。これは「外出中のリモートCodex操作時にtmux全体が固まる」という相関仮説の基準点であるが、切断前後の1系列だけでは再起動後の自然収束と寄与を分離できない。

## update・再起動後baseline

baselineの主値は、sandbox外のhost processを観測できる`claude`が2026-07-22 21:41 JSTに採取し、agmsgで`techlead2`へ返した値である。`techlead2`からsandbox外`ps`の承認は得られなかったため再試行せず、sandbox内だけを見た無効な`ps`結果は採用していない。

| 項目 | baseline |
|---|---:|
| installed VERSION | `v1.1.10-1-g3f87d60` |
| package source HEAD | `3f87d60324b9f2a0fc66b5426798e3708dd5496f` |
| launcher名process総数 | 9 |
| dispatcher | 1（現行設計と総数からの推定。snapshotでのPPID再分類は未実施） |
| 永続role child | 7（登録済み7 Codex identityと現行設計からの推定。snapshotでのstarttime再分類は未実施） |
| 短命launcher subshell | 1（総数9との差分としての推定） |
| `codex-bridge.js` | 7（実測） |
| 共有app-server | PID 3192951、約11.6分継続時点で安定（transient fact） |
| load average | 7.01 / 8.97 / 17.06（1 / 5 / 15分） |
| リモート接続 | macOS / iPhoneとも切断済み。切断基準点は21:34 JST |

このbaselineは「正常性を証明した値」ではなく、update・再起動・復旧後に得た比較基準である。特にlauncher内部の0.3秒pollingが解消したとは確認していない。再発時は総数だけでなく、永続processと短命subshellを分けて比較する。

## 複合要因としての再解釈

| 要因 | 現時点の判断 |
|---|---|
| 3 Roleの重複調査、完全直列フロー、中間成果物・polling過多 | Process Incidentの工程要因として維持する。軽量レーンで相対時間が短縮した事実と整合する。 |
| role childごとの0.3秒global fingerprint再計算 | 2コア環境のfork stormとload上昇を説明する有力なリソース要因。恒久修正の有無は本記録のscope外。 |
| dispatcher世代交代による永続child孤児化 | コード上成立する二次的リスク。ただし今回観測した90〜114件の主成分とする初期仮説は撤回した。 |
| stale thread / app-server pin | 状態管理上は関連するが、非-launcher経路の誤bind問題であり、今回のprocess増加とは直接根因を分ける。 |
| source cloneの98 commit遅延 | 正しい調査・修正baseを妨げた要因。runtime installed copyが直ちに同じ古さだったという意味ではない。 |
| macOS / iPhoneリモート接続 | 症状との相関仮説は残る。21:34 JST切断後の1系列だけでは因果未確定。 |
| update、全Codex再起動、時間経過、リモート切断 | ほぼ同じ時間帯に重なったため、それぞれのload低下への寄与は現記録から分離できない。 |

したがって、依頼Bの2時間15分とTODO 2-2 / 2-3の約20分は、同じ高負荷要因を含む環境同士の相対比較として扱う。委任Skillによる工程削減効果は維持する一方、約20分をclean環境の絶対baselineとはしない。次の同等案件では、本書のprocess・load・リモート接続条件を併記して再baselineする。

## 今後tmuxフリーズが再発したら確認すべきこと

- [ ] 発生時刻をJSTとUTCで記録し、直前の操作と復旧操作を分けて残す。
- [ ] macOS / iPhone等のリモート接続有無、接続・切断時刻、接続元を記録する。
- [ ] installed `VERSION`、source HEAD、対象componentのhashが本書のbaselineと一致するか確認する。
- [ ] 共有app-serverのPID・starttime・親ペインを確認し、単一ペイン停止が全Codexへ波及する配置か確認する。
- [ ] launcherをargv件数だけで数えず、PID・PPID・starttime・`etimes`を使ってdispatcher、永続role child、短命subshellへ分類する。
- [ ] dispatcherが1、永続role childが登録identity数、bridgeがrole数へ収束するか、間隔を空けた複数snapshotで確認する。
- [ ] 同一roleの永続childが複数世代残っているか、短命subshellだけがburstしているかを区別する。
- [ ] load average、CPU数、task数、memory / swapを同時刻に記録し、process burstとの時間関係を確認する。
- [ ] SessionStart、role-session更新、request変更、app-server再生成と、全role一斉rebindの時刻を対応付ける。
- [ ] リモート接続なしでも再発するか確認する。再発すればagmsg側の残存要因を疑う材料とし、接続時だけ再発するなら相関仮説の裏付けを強める。ただし単発で因果確定しない。
- [ ] 証拠採取前に広域`pkill`、tmux全体停止、DB / team dataの直接編集、run stateの一括削除を行わない。
- [ ] 再起動が必要なら、共有app-serverのownerと起動順を確認し、7ペイン同時killを避けてapp-server確立後にroleを順次復旧する。
- [ ] 同等規模案件の所要時間を比較するときは、version、再起動済みか、load、リモート接続状態、委任Tierを同じ記録へ含める。

## 関連記録

- `docs/ai/reviews/agent_skills_reorganization_phase7_process_incident_lightweight_lane.md`
- `docs/ai/reviews/agent_skills_reorganization_phase4_delegation_skill_draft.md`
- `docs/ai/reviews/agent_skills_reorganization_phase0_current_state.md`

本作業は記録作成だけであり、agmsg source / installed copy、live process、DB / team data、tmux構成を変更していない。commit / pushも行っていない。
