# 実装報告: proxmox_patch_policy.md 陳腐化記述・宙ぶらりん参照・冗長規範の整理

対象:
`docs/ai/reviews/policy_standardization/2026-07-25_024_requirement_proxmox_patch_policy_sophos_mode_cleanup.md`
の「変更内容(逐語指定)」変更1〜10。

種別: Policy文書の変更のみ(実装コード変更なし)。文言は要件書のbefore/afterを
そのまま適用し、言い換え・要約・追加解釈は行っていない。

## 変更1〜10 適用結果

| # | 対象 | 適用結果 |
|---|---|---|
| 1 | `proxmox_patch_policy.md` §1 SB-001 | 「Sophos Firewall VMをProxmoxへ移行する前にpatch運用を確立する。」bulletを削除。他のbulletは無変更。 |
| 2 | SB-003 | 「土曜朝の自動適用を許可する。」→「自動適用を許可する。実行scheduleの実値はscheduler設定とOperations Contextを正本とする。」に置換。 |
| 3 | SB-014 | 「tagなしguestは明示migration対象外だが、runningのまま残れば最終確認で停止する。」を「tagなしguestは明示migration対象にしない。」へ書き換え、直後に新規`<!-- SB-091 -->`(終端不変条件)を追加。 |
| 4 | SB-049 | markerと本文をまとめて削除。前後の空行は単一空行に整えた(diff確認済み、二重空行なし)。 |
| 5 | SB-060 | 「Sophos移行前なら移行を延期し、移行後なら」を削除し「Sophos稼働nodeを固定して…」へ直結。 |
| 6 | SB-080 | 「Mode A、Mode B、」→「cluster外control nodeからのfull flow、Proxmox上control nodeからの単一node flow、」に置換、`条件`の後に`(§2.3)`を追加。 |
| 7 | SB-085 | 冒頭の「Sophos Firewall VMがProxmox上で稼働している場合は、」条件節を削除。 |
| 8 | §7.3 | SB-083(見出し行除く本文+10 bullet)、SB-084、SB-086を削除し、要件書指定どおりの`<!-- SB-092 -->`・`<!-- SB-093 -->`に置換。見出し`### 7.3 Sophos安全前提`は維持。 |
| 9 | §8 変更履歴 | 2026-07-24行の直前に2026-07-25行を要件書の文言どおり追加。既存行は無変更。 |
| 10 | `context/operations/proxmox-patch.md` Sophos VM稼働時 | 段落全体を要件書afterのとおり置換。直後の「本節は確認順を示すだけで、直接patchの許可や例外を作らない。」文は無変更で維持。 |

全10箇所とも要件書のbefore/after文字列と一致することを、適用後に該当paragraphを
目視突き合わせ済み(下記「自己検証」のgit diff全文にも表れている)。

## 自己検証

### git diff(全文、2ファイル)

適用後の差分は、上記10箇所以外のhunkを含まない(意図しない箇所への変更なし)。
`docs/ai/policies/proxmox_patch_policy.md`: 変更1〜9に対応する7 hunk。
`docs/ai/context/operations/proxmox-patch.md`: 変更10に対応する1 hunk。

### git diff --check(whitespace異常)

```text
$ git diff --check -- docs/ai/policies/proxmox_patch_policy.md docs/ai/context/operations/proxmox-patch.md
(出力なし、exit=0)
```
→ PASS。

### playbooks/roles 差分ゼロの確認

```text
$ git diff --stat -- playbooks/ roles/
(出力なし)
$ git status --porcelain playbooks/ roles/
(出力なし)
```
→ PASS。実装コードは一切変更していない。

### 他Policy無変更の確認

```text
$ git diff --stat -- docs/ai/policies/autonomous_recovery_policy.md
(出力なし)
$ git diff --stat -- docs/ai/policies/ | grep -v proxmox_patch_policy.md
(出力なし、= proxmox_patch_policy.md以外のPolicyに差分なし)
```
→ PASS。`autonomous_recovery_policy.md`への変更は参照リンク追加(SB-093内、
`[autonomous_recovery_policy.md](autonomous_recovery_policy.md)`)のみで、
同文書自体は未編集。

### SBマーカー台帳(全件抽出)

`<!-- SB-XXX -->` 形式のマーカーのみを対象に抽出(変更9の変更履歴行はSB番号を
平文で言及するが、これはマーカーではなく履歴説明文であり要件書の指定文言どおり)。

```text
$ grep -oE '<!-- SB-[0-9]{3} -->' docs/ai/policies/proxmox_patch_policy.md \
    | sed -E 's/<!-- (SB-[0-9]{3}) -->/\1/' | sort > /tmp/after.txt
$ wc -l /tmp/after.txt
89 /tmp/after.txt
$ uniq -d /tmp/after.txt   # 重複チェック
(出力なし = 重複なし)
$ grep -E '<!-- SB-(049|083|084|086) -->' docs/ai/policies/proxmox_patch_policy.md
(出力なし = 退番4件が本文から完全に消滅)
$ for n in 091 092 093; do grep -c "<!-- SB-$n -->" docs/ai/policies/proxmox_patch_policy.md; done
1
1
1
```

期待集合(SB-001〜SB-090からSB-049/083/084/086を除いた86件 + 新規SB-091/092/093の
3件 = 89件)と実際のマーカー一覧を`diff`で突き合わせ、完全一致を確認した
(過不足なし、SB-001〜SB-090のうち退番4件以外の欠落なし)。

- (a) 重複なし: 確認済み(`uniq -d`出力なし)。
- (b) 退番SB-049/083/084/086: 本文から消滅を確認済み。
- (c) 新規SB-091/092/093: 各1回だけ存在を確認済み。
- (d) それ以外の番号の欠落なし: 期待集合との`diff`が完全一致(差分なし)で確認済み。

### 宙ぶらりん参照の消滅(`Mode A` / `Mode B`)

```text
$ grep -n "Mode A\|Mode B" docs/ai/policies/proxmox_patch_policy.md
405:| 2026-07-25 | ...定義が存在しない`Mode A` / `Mode B`参照を条件記述へ置換。... |
```
本文中の実参照(SB-080)は変更6で条件記述へ置換済みで消滅。唯一残る言及は変更9で
追加した変更履歴行内で、要件書が指定した文言どおりに`Mode A` / `Mode B`という
語句そのものを履歴説明として記載しているもの(退番SB-049/083/084/086の言及も同様)。
これは要件書「変更9」のafter文言に含まれる文字列そのものであり、宙ぶらりん参照
(定義なき本文中の使用)ではない。`docs/ai/reviews/`配下の過去記録は要件書の
「レビュー観点3」どおり対象外のため未確認・未変更。

### 陳腐化表現の掃引

```text
$ grep -n "移行前\|移行する前" docs/ai/policies/proxmox_patch_policy.md docs/ai/context/operations/proxmox-patch.md
(出力なし)
```
→ PASS。「移行前」「移行する前」等、Sophos移行完了前を前提とした表現は残っていない。

### IPv4リテラルの手動確認

`scripts/git-pre-commit-check.sh`はstaged files前提の設計で、Implementerはcommit
準備(git add)を行わない方針([[feedback_no_agent_commit_any_repo]])のため、
同スクリプト内のIPv4検査ロジック(`git diff --cached -U0` + 正規表現)と同じ
パターンを追加行(working tree diff)へ直接適用して代替確認した。

```text
$ git diff -U0 -- docs/ai/policies/proxmox_patch_policy.md docs/ai/context/operations/proxmox-patch.md \
    | grep -E '^\+[^+].*([0-9]{1,3}\.){3}[0-9]{1,3}'
(出力なし)
```
→ IPv4様の文字列を含む追加行なし。staged状態での同スクリプト実行はtester委譲。

### markdown link切れ確認

新規追加した相対リンク`[autonomous_recovery_policy.md](autonomous_recovery_policy.md)`
(SB-093、`docs/ai/policies/`内での同一ディレクトリ参照)を含め、両ファイル内の
`.md`リンクを全件抽出し、リンク先ファイルの実在を確認した。

```text
$ ls docs/ai/policies/autonomous_recovery_policy.md
docs/ai/policies/autonomous_recovery_policy.md
```
→ 存在確認OK。他のリンク(`../context/...`、`../../policies/...`)は既存のまま
未変更で、今回のdiffによる破損はない。

### tester-gate lint

```text
$ bash scripts/check-tester-gate.sh
[tester-gate-lint] OK (37 playbooks)
```
→ PASS(playbook無変更の副次確認)。

## 作成・更新したファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `docs/ai/policies/proxmox_patch_policy.md` | 更新 | 変更1〜9を適用。 |
| `docs/ai/context/operations/proxmox-patch.md` | 更新 | 変更10を適用。 |
| `docs/ai/reviews/policy_standardization/2026-07-25_025_implement_proxmox_patch_policy_sophos_mode_cleanup.md` | 新規 | 本ファイル。 |

`playbooks/`、`roles/`、`docs/ai/policies/autonomous_recovery_policy.md`を含む
上記以外のファイルは一切変更していない。

## 未対応事項 / 注意点

特になし。要件書の変更1〜10はすべて適用済みで、意味の再判断が必要と感じた
箇所はなかった(逐語指定どおり機械的に適用可能な差分だった)。

## Next step files
- docs/ai/reviews/policy_standardization/2026-07-25_024_requirement_proxmox_patch_policy_sophos_mode_cleanup.md
- docs/ai/reviews/policy_standardization/2026-07-25_025_implement_proxmox_patch_policy_sophos_mode_cleanup.md
