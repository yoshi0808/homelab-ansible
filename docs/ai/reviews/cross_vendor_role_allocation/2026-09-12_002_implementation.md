# 実装記録

## 変更

- ADR-013を追加し、次の非自明な実装案件3件に限る実験配分と評価項目を定めた。
- Coordinator Roleの現在割当を、Claude Code Implementer、Claude Code計画Reviewer、fresh Codex差分Reviewer、fresh Codex Tester、Claude Code Auditorへ変更した。
- agent-messaging Operations Contextのactive identity、agmsg対象Role、native subagent対象Role、tmux常駐構成を新配分へ揃えた。
- ADR-011はベンダー中立とCoordinator effortの原則を保持した部分supersede、ADR-012は実験期間中supersedeと明記した。
- gitignoredの`new-session.sh`は、常駐Claude Roleを`implementer reviewer auditor`へ変更した。tracked正本はagent-messaging Contextである。
- `docs/ai/status.md`へ3案件の評価待ちを追加し、完了済みPolicy補完行を規律どおり除去した。

## 反映前の状態

`homelab` rosterには旧`implementer(codex)`登録が残っている。新しいlauncherが`implementer(claude-code)`を起動する前に旧登録を正規のagmsg scriptで解除し、`./new-session.sh --reset`でfresh構成を作る必要がある。登録変更とsession resetは本差分のレビュー・commit前には行わない。

## 自己検証

- `bash -n new-session.sh`: rc0
- `git diff --check`: rc0
- liveなRole/Context/launcherを旧配分の語で掃引し、履歴として保持するADR-011/012以外の現行記述を更新した。

独立規範レビュー、ローカルlauncherのreset実測、commit/pushは未実施。

## 003レビュー対応

Major 1件を受け、agmsgに存在しないrole別effort経路を追加する案は採らず、Claude Code Implementerを計画Reviewer・Auditorと同じmedium既定へ揃えた。ADR-013とCoordinator Roleに、agmsgはmodelだけを渡すため実効経路のないhighを宣言しないこと、品質不足時は起動経路ごと見直すことを明記した。agmsg本体と外部設定は変更していない。

SuggestionのADR-011 Status表現も、残る原則をAcceptedとし、Role割当だけをADR-013が実験期間中supersedeする形へ整理した。

## 005テスト対応

Testerが、`docs/ai/status.md`のNextに「Testerをcodex側へ移すか(未決)」というliveな旧判断を検出した。現行Now行とADR-013で移行が決定済みのため、重複更新せず旧Next行を削除した。AC4の実resetとAC6の3案件評価は配備・経過観察工程へ残す。
