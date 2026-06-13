#!/usr/bin/env bash
#
# cloudkey_cert_deploy.sh
#
# UniFi OS (CloudKey Gen2 Plus) の Web UI 用 TLS 証明書を、プライベートCA
# 署名のリーフ証明書で更新する参考スクリプト。
#
# これは Ansible role 化の前段として、UniFi OS の非公開証明書管理APIの
# ライフサイクル(login -> upload -> activate -> verify -> delete)を
# CLI で実証・再現するためのものである。本番運用は Ansible playbook
# (cloudkey_cert_deploy.yml) 側で行う。
#
# == 確認済みAPI ==
#   POST   /api/auth/login                        ログイン、TOKEN(JWT)取得
#   GET    /api/userCertificates                  一覧
#   POST   /api/userCertificates                  {name,key,cert} アップロード
#   PUT    /api/userCertificates/{id}/status      {"active":true} 有効化
#   DELETE /api/userCertificates/{id}             削除 (204)
#
# == 認証 ==
#   Cookie の TOKEN(JWT, 有効2時間)+ X-CSRF-Token ヘッダ。
#   CSRFトークンは JWT ペイロードの csrfToken クレームに含まれる。
#   状態変更系(POST/PUT/DELETE)には Origin ヘッダの付与が必要
#   (ホスト名アクセス + Origin が無いと DELETE が 403 になる)。
#
# == 証明書側の制約 ==
#   - 鍵は RSA。ECDSA は受け付けられない。
#   - 鍵は PKCS#1 形式 (BEGIN RSA PRIVATE KEY)。PKCS#8 では登録に失敗する。
#   - cert はチェーン全体(リーフ + 中間CA + ルートCA)を連結した1文字列。
#     プライベートCAではルートまで含めないと検証に失敗する。
#   - name と fingerprint はともにユニーク制約。同一は登録不可。
#
# == 依存 ==
#   bash, curl, jq, openssl
#
# == 使い方 ==
#   read -rs CK_PASS && export CK_PASS    # 管理者パスワードを環境変数で渡す
#   ./cloudkey_cert_deploy.sh
#   unset CK_PASS
#
set -euo pipefail

# ===== 設定(環境変数で上書き可) =====
CK_HOST="${CK_HOST:-cloudkey.internal}"          # 必ずホスト名で接続する
CK_USER="${CK_USER:-yoshi-local}"
CK_PASS="${CK_PASS:?環境変数 CK_PASS に管理者パスワードを設定してください}"

CERT_NAME="${CERT_NAME:-cloudkey-$(date +%Y-%m)}" # 世代が分かるユニーク名
CA_DIR="${CA_DIR:-$HOME/.cert/ca}"
INT_CA_CRT="${INT_CA_CRT:-$CA_DIR/home_tls_ca.crt}"
INT_CA_KEY="${INT_CA_KEY:-$CA_DIR/home_tls_ca.key}"
ROOT_CA_CRT="${ROOT_CA_CRT:-$CA_DIR/radius_ca.crt}"
WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
LEAF_DAYS="${LEAF_DAYS:-45}"
DELETE_OLD="${DELETE_OLD:-true}"                  # 旧 uploaded 証明書を削除するか

BASE="https://${CK_HOST}"
ORIGIN="https://${CK_HOST}"
# UniFi OS はプライベートCA証明書のため -k で接続(接続先はLAN内のホスト名固定)
CURL="curl -sk --connect-timeout 10"

cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

# ===== 0) リーフ証明書を発行(RSA / PKCS#1 / フルチェーン) =====
echo "[*] リーフ証明書を発行中 (CN=${CK_HOST})..."
LEAF_KEY="$WORK_DIR/leaf.key"
LEAF_CSR="$WORK_DIR/leaf.csr"
LEAF_CRT="$WORK_DIR/leaf.crt"
CHAIN="$WORK_DIR/fullchain.pem"
EXT="$WORK_DIR/ext.cnf"

# CloudKey の名前解決から IP を取得して SAN に動的に含める
CK_IP=$(getent ahostsv4 "$CK_HOST" | awk 'NR==1{print $1}')
cat > "$EXT" <<EOF
subjectAltName = DNS:${CK_HOST}$([[ -n "$CK_IP" ]] && echo ",IP:${CK_IP}")
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
EOF

# RSA 2048, PKCS#1 形式(-traditional)
openssl genrsa -traditional -out "$LEAF_KEY" 2048 2>/dev/null
openssl req -new -key "$LEAF_KEY" \
  -subj "/CN=${CK_HOST}/O=Home/C=JP" -out "$LEAF_CSR" 2>/dev/null
openssl x509 -req -in "$LEAF_CSR" \
  -CA "$INT_CA_CRT" -CAkey "$INT_CA_KEY" -CAcreateserial \
  -days "$LEAF_DAYS" -sha384 \
  -extfile "$EXT" -out "$LEAF_CRT" 2>/dev/null

# フルチェーン = リーフ + 中間CA + ルートCA
cat "$LEAF_CRT" "$INT_CA_CRT" "$ROOT_CA_CRT" > "$CHAIN"
chain_count=$(grep -c "BEGIN CERTIFICATE" "$CHAIN")
[[ "$chain_count" -eq 3 ]] \
  || { echo "ERROR: フルチェーンの段数が想定外 (${chain_count}/3)" >&2; exit 1; }
echo "[*] 発行OK: RSA/PKCS#1, フルチェーン3段, ${LEAF_DAYS}日, name=${CERT_NAME}"

# ===== 1) ログイン =====
echo "[*] ログイン中..."
login_headers=$($CURL -D - -o /dev/null -X POST "${BASE}/api/auth/login" \
  -H "Content-Type: application/json" -H "Origin: ${ORIGIN}" \
  -d "$(jq -n --arg u "$CK_USER" --arg p "$CK_PASS" '{username:$u, password:$p}')")

TOKEN=$(echo "$login_headers" | tr -d '\r' \
  | sed -n 's/.*[Ss]et-[Cc]ookie:.*TOKEN=\([^;]*\).*/\1/p' | head -1)
[[ -n "$TOKEN" ]] || { echo "ERROR: ログイン失敗(TOKEN取得不可)" >&2; exit 1; }

# JWT ペイロードを base64url デコードして csrfToken を取り出す
pad() { local s="$1"; while (( ${#s} % 4 )); do s="${s}="; done; echo "$s"; }
payload=$(echo "$TOKEN" | cut -d. -f2)
CSRF=$(pad "$payload" | tr '_-' '/+' | base64 -d 2>/dev/null | jq -r .csrfToken)
[[ -n "$CSRF" && "$CSRF" != "null" ]] || { echo "ERROR: CSRF抽出失敗" >&2; exit 1; }
echo "[*] 認証OK (CSRF: ${CSRF:0:8}...)"

# 状態変更系には Origin が必須
auth_hdr=(-H "Cookie: TOKEN=${TOKEN}" -H "X-CSRF-Token: ${CSRF}" -H "Origin: ${ORIGIN}")

# ===== 2) 現在アクティブな uploaded 証明書のIDを控える(後で削除) =====
list_json=$($CURL "${BASE}/api/userCertificates" \
  -H "Cookie: TOKEN=${TOKEN}" -H "X-CSRF-Token: ${CSRF}")
OLD_IDS=$(echo "$list_json" | jq -r '.[] | select(.source=="uploaded") | .id')

# ===== 3) アップロード =====
echo "[*] アップロード中..."
upload_resp=$($CURL -X POST "${BASE}/api/userCertificates" \
  -H "Content-Type: application/json" "${auth_hdr[@]}" \
  -d "$(jq -n --arg name "$CERT_NAME" \
            --rawfile key "$LEAF_KEY" \
            --rawfile cert "$CHAIN" \
            '{name:$name, key:$key, cert:$cert}')")
NEW_ID=$(echo "$upload_resp" | jq -r .id)
NEW_FP=$(echo "$upload_resp" | jq -r .fingerprint)
[[ -n "$NEW_ID" && "$NEW_ID" != "null" ]] \
  || { echo "ERROR: アップロード失敗: $upload_resp" >&2; exit 1; }
echo "[*] アップロードOK id=${NEW_ID}"

# ===== 4) 有効化 =====
echo "[*] 有効化中..."
$CURL -X PUT "${BASE}/api/userCertificates/${NEW_ID}/status" \
  -H "Content-Type: application/json" "${auth_hdr[@]}" \
  -d '{"active":true}' >/dev/null

# ===== 5) 検証(TLSで実際に配信される指紋と照合) =====
echo "[*] 配信証明書を検証中..."
sleep 5
served_fp=$(echo | openssl s_client -connect "${CK_HOST}:443" 2>/dev/null \
  | openssl x509 -noout -fingerprint -sha1 2>/dev/null | sed 's/.*=//')
norm() { tr -d ':' | tr 'a-f' 'A-F'; }
if [[ "$(echo "$NEW_FP" | norm)" == "$(echo "$served_fp" | norm)" ]]; then
  echo "[OK] 検証成功: 配信中の証明書がアップロードしたものと一致"
else
  echo "[!]  指紋不一致(再起動途中かも)。expected=${NEW_FP} served=${served_fp}" >&2
fi

# ===== 6) 旧 uploaded 証明書を削除(新しいものは残す) =====
if [[ "$DELETE_OLD" == "true" ]]; then
  echo "[*] 旧 uploaded 証明書を削除中..."
  for id in $OLD_IDS; do
    [[ "$id" == "$NEW_ID" ]] && continue
    code=$($CURL -o /dev/null -w '%{http_code}' \
      -X DELETE "${BASE}/api/userCertificates/${id}" "${auth_hdr[@]}")
    echo "    DELETE ${id} -> HTTP ${code}"
  done
fi

echo "[*] 完了 (name=${CERT_NAME})"
