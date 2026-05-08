#!/usr/bin/env bash
# Ansible から呼ばれ、Codex CLI に changelog 分類・日本語レポート生成を依頼する。
# Usage: scripts/codex-classify.sh <input_json> <output_json>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POLICY_FILE="$REPO_ROOT/docs/ai/prompts/proxmox_patch_policy.md"

# --- 1. 引数チェック ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_json> <output_json>" >&2
    exit 1
fi

INPUT_JSON="$1"
OUTPUT_JSON="$2"

if [ ! -f "$INPUT_JSON" ]; then
    echo "Error: input_json not found: $INPUT_JSON" >&2
    exit 1
fi

if [ ! -f "$POLICY_FILE" ]; then
    echo "Error: policy file not found: $POLICY_FILE" >&2
    exit 1
fi

OUTPUT_DIR="$(dirname "$OUTPUT_JSON")"
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: output directory not found: $OUTPUT_DIR" >&2
    exit 1
fi

# --- Temp files（終了時に必ず削除） ---
PROMPT_FILE=$(mktemp /tmp/codex-classify-prompt.XXXXXX.md)
CODEX_OUTPUT=$(mktemp /tmp/codex-classify-output.XXXXXX.txt)

cleanup() {
    rm -f "$PROMPT_FILE" "$CODEX_OUTPUT"
}
trap cleanup EXIT

# --- 2. Section 3 と Section 16 を抽出 ---
extract_section() {
    local file="$1"
    local section_num="$2"
    awk -v pat="^## ${section_num}[.]" '
        $0 ~ pat             { found=1; print; next }
        found && /^## [0-9]+[.]/ { found=0 }
        found                { print }
    ' "$file"
}

SECTION3=$(extract_section "$POLICY_FILE" "3")

if [ -z "$SECTION3" ]; then
    echo "Error: Failed to extract Section 3 from $POLICY_FILE" >&2
    exit 1
fi

# --- 3. プロンプト生成（tempファイル） ---
INPUT_CONTENT=$(cat "$INPUT_JSON")

cat > "$PROMPT_FILE" << 'PROMPT_EOF'
あなたはProxmox VEパッチ分類エンジンです。以下の入力JSONとパッチポリシーを読み、指定されたJSON形式のみで応答してください。前後の説明文・コードブロックマーカー（```json 等）は出力しないでください。

## 指示

1. 入力JSON の updates リストに含まれる**各パッケージを実際に分析**してください。
   - package_classifications には updates の各パッケージの分析結果を入れてください。
   - 後述の出力形式に示す "package" フィールドが "" のエントリはダミーです。削除し、実際のパッケージ名に置き換えてください。
   - 空の JSON やテンプレートをそのまま返すことは禁止です。
2. 各パッケージの changelog_diff を読み、CVEタイプを識別する（LPE / RCE / DoS / XSS / 認証バイパス / VM escape 等）
3. パッチポリシーの URGENT / HIGH 判断基準テーブルと照合し、urgency_candidate を決定する
4. 日本語で mail_subject および mail_body を生成する（mail_body は 1000 文字程度）
5. 日本語で report_md を生成する（changelog 差分の全文と分析結果を含む）
6. JSON 形式のみ出力する（前後の説明文不要）

## パッチポリシー（Section 3: 判断軸）

PROMPT_EOF

printf '%s\n' "$SECTION3" >> "$PROMPT_FILE"

cat >> "$PROMPT_FILE" << 'PROMPT_EOF'

## 入力JSON

PROMPT_EOF

printf '%s\n' "$INPUT_CONTENT" >> "$PROMPT_FILE"

cat >> "$PROMPT_FILE" << 'PROMPT_EOF'

## 出力形式（以下のスキーマに従い、このJSONのみ出力すること）

※ package_classifications の配列には、入力JSON の updates に含まれる**全パッケージ**の分析結果を入れること。
※ 以下の "package": "" のエントリはスキーマ説明用のダミーである。このまま返さないこと。

{
  "status_inputs": {
    "important_component_updates": [],
    "important_component_removals": [],
    "replacement_suspected": false,
    "major_upgrade_suspected": false,
    "security_sensitive_updates": [],
    "urgency_candidate": "NORMAL"
  },
  "package_classifications": [
    {
      "package": "<updates の各パッケージ名に置き換えること>",
      "important_component": false,
      "remove_action": false,
      "replacement_suspected": false,
      "security_sensitive": false,
      "cve_types_detected": [],
      "urgency_candidate": "LOW",
      "urgency_reasoning": "<分析根拠を記述すること>",
      "evidence": [],
      "confidence": "medium"
    }
  ],
  "mail_subject": "<日本語で記述すること>",
  "mail_body": "<日本語で1000文字程度で記述すること>",
  "report_md": "<日本語でchangelog全文と分析結果を含めること>"
}
PROMPT_EOF

# --- 4. codex exec でCodex CLIを呼び出す ---
cd "$REPO_ROOT"
if ! codex exec "$(cat "$PROMPT_FILE")" > "$CODEX_OUTPUT" 2>&1; then
    echo "Error: codex exec failed" >&2
    sed -n '1,200p' "$CODEX_OUTPUT" >&2
    exit 1
fi

# --- 5. 出力からJSONを抽出・検証してoutput_jsonに保存 ---
CODEX_OUTPUT_PATH="$CODEX_OUTPUT" \
INPUT_JSON_PATH="$INPUT_JSON" \
OUTPUT_JSON_PATH="$OUTPUT_JSON" \
python3 << 'PYEOF'
import json
import sys
import os

codex_output_path = os.environ['CODEX_OUTPUT_PATH']
input_json_path = os.environ['INPUT_JSON_PATH']
output_json_path = os.environ['OUTPUT_JSON_PATH']

with open(codex_output_path, 'r', encoding='utf-8') as f:
    raw = f.read()

with open(input_json_path, 'r', encoding='utf-8') as f:
    input_data = json.load(f)

# 出力中の全JSONブロックを探し、最後のものを使う
def find_json_blocks(text):
    blocks = []
    i = 0
    while i < len(text):
        if text[i] != '{':
            i += 1
            continue
        depth = 0
        in_string = False
        escape_next = False
        end = -1
        for j, c in enumerate(text[i:], i):
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end != -1:
            blocks.append(text[i:end + 1])
            i = end + 1
        else:
            i += 1
    return blocks

blocks = find_json_blocks(raw)
if not blocks:
    print('Error: No JSON found in Codex output', file=sys.stderr)
    print('Codex output (first 2000 chars):', file=sys.stderr)
    print(raw[:2000], file=sys.stderr)
    sys.exit(1)

json_str = blocks[-1]

try:
    data = json.loads(json_str)
except json.JSONDecodeError as e:
    print(f'Error: Invalid JSON: {e}', file=sys.stderr)
    print(f'JSON string (first 500 chars): {json_str[:500]}', file=sys.stderr)
    sys.exit(1)

# 必須キーの検証
required = ['status_inputs', 'package_classifications', 'mail_subject', 'mail_body', 'report_md']
missing = [k for k in required if k not in data]
if missing:
    print(f'Error: Missing required keys: {missing}', file=sys.stderr)
    sys.exit(1)

status_inputs = data['status_inputs']
if not isinstance(status_inputs, dict):
    print('Error: status_inputs must be an object', file=sys.stderr)
    sys.exit(1)

status_required = ['security_sensitive_updates']
status_missing = [k for k in status_required if k not in status_inputs]
if status_missing:
    print(f'Error: Missing required status_inputs keys: {status_missing}', file=sys.stderr)
    sys.exit(1)

classifications = data['package_classifications']
if not isinstance(classifications, list):
    print('Error: package_classifications must be a list', file=sys.stderr)
    sys.exit(1)

if not classifications:
    print('Error: package_classifications must not be empty', file=sys.stderr)
    sys.exit(1)

updates = input_data.get('updates')
if not isinstance(updates, list):
    print('Error: input_json.updates must be a list', file=sys.stderr)
    sys.exit(1)

if len(classifications) != len(updates):
    print(
        f'Error: package_classifications count ({len(classifications)}) '
        f'does not match input updates count ({len(updates)})',
        file=sys.stderr,
    )
    sys.exit(1)

dummy_package_values = {
    '',
    '<updates の各パッケージ名に置き換えること>',
}

for index, item in enumerate(classifications):
    if not isinstance(item, dict):
        print(f'Error: package_classifications[{index}] must be an object', file=sys.stderr)
        sys.exit(1)
    package = item.get('package')
    if package in dummy_package_values:
        print(
            f'Error: package_classifications[{index}].package was not replaced: {package!r}',
            file=sys.stderr,
        )
        sys.exit(1)
    if 'evidence' not in item:
        print(f'Error: package_classifications[{index}] missing required key: evidence', file=sys.stderr)
        sys.exit(1)

with open(output_json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'OK: Classification JSON saved to {output_json_path}')
PYEOF
