#!/usr/bin/env python3
import os
import re
import sys

env_var = sys.argv[1]
val = os.environ.get(env_var, '')
if not val:
    sys.exit(1)

pem = re.sub(r'(-----(?:BEGIN|END) [A-Z ]+-----)', lambda m: '\n' + m.group(0) + '\n', val)
pem = re.sub(r' ', '\n', pem)
pem = re.sub(r'\n+', '\n', pem).strip()
print(pem)
