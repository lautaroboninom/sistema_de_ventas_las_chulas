import re, io
text=io.open(r"api/service/views.py",'rb').read().decode('utf-8','ignore')
classes=set(re.findall(r"\nclass\s+(\w+)\s*\(", text))
funcs=set(re.findall(r"\ndef\s+(\w+)\s*\(", text))
all_names=classes|funcs
u=io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read()
usages=set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.as_view\(", u))
missing_used=sorted(list(usages - all_names))
print('MISSING_USED', len(missing_used))
for n in missing_used:
    print(n)

# Also compute imported-but-missing
lines=u.splitlines()
collect=False
names=[]
for line in lines:
    if not collect and line.strip().startswith('from .views import ('):
        collect=True
        continue
    if collect:
        if line.strip()==')':
            break
        names.append(line)
body='\n'.join([l.split('#',1)[0] for l in names])
imports=[n.strip() for n in body.split(',') if n.strip()]
missing_imports=sorted([n for n in imports if n not in all_names])
print('MISSING_IMPORTS', len(missing_imports))
for n in missing_imports:
    print(n)

# Duplicates in imports
from collections import Counter
cnt=Counter(imports)
dups=[n for n,c in cnt.items() if c>1]
print('DUPS',dups)
