---
name: incident-recording
description: homelab-ansibleのTech Leadが不具合・セキュリティ事故の修正確認後にIncidentを記録するときに使う。「インシデントを記録する」「incidentを書く」場面で使う。分類・保存期間・昇格条件は docs/ai/memory-classification.md が正本、このSkillはIncidentファイル自体の型のみ定める。
---

# Incident記録

## 型

ファイルパス: `docs/ai/memory/incidents/<YYYY-MM-DD>_<slug>.md`

```
# Incident: [一言タイトル]

日付: YYYY-MM-DD
対象: [playbook / role / system]
種別: [動作不具合 | セキュリティ事故]
原因分類: #要件定義ミス #製造ミス #テスト不足 #運用考慮ミス #リソース・資源不足 (複数可)

## 症状

## 原因

## 修正内容

## 確認方法
[正常動作をどう確認したか]
```

## 記録タイミング

修正して正常動作の確認が取れた時点で1回記録する。調査中の仮説や未確定情報は載せない。

## 運用ルール

- Coordinatorが月次で`docs/ai/memory/incidents/`を振り返る。
- 同じ`原因分類`タグが複数件で繰り返し検出された場合、Lessonを経由せず直接、該当業務のPolicy改訂(許可/禁止/停止条件の明文化が必要な場合)またはSkill新設・改訂(再利用手順の整備が必要な場合)を検討する。
- 一度きりの気づきは従来どおりLessonへの昇格を検討する。昇格ルールの全体像は`docs/ai/memory-classification.md` 3節が正本。

## 適用条件

IPアドレス・VLAN ID・VM ID・認証情報の実値は書かない(`docs/ai/context-classification.md` §3/§4)。
