# Code Review: Proxmox Patch Policy 標準構造書換

## Summary

旧版正本は `git show HEAD:docs/ai/policies/proxmox_patch_policy.md`（HEAD `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `61a38e445d6d8af4113b0f33e43213c205d2986d`、2007行）から独立取得した。005/006の要約を合格根拠にせず、旧版の許可・禁止・停止・必須・例外・判断条件を原文の規範文、箇条書き、表行単位で新版へ突合した。

初回レビューでは原文規範の欠落・条件変更を5件検出して `Request Changes` とした。再レビューでPolicy、005 ledger、006 indexへの修正を旧HEAD原文から再突合し、5件すべての解消を確認した。全90 SB、19行migration、標準8節、付録A、Context分類、scope、秘密情報、whitespaceの回帰もPASSしたため、最終verdictは `Approve` である。

## Initial Critical Issues (resolved in re-review)

| # | File | Line | Issue | Severity |
|---|---|---:|---|---|
| 1 | `docs/ai/policies/proxmox_patch_policy.md` | 99-100 | **旧L440のdry-run開始前healthcheck gateが欠落。** 旧文は「対象ノードの healthcheck が OK であることを確認する」。新版SB-023はfixed pair、metadata更新、simulation、実patch禁止だけで、dry-run入口自体のhealthcheck条件を持たない。新版L262-264は標準full flowの順序であり、単独dry-run入口の条件を代替しない。005 ledgerもSB-023の旧行をL428-435/L459だけとし、L440を収録していない。必要な修正: SB-023へ「dry-runは実行対象のpve1 / pve2両nodeのhealthcheckがOKの場合だけ開始する」を追加し、005/006のledger/index実績にも旧L440の到達を反映する。 | must-fix |
| 2 | `docs/ai/policies/proxmox_patch_policy.md` | 207-208 | **旧L995-1000のmajor upgrade判断条件が欠落。** 旧版は、Proxmox major version変化疑い、Debian suite変化疑い、repository suite変更直後、base package大量更新、install/remove大量、`pve-manager` major version変化疑いを独立条件としていた。新版SB-041は検出後の行動だけで、何を `MAJOR_UPGRADE_DETECTED` とするかを定義しない。005のSB-041も旧L991-1015を一括しながら条件6行を要約から落としており、ledger自体が不完全。必要な修正: 判断軸へ旧6条件を意味変更なく列挙し、各旧行の新版到達行をledger/indexへ記録する。 | must-fix |
| 3 | `docs/ai/policies/proxmox_patch_policy.md` | 240-244 | **Roadmap参照条件が1件欠落。** 旧L1494-1500は、`MAJOR_UPGRADE_DETECTED`、major/minor変化疑い、中核更新の広がりに加え、L1500「changelogだけでは変更の全体像が見えない場合」も参照条件としていた。新版L241は前者だけを保持し、L244は各情報源の用途だけで後者を復元しない。これは必要な公式情報確認を緩和する。必要な修正: SB-066またはSB-068へ「changelogだけでは変更の全体像が見えない場合もRoadmap / Release Notesを参照する」を追加し、旧L1500の到達行を記録する。 | must-fix |
| 4 | `docs/ai/policies/proxmox_patch_policy.md` | 379-380 | **分類CLIの実行場所制限が緩和。** 旧L1708-1719は実行場所をansy/quory/macOSに限定し、pve1、pve2、authy、Sophos Firewall VMでは実行しないとしていた。新版SB-075はProxmox hostだけを禁止し、authy/Sophos上の実行禁止と3場所のallowlistを規範から落とす。System Context L43の配置事実は非規範でありPolicyの禁止を代替できない。005のSB-075も旧L1706-1732を対象にしながらこの禁止を要約から落としている。必要な修正: Policyへ「分類CLIはansy、quory、macOSだけで実行し、pve1、pve2、authy、Sophos Firewall VMでは実行しない」を復元し、ledger/indexへ各旧箇条書きの到達を記録する。 | must-fix |
| 5 | `docs/ai/policies/proxmox_patch_policy.md` | 327-328 | **旧§20の適用条件が落ち、SB-085が厳格化。** 旧L1952は§20の全追加ルールを「Sophos Firewall VM が Proxmox 上で稼働している場合」に限定していた。新版SB-085は一般のlifecycle節で「時間帯だけpatch」「割当確認」「移動後通信確認」を無条件に読めるため、Sophos移行前にも新しい必須条件を課し得る。005 ledgerのSB-084〜086はL1952を収録していない。必要な修正: L328を「Sophos Firewall VMがProxmox上で稼働している場合は、…」で明示的に条件付けし、旧L1952をSB-084〜086共通条件としてledger/indexへ記録する。 | must-fix |

## Suggestions

なし。安全境界差異の解消以外に、今回の非ゴールを広げる提案は行わない。

## Re-review (final)

### must-fix解消確認

| # | 旧HEAD原文 | 修正版到達 | 再判定 |
|---|---|---|---|
| 1 | L440: dry-run開始前に対象nodeのhealthcheck OKを確認 | Policy L99-100、005 L120、006 L77 | **保持**。fixed pair両nodeがOKの場合だけ開始する条件を復元。 |
| 2 | L995-1000: major upgrade疑いの6判断条件 | Policy L207-217、005 L138、006 L95 | **保持**。6条件を独立箇条書きで復元し、いずれか該当のOR条件も明示。 |
| 3 | L1500: changelogだけでは全体像が見えない場合のRoadmap参照 | Policy L252-253、005 L165、006 L122 | **保持**。参照条件を復元。 |
| 4 | L1708-1719: 分類CLIの3場所allowlistと4場所denylist | Policy L388-389、005 L172、006 L129 | **保持**。ansy/quory/macOSだけを許可し、pve1/pve2/authy/Sophosを禁止。apply中の導入・更新禁止も維持。 |
| 5 | L1952: §20全ルールのSophos稼働時という共通条件 | Policy L336-337/L410-414、005 L181-183、006 L138-140 | **保持**。SB-084〜086すべてへ共通条件を復元し、SB-085の無条件化を解消。 |

### ledger/indexと全体回帰

| 観点 | 独立再計測・結果 |
|---|---|
| 90 SB本文 | SB-001〜SB-090 markerが各1件。初回逐行表の保持項目を再確認し、5修正以外の安全境界に欠落・緩和・厳格化・条件例外順序変更なし |
| 005 ledger | 90行、重複0。SB-023/041/068/075/084-086の旧行・種別・要約を補正し、§9.1.1に初回実績を改変しない補正履歴あり |
| 006 index | 90行。Policyの全marker実行番号と比較して行不一致0 |
| migration | 19行。修正後の到達行を反映し、18移動候補と旧§22維持を全件追跡 |
| Policy構造 | 430行。標準8節はL5/L18/L77/L148/L267/L339/L355/L416に各1件・順序正。付録AはL423 |
| Context | 3 Contextに非規範宣言とPolicy優先linkあり。今回修正でContext変更なし、分類・重複・矛盾の回帰なし |
| scope | playbooks/rolesのtracked/untracked差分0。他Policyのtracked diffは対象Policyだけ。修正対象はPolicy/005/006のみ |
| 秘密・実値 | 対象文書にIPv4 literal、数値付きVLAN、実VM/CT ID、password/token/secret代入形式なし |
| Markdown/link | 対象文書の表空セル0。既存のlocal Markdown link targetを維持 |
| whitespace | tracked `git diff --check` PASS。未追跡の2 Context、005、006も個別 `git diff --no-index --check` PASS |

## Initial review: 旧原文規範行の独立突合

以下は初回421行版に対する監査記録である。再レビューで変わった5件と現在行は上の「Re-review (final)」を正とする。

判定は `保持 / 欠落 / 緩和 / 厳格化 / 条件・例外・順序変更` のいずれかで記録した。旧行欄でコンマ区切りにした行は、各原文箇条書き・表行・規範文を個別に確認したことを表す。複数行を単なる範囲要約としてPASSにはしていない。

| SB | 旧原文単位 → 新版到達行 | 判定 | 所見 |
|---|---|---|---|
| SB-001 | L15→L10; L16→L11; L17→L12; L18→L13; L19→L13; L20→L14/L322; L21→L15; L22→L16 | 保持 | 目的の各必須原則を保持。 |
| SB-002 | L30→L23; L34→L23; L35→L23/L184-185; L36→L23; L37→L23/L178; L38→L23/L183; L39→L23/L177; L40→L23/L180; L41→L23; L42→L23 | 保持 | 個別componentはL175-191の重要component一覧も併用して到達。 |
| SB-003 | L46→L26 | 保持 | `のみ`、`PATCH_READY`、土曜朝自動を保持。 |
| SB-004 | L52→L29; L54→L29/L146 | 保持 | 3 Statusの自動禁止と移行先を保持。 |
| SB-005 | L58→L32; L62→L32; L63→L32; L64→L32; L65→L32 | 保持 | 通常運用での部分適用禁止を保持。 |
| SB-006 | L67→L35 | 保持 | 明示的な例外maintenanceだけという条件を保持。 |
| SB-007 | L86→L155; L87→L156; L88→L157; L89→L158; L90→L159 | 保持 | Status表5行の自動可否を保持。 |
| SB-008 | L94→L162; L96→L162; L100→L224; L101→L225; L102→L226; L103→L227 | 保持 | Urgencyを自動許可に使わない。 |
| SB-009 | L111→L165; L112→L165; L113→L165; L114→L165; L115→L165; L116→L165; L117→L165; L118→L165 | 保持 | URGENT 8条件を個別確認。 |
| SB-010 | L126→L168; L127→L168; L128→L168; L129→L168; L130→L168; L131→L168 | 保持 | HIGH候補6条件と各確認軸を保持。 |
| SB-011 | L155→L40; L156→L41; L157→L42; L158→L43 | 保持 | node順序と続行条件を保持。 |
| SB-012 | L166→L46; L168→L46 | 保持 | apply前所在確認と自動flowの退避・復帰を保持。 |
| SB-013 | L203→L49; L205→L49; L210→L49; L213→L49; L228→L49 | 保持 | tag正本、外部YAML禁止、命名、一致条件を保持。 |
| SB-014 | L232→L273; L242→L273; L243→L273; L244→L273; L246→L273; L248→L273; L250→L273 | 保持 | tagだけによるHA/non-HA/対象外分類、退避、force stop、明示relocateを保持。 |
| SB-015 | L267→L276; L268→L276; L269→L276; L270→L276/L273; L271→L276/L273; L272→L276/L273; L273→L276/L273; L274→L276 | 保持 | pve2 apply前の8条件を保持。 |
| SB-016 | L280→L279; L281→L279; L282→L279; L283→L279 | 保持 | pve1 apply前の4条件を保持。 |
| SB-017 | L287→L282; L289→L267/L282; L293→L282; L294→L282; L295→L282 | 保持 | restore順と最終3条件を保持。 |
| SB-018 | L299→L52 | 保持 | migration許可範囲はPATCH_READY flow内だけ。 |
| SB-019 | L305→L55; L308→L55; L315→L55; L316→L55; L318→L55; L320→L55 | 保持 | 2変数、true/false、失敗停止、非除外、HA例外を保持。 |
| SB-020 | L326→L82; L329→L82; L333→L86; L334→L87; L335→L88; L336→L89; L344→L86; L345→L87; L346→L88; L347→L89; L348→L89; L349→L88; L350→L89 | 保持 | 4分類と全入口の許可範囲を保持。 |
| SB-021 | L370→L94; L398→L94 | 保持 | 単一node limit許可とWARNING/CRITICAL apply禁止を保持。 |
| SB-022 | L408→L97; L409→L97; L410→L97; L411→L97; L412→L97; L413→L97; L414→L97 | 保持 | healthcheck失敗7条件を個別確認。 |
| SB-023 | L428→L100; L434→L100; L435→L100; L459→L100 | 保持 | ledger収録分は保持。ただし旧L440はledger外かつ欠落（must-fix #1）。 |
| SB-024 | L470→L235; L1480→L374; L1482→L374 | 保持 | AIは入力・補助に限定。 |
| SB-025 | L482→L105; L483→L106; L484→L107; L485→L108; L486→L109; L487→L110 | 保持 | Status決定順6分岐を保持。 |
| SB-026 | L520→L115; L521→L115; L522→L115/L118; L548→L115; L549→L115; L550→L115; L551→L115 | 保持 | 両node health、node制限、2停止条件を保持。 |
| SB-027 | L566→L123; L570→L132; L582→L126; L583→L126; L584→L126; L585→L126; L586→L126/L132; L587→L126; L588→L123; L598→L123; L599→L123; L600→L126 | 保持 | 単一node、2許可Status、明示確認、禁止Statusを保持。 |
| SB-028 | L582→L126; L583→L126; L584→L126; L585→L126; L586→L126; L587→L126; L596→L126; L599→L123; L600→L126 | 保持 | AND条件とStatus停止を保持。 |
| SB-029 | L625→L285; L626→L285; L628→L285; L629→L285; L631→L285 | 保持 | reboot済みかつCRITICAL/UNKNOWNだけretry、非rebootはretry不可。 |
| SB-030 | L662→L238; L663→L238 | 保持 | OK復帰と全CRITICAL時の結果を保持。 |
| SB-031 | L692→L129; L693→L129; L694→L129; L695→L129; L696→L129 | 保持 | apply単体の5禁止を保持。 |
| SB-032 | L712→L137/L140; L730→L137; L731→L137; L732→L137; L733→L137; L734→L137; L735→L137 | 保持 | 全実行条件、pve2先行、controller既定と明示overrideを保持。 |
| SB-033 | L747→L140; L751→L140; L755→L140; L759→L140; L767→L140; L768→L140; L769→L140; L770→L140; L771→L140; L772→L140; L773→L140; L774→L140 | 保持 | 各gate失敗とpve2 NG時の停止を保持。 |
| SB-034 | L789→L143; L793→L143; L794→L143; L795→L143; L822→L143; L823→L143; L824→L143; L825→L143 | 保持 | home tag対象と4停止条件を保持。 |
| SB-035 | L833→L146; L837→L146; L840→L146; L843→L146; L846→L146 | 保持 | 3非通常Statusの移行先と自動禁止を保持。 |
| SB-036 | L856→L175; L857→L176; L858→L177; L859→L178; L860→L179; L861→L180; L862→L181; L863→L182; L864→L183; L865→L184; L866→L185; L867→L186; L868→L187; L869→L188; L870→L189; L871→L190; L872→L191; L880→L193; L883→L193; L886→L193 | 保持 | 重要component全項目と3分類を保持。 |
| SB-037 | L897→L196; L901→L196; L902→L196; L903→L196 | 保持 | NO_UPDATESの通知、非apply、reportを保持。 |
| SB-038 | L911→L199; L912→L199; L913→L199; L914→L199; L915→L199; L916→L199; L922→L199; L927→L199; L928→L199; L929→L199; L930→L199 | 保持 | 6条件のAND、pve2先行、OK時だけpve1、NG停止通知を保持。 |
| SB-039 | L938→L202; L939→L202/L213; L940→L193/L213; L941→L213; L942→L213; L948→L202; L949→L202; L954→L202; L955→L202; L956→L202; L957→L202; L958→L202; L959→L230/L294; L960→L202/L294 | 保持 | 条件、非自動・非部分、無期限再評価、人間判断を保持。 |
| SB-040 | L968→L216; L969→L216; L970→L216; L971→L216; L972→L216; L978→L205/L299; L983→L205/L299; L984→L205; L985→L205/L299; L986→L205; L987→L205/L314 | 保持 | BLOCKED条件と禁止・復帰gateを保持。 |
| SB-041 | L995→欠落; L996→欠落; L997→欠落; L998→欠落; L999→欠落; L1000→欠落; L1010→L208; L1011→L208; L1012→L208; L1013→L208; L1014→L208; L1015→L208 | 欠落 | 検出後の行動は保持したが判断条件6行が欠落（must-fix #2）。 |
| SB-042 | L1023→L213; L1024→L213; L1030→L213; L1031→L213; L1032→L213; L1033→L213; L1035→L213 | 保持 | 即BLOCKEDにせず4条件ANDでmaintenance、人間判断を保持。 |
| SB-043 | L1041→L216; L1042→L216; L1043→L216; L1044→L216; L1045→L216 | 保持 | BLOCKED 5条件を個別確認。 |
| SB-044 | L1051→L162/L221; L1052→L162; L1054→L221; L1057→L221; L1058→L221; L1059→L221; L1060→L221; L1061→L221 | 保持 | Status分離と複数材料を保持。 |
| SB-045 | L1065→L224; L1069→L224; L1070→L224; L1071→L224; L1072→L224; L1076→L225; L1080→L225; L1081→L225; L1082→L225; L1083→L225; L1087→L226; L1091→L226; L1092→L226; L1093→L226; L1094→L226; L1095→L226; L1110→L227; L1114→L227; L1115→L227; L1116→L227; L1117→L227; L1118→L227 | 保持 | LOW/NORMAL/HIGH/URGENTの条件・例を個別確認。 |
| SB-046 | L1120→L230; L1121→L230; L1123→L230 | 保持 | 過剰昇格禁止と非許可Statusの自動禁止を保持。 |
| SB-047 | L1137→L60; L1138→L60; L1139→L60; L1141→L60; L1144-1164→L262-268 | 保持 | cluster外かつreboot非影響の場合だけfull flowを許可。 |
| SB-048 | L1171→L63; L1172→L63; L1174→L63; L1176→L63; L1182→L63; L1183→L63; L1186→L63; L1187→L63; L1190→L63; L1191→L63 | 保持 | cluster内control nodeの単一node制限と自己migration禁止を保持。 |
| SB-049 | L1288→L288; L1297→L288; L1301→L288; L1302→L288 | 保持 | NO_UPDATES時非applyと片node手動済みのMode別例外を保持。 |
| SB-050 | L1308→L351 | 保持 | apply失敗時は次nodeへ進まない。 |
| SB-051 | L1309→L354 | 保持 | SSH/API/GUI未復帰時停止。 |
| SB-052 | L1310→L357 | 保持 | WARNING/CRITICAL時停止。 |
| SB-053 | L1311→L360; L1312→L360; L1313→L360 | 保持 | apt/dpkg、systemd、cluster/corosync/ZFS/replicationの全条件を保持。 |
| SB-054 | L1314→L363; L1315→L363; L1316→L363 | 保持 | 退避・復帰・稼働影響の3条件を保持。 |
| SB-055 | L1317→L366 | 保持 | target上control nodeで継続不能なら停止。 |
| SB-056 | L1319→L333 | 保持 | 理由通知と週末対応を保持。 |
| SB-057 | L1323→L291; L1332→L291; L1333→L291; L1334→L291; L1335→L291; L1336→L291 | 保持 | 自動reboot、復帰待ち、post-check、OKだけ続行、NG停止を保持。 |
| SB-058 | L1342→L294; L1344→L294; L1346→L202; L1348→L294; L1350→L294 | 保持 | 非自動・非部分・無期限再評価・高Urgency時も人間判断。 |
| SB-059 | L1352→L369 | 保持 | 規定形式の明示確認必須、不在時停止を保持。 |
| SB-060 | L1358→L299; L1360→L299; L1361→L205; L1365→L299; L1366→L299; L1367→L299; L1368→L299; L1369→L299; L1370→L299 | 保持 | timer/playbook/両node禁止とSophos状態別保護を保持。 |
| SB-061 | L1378→L302; L1379→L302; L1380→L302; L1381→L302 | 保持 | simulation失敗routeと復帰Statusまでのapply禁止を保持。 |
| SB-062 | L1385→L305; L1386→L305; L1387→L305 | 保持 | 置換なし重要removeの非適用と復帰条件を保持。 |
| SB-063 | L1391→L308; L1392→L308; L1393→L308 | 保持 | apt/dpkg修復とcheck成功までの禁止を保持。 |
| SB-064 | L1397→L311; L1398→L311; L1399→L311; L1400→L311; L1401→L311 | 保持 | major疑い時の停止、別計画、pve2検証、pve1除外を保持。 |
| SB-065 | L1407→L314; L1408→L314; L1409→L314; L1410→L314; L1411→L314; L1412→L314 | 保持 | 復帰6条件のANDを保持。 |
| SB-066 | L1420→L241; L1422→L241; L1438→L241/L344; L1439→L241/L344; L1440→L241; L1441→L241; L1442→L241/L247; L1443→L241/L253 | 保持 | ledger収録分を保持。Roadmapの追加条件L1500はSB-068側で欠落。 |
| SB-067 | L1480→L374; L1482→L374 | 保持 | AIは最終入力のみで実行・解除・apply判断禁止。 |
| SB-068 | L1490→L244; L1491→L244; L1492→L244; L1496→L208/L244; L1497→L241; L1498→L241; L1499→L241; L1500→欠落; L1512→L244; L1513→L244; L1525→L244; L1537→L244 | 緩和 | L1500のRoadmap参照条件が欠落（must-fix #3）。 |
| SB-069 | L1551→L336; L1552→L336; L1553→L336; L1554→L336; L1555→L336; L1556→L336 | 保持 | 全通知Statusと強度を保持。 |
| SB-070 | L1572→L339; L1573→L339; L1574→L339; L1575→L339; L1576→L339; L1577→L339; L1578→L339; L1584→L340; L1585→L340; L1586→L340; L1587→L340; L1588→L340; L1594→L341; L1595→L341; L1596→L341; L1597→L341; L1598→L341; L1599→L341; L1600→L341; L1601→L341; L1602→L341; L1608→L342; L1609→L342; L1610→L342; L1611→L342; L1612→L342; L1613→L342 | 保持 | 4種通知の必須項目を全件確認。 |
| SB-071 | L1625→L247; L1626→L247; L1627→L247; L1628→L247; L1629→L247/L250; L1630→L247; L1632→L247; L1637→L247; L1638→L247; L1639→L247 | 保持 | AIは分類・説明補助で実行・最終判断者ではない。 |
| SB-072 | L1667→L250; L1669→L250 | 保持 | AI候補、Ansible最終確定を保持。 |
| SB-073 | L1675→L377; L1676→L377; L1677→L377; L1678→L377; L1679→L377; L1680→L377; L1681→L377; L1682→L377; L1683→L377; L1684→L377 | 保持 | AIへの10禁止を個別確認。 |
| SB-074 | L1692→L253; L1693→L253; L1694→L253; L1695→L253; L1696→L253; L1697→L253; L1698→L253; L1699→L253; L1700→L253; L1701→L253; L1702→L253; L1703→L253; L1704→L253 | 保持 | 収集・分類・最終判定・apply責務を全件確認。 |
| SB-075 | L1708→System L43（非規範）; L1710→System L43（非規範）; L1711→System L43（非規範）; L1712→System L43（非規範）; L1716→L380; L1717→L380; L1718→欠落; L1719→欠落; L1729→L380; L1730→L380 | 緩和 | allowlistがPolicyから消え、authy/Sophos禁止が欠落（must-fix #4）。 |
| SB-076 | L1736→L66 | 保持 | PATCH_READY自動時のtarget上control node禁止。 |
| SB-077 | L1746→L75; L1750→L63/L69; L1751→L60/L72/L75; L1753→L69/L75; L1755→L75; L1759→L69; L1763→L63; L1766→L63; L1769→L63/L69 | 保持 | Ansible実行端末、管理対象自身禁止、cluster内full禁止、単一node範囲を保持。 |
| SB-078 | L1773→System L44/L45; L1780→L72; L1783→L72 | 保持 | cluster外・reboot非影響の場合だけfull flow可。 |
| SB-079 | L1787→L383; L1789→L383 | 保持 | 指定重点箇所。apply停止とfull flow禁止を同条件・同順序で保持。 |
| SB-080 | L1809→L319; L1812→L319; L1813→L319; L1814→L319; L1815→L319; L1817→L319; L1818→L319; L1820→L319; L1821→L319; L1822→L319; L1823→L319; L1825→L319; L1826→L319; L1835→L319; L1836→L319; L1837→L319; L1838→L319; L1839→L319; L1840→L319; L1841→L319; L1842→L319; L1844→L319; L1848→L319; L1853→L319; L1854→L319; L1855→L319; L1856→L319; L1857→L319; L1858→L319; L1859→L319; L1861→L319; L1862→L319; L1863→L319; L1871→L319; L1872→L319; L1873→L319; L1874→L319; L1875→L319; L1876→L319; L1877→L319; L1878→L319; L1879→L319; L1882→L319 | 保持 | Mode A/B/maintenanceのcontrol、health、Status、退避、確認、post-check、pve2先行gateを個別確認。逐次手順はOperations Context L5-40へ非規範移動。 |
| SB-081 | L1891→L322; L1892→L322 | 保持 | 指定重点箇所。rollback原則禁止と再インストールを保持。 |
| SB-082 | L1897→L325/Operations L66; L1898→L325/Operations L66; L1899→Operations L66; L1900→Operations L66; L1904→Operations L67; L1905→Operations L67; L1906→L325; L1910→L325; L1914→Operations L71; L1915→Operations L72; L1916→Operations L72; L1917→Operations L73; L1918→Operations L73; L1919→Operations L74; L1920→Operations L74; L1921→Operations L75; L1922→Operations L75; L1923→Operations L76; L1924→Operations L77; L1925→Operations L78; L1926→Operations L79; L1927→Operations L80; L1928→Operations L81; L1929→Operations L82 | 保持 | 再構築義務をPolicyに残し、具体情報をOperationsへ移動。実値は転載なし。 |
| SB-083 | L1935→L388; L1937→L390; L1938→L391; L1939→L392; L1940→L393; L1941→L394; L1942→L395; L1943→L396; L1944→L397; L1945→L398; L1946→L399 | 保持 | 指定重点箇所。全10条件と「すべて」を保持。 |
| SB-084 | L1954→L402; L1955→L402 | 保持 | 直接patch禁止と先行移動可否確認を保持。ただし共通条件L1952はledger外（must-fix #5）。 |
| SB-085 | L1956→L328; L1957→L328; L1958→L328 | 条件・例外・順序変更 | 時間帯、必要なinterface/segment、移動後通信確認自体は保持。旧L1952の適用条件欠落により適用範囲が広がる（must-fix #5）。 |
| SB-086 | L1959→L405; L1960→L405 | 保持 | 慎重扱いとHIGH/URGENT早期判断を保持。ただし共通条件L1952はledger外（must-fix #5）。 |
| SB-087 | L503→L118; L522→L118 | 保持 | target allowlist、反対側自動決定、外部指定禁止を保持。 |
| SB-088 | L570→L132; L601→L132 | 保持 | pve1/pve2単一nodeとrunning guest不在確認を保持。 |
| SB-089 | L612→L256; L613→L256; L615→L256; L616→L256; L617→L256; L618→L256; L1325→L256; L1326→L256; L1328→L256 | 保持 | dry-run推定/apply後事実と2系統のreboot判定を保持。 |
| SB-090 | L1746→L75; L1750→L75; L1751→L75; L1753→L75; L1755→L75 | 保持 | Ansible端末2種、管理対象host禁止、weekly full preflight拒否を保持。 |

### Initial ledger外規範の逆検索結果

以下の初回差異はすべて「Re-review (final)」の到達行へ復元済みである。

| 旧行 | 原文規範 | 新版到達 | 判定 |
|---:|---|---|---|
| L440 | dry-run開始時に対象nodeのhealthcheck OKを確認する | なし。L262-264は標準full flowだけ | 欠落（must-fix #1） |
| L995-1000 | major upgrade疑いの6判断条件 | なし | 欠落（must-fix #2、SB-041 ledger不完全） |
| L1500 | changelogだけでは全体像が見えない場合のRoadmap参照 | なし | 欠落（must-fix #3、SB-068 ledger不完全） |
| L1708-1719 | 分類CLIの3場所allowlistと4場所denylist | PolicyにはProxmox host禁止だけ | 緩和（must-fix #4、SB-075 ledger不完全） |
| L1952 | §20全追加ルールの「SophosがProxmox上で稼働時」条件 | なし | 厳格化（must-fix #5、SB-084〜086 ledger不完全） |

## migration 19行・Context境界の確認

| 観点 | 結果 |
|---|---|
| migration実測 | 006の追跡表は19行。旧§4、§5.2、§6.2-6.7、§6.5、§11.2、§11.3-11.4、§14.2-14.3、§16.1-16.3、§16.5、§16.6-16.7、§16.8.0-16.8.2、§16.9、§17、§18、§19、§20、§21、§22の全行に移動先またはPolicy核がある。安全境界差異は上記must-fixを除く。 |
| System Context | L3で非規範・Policy優先を明記。node役割とCLI/control nodeの環境事実に限定し、既存のnode順序記述を重複追加していない。 |
| Repository Context | L3で非規範・Policy優先・単一taskはcode正本を明記。複数入口、role間data flow、分類CLI契約、reportの横断地図であり、単一taskの逐語複製を避けている。 |
| Operations Context | L3で非規範・Policy優先・本書だけでapplyしないことを明記。Mode、retry、evacuation/restore、再構築、Sophos確認順を収容し、新しい許可・例外を作っていない。 |
| 重複・矛盾 | 3 ContextはいずれもPolicyへの正しい相対linkを持つ。Policyと競合する規範宣言なし。Repository/Operations/Systemの分類は `context-classification.md` に適合。 |
| 付録A | 旧§22の6参照をL416-421に維持。標準8節とは別の非規範出典付録で、必須移動扱いにしていない。 |

## 独立機械検査

| 検査 | 独立実測 |
|---|---|
| 旧HEAD正本 | commit `ceb1dd7c25a3aa8e8472c993d8fd5d586de31f79`、blob `61a38e445d6d8af4113b0f33e43213c205d2986d`、2007行 |
| 標準節 | 初回8件。最終再計測はL5, L18, L77, L148, L267, L339, L355, L416の順で各1回。付録AはL423に1件 |
| migration | 19行 |
| SB marker | 90件、SB-001〜SB-090各1回、欠番・重複なし |
| 006 SB index | 90行 |
| Markdown表 | 対象5ファイルで空セル0 |
| Context宣言 | 3 Contextすべてに非規範宣言とPolicy linkあり |
| local link | Policy、3 Context、005/006内で参照するRepository内Markdown targetの存在を確認 |
| scope | `git diff --name-only -- playbooks roles` と同pathの未追跡fileは0。他Policyのtracked diffは対象Policyだけ。指定外の既存worktree変更は編集していない |
| 秘密・実値 | 対象5ファイルにIPv4 literal、数値付きVLAN、実VM/CT ID、password/token/secret代入形式なし。公開済みhost名と変数名だけ |
| whitespace | tracked `git diff --check` PASS。未追跡のRepository Context、Operations Context、005、006、007は個別 `git diff --no-index --check` PASS |
| 実行 | 文書再構成のためAnsible・実機実行なし |

## What Looks Good

- Policyは標準8節を正しい順序・一意性で持ち、旧§22を付録Aとして維持している。
- 指定重点の旧§11.6は9停止条件と通知を新版L359-378/L341-342へ保持した。
- 旧§13はImmediate actions、4 route、6復帰条件を新版L307-323へ保持した。
- 旧§16.8.3はapply停止とfull flow禁止を新版L391-392へ保持した。
- 旧§18.1はrollback原則禁止と再インストールを新版L330-334へ保持した。
- 旧§19の10前提は「すべて」を含め新版L396-409へ保持した。
- Contextは非規範でPolicy優先を明記し、コード、runbook、環境事実の分類が明瞭である。
- playbooks/roles/他Policyの意味的変更や、秘密・禁止実値の追加はない。

## Verdict

**Approve**

初回must-fix 5件は同じ旧HEAD正本から再照合して全件解消した。全90 SB、19行migration、標準構造、Context境界、scope、秘密情報、whitespaceの回帰に新たな差異はない。
