---
name: ansible-correctness-review
description: homelab-ansibleのReviewerがAnsibleの計画または実装差分について、実行経路、冪等性、部分失敗後の再実行、失敗の観測可能性、変数評価、check modeの成立性を査読するときに使う。Ansibleのplaybook、role、task、handler、filter pluginまたはそれらの接続をレビューする場面で使い、表現上の好みや網羅的なスタイル指摘には使わない。
---

# Ansible Correctness Review

要求どおりの状態遷移が実際のAnsible実行モデルで成立するかを確認する。重大な誤動作へつながる具体的な経路だけをfindingにし、好みや局所的な書き味は実装者に委ねる。

## 手順

1. requirement、受入条件、対象diff、対象Context / Policy、tester-gateを読む。
2. entrypointから変更箇所と接続先までを辿り、どのhostで、どの条件で、何回実行されるかを確認する。
3. 変更に関係する観点だけを、次の順で確認する。
   - **到達性と実行単位**: `when`、loop、動的include、handler、`run_once`、`delegate_to`、host failureにより、必要なtaskが未実行または過剰実行にならないか。
   - **状態遷移と再実行**: 初回、変更なし、途中失敗後の再実行で、前提・処理順・冪等性・一時状態の扱いが成立するか。
   - **結果判定**: rc、registered result、`changed_when`、`failed_when`、`rescue`、例外吸収が、成功・該当なし・判定不能を区別しているか。
   - **評価文脈**: 変数の未定義・空・型違い、変数優先順位、host scope、lookupの再評価、多層エスケープにより意味が変わらないか。
   - **check mode**: 対象Policyの分類とmoduleの実挙動に照らし、必要な分岐がskipまたは実行され、apply相当の副作用が混入しないか。
4. 想定入力または実行経路、発生条件、観測される影響を示せるものだけをfindingにする。
5. 最小の修正条件または確認方法を`skills/code-review/SKILL.md`の形式で返す。

## 指摘しないもの

- 要求、Policy、既存のリポジトリ規約、具体的な障害可能性のいずれにも結び付かない命名・配置・記法の好み。
- 同じ意味を保つ複数の妥当な実装方式のうち、Reviewerが別案を好むというだけの差。
- 発生経路や影響を示せない一般論上の懸念。
- Testerが担う実ホスト検証の代行。実行による裏取りが必要なら、Reviewer Roleの安全境界内で可能な検証を提案し、不足は未確認事項として返す。

## 正本との関係

- 重大度、返却先、レビュー独立性は`docs/ai/roles/reviewer.md`を正本とする。
- Ansible実行の安全分類とcheck modeの判断は`docs/ai/policies/ansible_test_safety_policy.md`を正本とする。
- 実装上の既知の落とし穴は、対象に関係する場合だけ`skills/ansible-implementation-style/SKILL.md`を参照する。本Skillへ複製しない。
- セキュリティ上の攻撃面は`skills/ansible-security-review/SKILL.md`、テスト不足は`skills/test-gap-review/SKILL.md`で別に扱う。
