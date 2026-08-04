# Incident: ansy Semaphore の API token が対話ログへ露出した

日付: 2026-08-04
状態: 解決済み
対象: `docs/ai/reviews/semaphore_templates_as_code/` の検証工程(Tester)
種別: セキュリティ事故
原因分類: #運用考慮ミス

## 症状

Tester が ansy の Semaphore API を検証する過程で `curl -v` を1回使用し、**`Authorization` ヘッダ(API token を含む)が自身のツール出力へ表示された**。Tester 自身が申告した。

- 露出先は**このセッションの対話ログとsubagentのtranscript**(`/tmp` 配下)。**リポジトリ内のファイル・成果物には書かれていない**(`2026-08-04_005_test_result.md` を含む)。
- 対象は **ansy の Semaphore の token** であり、quory(本番)のものではない。
- ansy の Semaphore は同日に SSH 鍵をすべて削除済みで、**どのホストへも到達できず、リポジトリの clone もできない**。この token で可能なのは ansy 上のテンプレート定義等の操作に限られる。

## 原因

`curl -v` は要求ヘッダを標準エラーへ出力する。**認証情報を含む要求で `-v` を使うと、出力先が人の目やログである限り必ず露出する。**

依頼文は「token が平文でログ・レポート・リポジトリに現れた状態」を禁止事項として明示していたが、**禁止したのは結果であり、`-v` という手段が同じ結果を生むことは Tester 側の判断に委ねられていた**。実装側(role)には `no_log` が入っており、そちらの経路では露出していない。**検証のために手で叩く経路にだけ、同じ防御が無かった。**

## 修正内容

1. **当該 token を失効させ、再発行した**(Yoshinobu、Semaphore UI、2026-08-04)。同じパスへ差し替え済み。
2. 認証情報を伴う API 検証を依頼するときは、**`-v` / `-i` / `--trace` 等でヘッダを出さないこと**を依頼文の禁止事項へ具体的に含める。結果だけを禁じても、手段の側で踏まれる。以後の依頼文へ反映済み。
3. 副産物として、実装側で**`no_log: true` は `rescue:` 内の `ansible_failed_result.msg` を隠さない**ことが判明した(Implementerがオフラインで発見)。失敗メッセージ表示前に token 値を明示的に伏せる処理を入れた。**同じ事象がrole側の経路でも起こりえたということであり、この incident が無ければ気づいていない。**

## 確認方法

- 新 token で `GET /api/projects` が **200** を返すことを確認済み(2026-08-04)。
- **旧 token の失効は、AI側では確認していない。** 旧 token の値は Coordinator の文脈に一度も入っておらず(露出したのは subagent の transcript 内)、確認するには transcript から掘り出すことになるため**行わなかった**。失効は Yoshinobu が UI で削除したことをもって成立とする。
- role 側の伏せ字処理は、token を埋め込んだ失敗メッセージのfixtureで完全に伏せられることをオフラインで確認済み。
