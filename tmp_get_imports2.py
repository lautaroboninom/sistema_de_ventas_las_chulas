import io
u=io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read().splitlines()
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

# remove comments
clean=[]
for l in names:
    if '#' in l:
        l=l.split('#',1)[0]
    clean.append(l)
body='\n'.join(clean)
imports=[n.strip() for n in body.split(',') if n.strip()]
print('IMPORTS_N=',len(imports))
for n in imports:
    print(n)
