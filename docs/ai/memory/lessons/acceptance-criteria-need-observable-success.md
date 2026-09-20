# 受入条件には「成功」の観測方法まで書く

Skill `skills/requirements-analysis/SKILL.md`「『成功』の観測方法まで書く」節へ昇格済み(2026-07-27の月次Knowledge振り返り)。

## 再発記録

**記録主体と判定契約は `docs/ai/memory-classification.md`「`lessons/`の「再発記録」節」が正本。**

| 日付 | 何に対して踏んだか | 反した規範 | 気づかせたもの |
|---|---|---|---|
| 2026-08-25 | Semaphore新版検知をcommit・push時点で「閉じた」としたが、template setup未実行でtemplateとscheduleは未登録だった。 | 依頼文「新版検知を自動実行する」に対し、実際にSemaphoreへtemplateとscheduleが登録され稼働可能であることが必要 | Yoshinobu |
| 2026-09-20 | weekly full件数超過ゲートのrequirement §6で、AC2が「本番Slackへ送らない」と「1通出る」を同時に要求し、AC5は件数・status、AC7はcheck modeの期待値を書いていなかった。安全境界内では観測できないACだった。 | `skills/requirements-analysis/SKILL.md`「『成功』の観測方法まで書く」 | 計画Reviewer(Codex、独立) |
