# 多層エスケープと初物スタックの検証手段

**分類**: Lesson
**由来**: Alloy Phase 2実装(2026-07-17)で本番APPLYが4連続FAILした教訓(全てfail-closed/自動復旧で実害ゼロ)。

## 失敗の分類

①AppArmor(rsyslogdがAnsible remote tmpのcandidate読取拒否) ②非文字列when conditional(check-modeのshort-circuitが隠蔽) ③River→LogQL二重パースのエスケープ(alloy validateはexit0、runtime graph評価のみで失敗) ④ヘルスチェック自体のrc判定バグ。うち3件(タスクregex→when→River template)が**多層エスケープ/評価文脈の同一クラス**。

## 学び

多層エスケープ(Jinja→YAML→regex、Jinja→River→LogQL)は系統的に見落としやすい弱点クラスである。また初物スタック(新DSL+新OS制約)は検証手段に構造的な穴がある(validateがruntimeを評価しない、`--check`がAPPLY専用経路を通せない、AppArmorは実検証時のみ発現)ため、慎重さだけでは防げず実適用でしか露見しないことがある。1:1移植だった同プロジェクトのPhase 1が一発で通ったのと対照的。

## 適用条件

1. **初物スタックのrequirementは増分を小さく切る**(一括の要求は過大になりやすい)。
2. **同一クラスのバグが出たら「そのファイル」でなく「その評価文脈クラス」で全面掃引する**(1箇所を直しても別の評価文脈に同種の問題が残ることがある)。
3. **新スタック導入時は、ローカルで実parser/実runtimeを再現できる検証手段を最初に確保する**(バイナリをローカル環境に導入する等)。
4. レビュー定型観点に「多層エスケープ文脈の列挙」「rc規約(grep/journalctlはno-match=1等)」「check-modeで評価されない条件分岐の列挙」を加える(`skills/ansible-security-review/SKILL.md`・`skills/code-review/SKILL.md`と合わせて運用する)。
5. Alloyの`stage.match`セレクタは、ダブルクォートのSTRING literalを使う(backtick raw literalは`unexpected IDENTIFIER`でAlloy起動自体が失敗し、`alloy validate`はこれを検出できない)。

## 再発記録

**この節は機械が追記する。** セッション終了時、**別体**が transcript を読み、**次のいずれかが実際に起きたときだけ**1行足す — ①Policyに反した ②harnessの安全機構に止められた ③規範文書または依頼文に書いてあることをしなかった。**それ以外は何も足さない。**

**話題が本 lesson に似ていることは記録の理由にならない。** 調べた・検証した・見つけた、は記録しない。lesson を正しく適用できているものも記録しない。**反した規範の所在を書けない項目は記録しない。**

**回数は推定であって測定ではない。** 分類器はLLMであり、見落とせば沈黙し、過検出すれば水増しする。**回数だけを昇格の根拠にしない** — 3回を超えたら Skill 化の候補として人へ出す、までが機械の役目である。

| 日付 | 何に対して踏んだか | 反した規範 | 気づかせたもの |
|---|---|---|---|
| 2026-08-25 | config.tomlへ省略記号を含むwritable_roots例を提示し、そのまま設定されてTOML解析エラーでCodexを起動不能にした。 | docs/ai/core.md「確認できていない値を推測で固定しない」 | Yoshinobu |
