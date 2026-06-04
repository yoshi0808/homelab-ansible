#!/usr/bin/env python3
import os
import re
import sys

env_var = sys.argv[1]
val = os.environ.get(env_var, '')
if not val:
    sys.exit(1)

# -----BEGIN ... ----- と -----END ... ----- の間のスペースを改行に変換
# ただしヘッダ/フッタ内のスペースは保持する
parts = re.split(r'(-----(?:BEGIN|END)[^-]*-----)', val)
result = []
for part in parts:
    if part.startswith('-----'):
        result.append(part)
    else:
        # Base64部分のスペースを改行に変換
        result.append(part.strip().replace(' ', '\n'))

pem = '\n'.join(p for p in result if p.strip())
print(pem)
