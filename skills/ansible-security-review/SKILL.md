---
name: ansible-security-review
description: homelab-ansibleのReviewerがAnsible実装のセキュリティレビューを行うときに使う。「セキュリティレビューする」「shell/commandモジュールの安全性を確認する」場面で使う。Webアプリ向けのSQLi/XSS/CSRFではなく、Ansible特有の攻撃面(変数注入、機密情報露出)を対象とする。
---

# Ansible Security Review

`anthropics/knowledge-work-plugins`の`code-review`はWebアプリ向け観点が中心でAnsible特有の攻撃面をカバーしないため、Ansible公式ドキュメントを直接の根拠として自作したもの(2026-07-23)。

**revision追跡**: 「その他の観点」節はrecovery pipelineのインシデント実例が根拠で外部revisionを持たない。「変数注入対策」節のAnsible公式ドキュメントは「latest」参照(固定revisionなし、参照日2026-07-23)。Ansibleのメジャーバージョンアップ時など内容が古くなったと疑われる場合は該当URLを再確認する。

## 変数注入対策(Ansible公式ドキュメントが根拠)

- shellモジュール: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/shell_module.html
- commandモジュール: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/command_module.html

- shellモジュールでテンプレート化された変数を使う場合は、必ず`quote`フィルタを使ってインジェクションを防ぐ。
- commandモジュールはシェルを介さないため、可能な限りshellよりcommandを優先する。
- `argv`パラメータ(リスト形式)を使うと文字列結合よりさらに安全。

## その他の観点(recovery pipelineのインシデント実例が根拠、公式ドキュメントに直接記載なし)

- `no_log`の付け忘れによる機密変数のログ露出。
- `delegate_to`と信頼できない変数の組み合わせ。
- `lookup()`プラグイン経由での信頼境界超え。

## 適用先

`skills/code-review/SKILL.md`の構造(Critical Issues / Suggestions)に差し込んで報告する。
