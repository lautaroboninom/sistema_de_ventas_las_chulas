import io
u=io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read().splitlines()
collect=False
names=[]
start_idx=None
end_idx=None
for i,line in enumerate(u):
    if not collect and line.strip().startswith('from .views import ('):
        collect=True
        start_idx=i
        idx=line.find('(')
        rest=line[idx+1:]
        if rest.strip():
            names.append((i,rest))
        continue
    if collect:
        if ')' in line:
            before=line.split(')')[0]
            if before.strip():
                names.append((i,before))
            end_idx=i
            break
        names.append((i,line))

print('start',start_idx,'end',end_idx)
for i,l in names:
    print(i+1, l)
