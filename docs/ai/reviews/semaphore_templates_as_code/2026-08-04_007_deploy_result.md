# 適用結果(Step 1、本番 quory)

日付: 2026-08-04
実行: Yoshinobu(Semaphore、task #561 / #563 / #564)
確認: Coordinator(`ssh quory-investigate` の read-only クエリ)

## 経過

| task | 実行 | 結果 |
|---|---|---|
| #561 | `--check` | **失敗**。TLS証明書検証で停止。**書き込みは1件も発行されていない**(最初のGETで停止) |
| #563 | 適用 | 成功。新規9件・更新34件 |
| #564 | `--check`(適用後) | 成功。`new=0 / changed=0 / unchanged=43 / orphans=1` |

## #561 の停止理由 — role の不具合ではない

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
CA cert does not include key usage extension (_ssl.c:1081)
```

**この環境のroot CAがKeyUsage拡張を持たず、Pythonの`ssl`モジュールがCA証明書として受け付けない。** `curl` は同じ証明書で通る(検証の厳格さが違う)。2026-08-04にTesterがansyで踏んだものと同一で、quoryにも同じCAが配られている以上、必然だった。

**この事実はこのroleに固有ではない。** Ansibleの `uri` モジュールで内部HTTPSサービスを叩く経路すべてに効く。恒久対応はCAの作り直し(全証明書の再発行と信頼ストアの再配布)であり、別案件。`docs/ai/status.md` に起票した。

**当面の回避**は、ブートストラップ用テンプレートのsurvey既定値として、

- `semaphore_templates_api_base_url` = `https://localhost:3000/api`
- `semaphore_templates_api_validate_certs` = `false`

を置く形にした。**検証を切るだけでなく接続先をループバックへ寄せている**のが要点で、切った検証が守っていたもの(経路上でのtoken奪取)を、経路の性質(ホストから出ない・DNSに依存しない)で置き換えている。内部DNSはsophos-fw自身であり、`quory.internal` を引く形のまま検証を切ると、DNSを取られた場合にAPI tokenを奪える経路が残る。

**roleの既定値は `validate_certs: true` のまま変更していない。**

## 受入条件の実データでの充足

| AC | 判定 | 根拠 |
|---|---|---|
| AC1 冪等 | **PASS** | #564 で `new=0 / changed=0`。**API書き込みが0件**であることで判定した(Ansibleの`changed`はレポート書き込みで必ず立つため、そちらでは判定しない) |
| AC2 `--check`で差分のみ | **PASS** | #561・#564 とも書き込み無し。#561 は失敗時ですら書き込みへ進んでいない |
| AC3 名前のレンダリング | **PASS** | 29件の名前が定義から描画された値へ変わった。`UNSAFE:` の表記ゆれも解消 |
| **AC4 改名でid保持** | **PASS** | 適用前の34 id(1-12, 14-17, 19-36)が**1つも消えず**、同じidのまま名前が変わった。新規は38-46。**ジョブ履歴とscheduleの`template_id`結合が保たれた** |
| AC5 削除しない | **PASS** | 定義外の `id=37`(ブートストラップ)が残存し、orphanとして報告のみ |
| AC6 token欠如で停止 | **PASS**(検証済み) | ansyでTesterが実証(`2026-08-04_005_test_result.md`)。本番では踏んでいない |
| AC7 setup系12本にボタン | **PASS** | 新規9 + 既存3。`arguments` は全12本で空 |
| AC8 秘密が残らない | **PASS** | #561 の失敗出力を確認したが、tokenは現れていない。`no_log` と rescue の伏せ字が効いている |

## 適用後の実測値

- テンプレート総数 **44**(管理下43 + ブートストラップ1)
- **43件すべてに `description` の同定マーカーがある**。無いのは `id=37` のみ
- `survey_vars` の変更は**全34件で0件**だった(転記が正確だったことの実データでの裏付け)
- `arguments` の変更は1件のみ(`incident_investigate_setup` の `["-l quory"] → []`。転記原則の唯一の例外、Coordinator判断)

## 名前の変化について(Yoshinobu判断、2026-08-04)

機械変換により、一部で元の名前が持っていた説明が失われた。

- `Proxmox hardware check` → `Proxmox hw check`
- `Ubuntu nightly reboot if required` → `Ubuntu nightly`
- `(only on Quory)` / `(Manual)` の注記が消えた

**Yoshinobuは許容と判断した。** 理由は「今後あまり自分がSemaphoreを叩く運用をしたくない」ため、手動操作時の読みやすさに拘る意味が小さいこと。**`title` フィールドでいつでも上書きでき、改名してもidは保たれる**ため、この判断は後から覆せる。
