import re, io
text = io.open(r"api/service/views.py",'r',encoding='utf-8',errors='ignore').read()
classes = set(re.findall(r'\nclass\s+(\w+)\s*\(', text))
funcs   = set(re.findall(r'\ndef\s+(\w+)\s*\(', text))
print('CLASSES', len(classes))
print('FUNCS', len(funcs))
all_names = classes|funcs
u = io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read().splitlines()
collect=False
names=[]
for line in u:
    if not collect and line.strip().startswith('from .views import ('):
        collect=True
        continue
    if collect:
        if line.strip()==')':
            break
        names.append(line)
body='\n'.join([l.split('#',1)[0] for l in names])
imports=[n.strip() for n in body.split(',') if n.strip()]
missing=[n for n in imports if n not in all_names]
print('MISSING', len(missing))
for n in missing:
    print(n)
