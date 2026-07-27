# 動的include(`include_tasks`)は静的検査も`rescue`も届かない

## 教訓

`ansible.builtin.include_tasks` で読み込むタスクファイルは、**実行時に初めて解決される**。ここから、実測で確認した3つの制約が出る(Ansible core 2.20.1、2026-07-27)。

**1. `--syntax-check` は中身を検証しない。** include先のYAMLが壊れていても静的検査は通る。`ansible-lint` も `load-failure` を出すだけで内容を追わない。**静的検査を通ったことは、include先が健全であることを意味しない。**

**2. YAML構文エラーは `block`/`rescue` で捕捉できない。** パースはタスク実行ループに入る前に失敗するため、`rescue:` の対象にならない。playは即死する(`rc=4`)。

- **ファイルが存在しない**ケースは `rescue` で捕捉できる(`rc=2` → `rc=0` に変わる)。ただし PLAY RECAP の `failed` は 0→1 になる
- **構文エラー**は捕捉できない。この2つを混同しない

**3. `include_tasks` タスク自身に付けられない属性がある。** `become` / `delegate_to` を付けると `'become' is not a valid attribute for a TaskInclude` でハードエラー。`block` に `changed_when` を付けても `'changed_when' is not a valid attribute for a Block` になる。これらは**include先の各taskへ個別に付ける**。

## 帰結

**動的includeを1つ足すことは、include元の全呼び出し経路に対してハード依存を1つ足すこと**である。include先が壊れれば、呼び出し元がいくつあっても全部止まる。

そしてその破損は**静的検査で防げず、実行時の防御でも防げない**。したがって予防の層はcommit前のゲートしか無い。

## 根拠(2026-07-27)

`roles/common_slack/tasks/notify.yml`(**38箇所・25ファイル**からincludeされる通知の単一の絞り)へ、証拠捕捉の `include_tasks` を1行足した案件。

独立Reviewerが「include行自体がどの`rescue`にも守られていない」と指摘し、**実際に `capture.yml` を退避して再現**した(`failed=1` / `rc=2`、playが死ぬ)。続いてImplementerが `block`/`rescue` で包んだうえで2ケースを実測し、**ファイル欠落は救えるが構文エラーは救えない**ことを確認した。

Coordinatorはここで衝突に直面した。「観測は被観測を壊さない」と「静かに壊れるのが最悪」が両立しない。採った解は**3層に分けること**である。

1. **予防(開発時)**: commit前にstagedな全YAMLの構文を検査する(`scripts/check-staged-yaml.py`)。構文エラーは実行時条件ではなく**リポジトリの欠陥**であり、開発時のゲートが正しい層である
2. **縮退(実行時)**: `block`/`rescue` でファイル欠落は巻き添えにしない。構文エラーは救えないことを既知の限界として受け入れる
3. **検出(観測側)**: 捕捉が止まっていることを別プロセスが検出する

**runtime での事前パース検証(include前にYAMLを読んで妥当性を確認する)は採らなかった。** 全呼び出し経路でsubprocessが増えるうえ、**include元のファイル自身が同じ構文エラーの露出を元から持っている**ため、新規ファイルにだけ防御を積むのは一貫しない。

## 適用

- 動的includeを追加するとき、**include元が何箇所から呼ばれるか**を先に数える。それが破損時の影響範囲である
- include先の健全性は**commit前に検査する**。静的検査と実行時防御のどちらも当てにしない
- 「ファイルが無い」と「ファイルが壊れている」を**別の失敗クラスとして扱う**。前者だけ `rescue` で救えるため、片方の実測をもって両方を保証したと書かない
- 防御を意図的に置かない箇所には、**置かない理由をコメントに残す**。書き忘れと区別がつかないと、後から善意で足される

## 関連

- [[distinguish-nothing-found-from-not-run]](同日に出たもう1つの欠陥クラス)
- [[multilayer-escaping-and-novel-stack-verification]](初物スタックはローカルでruntime再現手段を先に確保する)
