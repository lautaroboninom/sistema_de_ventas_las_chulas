import io
u=io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read().splitlines()
collect=False
names=[]
for line in u:
    if line.strip().startswith('from .views import ('):
        collect=True
        idx=line.find('(')
        rest=line[idx+1:]
        if rest.strip():
            names.append(rest)
        continue
    if collect:
        if ')' in line:
            before=line.split(')')[0]
            if before.strip():
                names.append(before)
            break
        names.append(line)

body='\n'.join(names)
body='\n'.join([l.split('#')[0] for l in body.splitlines()])
imports=[n.strip() for n in body.split(',') if n.strip()]
print('IMPORTS_N=',len(imports))
for n in imports:
    print(n)
