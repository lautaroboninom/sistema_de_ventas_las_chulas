import io,re
path=r"api/service/urls.py"
s=io.open(path,'r',encoding='utf-8',errors='ignore').read()
# Names from motivos_view
mv=io.open(r"api/service/motivos_view.py",'r',encoding='utf-8',errors='ignore').read()
motivo_exports=set(re.findall(r"\nclass\s+(\w+)\s*\(", mv))|set(re.findall(r"\ndef\s+(\w+)\s*\(", mv))
# Names defined in views
v=io.open(r"api/service/views.py",'r',encoding='utf-8',errors='ignore').read()
view_names=set(re.findall(r"\nclass\s+(\w+)\s*\(", v))|set(re.findall(r"\ndef\s+(\w+)\s*\(", v))

lines=s.splitlines()
start=end=None
for i,l in enumerate(lines):
    if l.strip().startswith('from .views import ('):
        start=i
        for j in range(i+1,len(lines)):
            if lines[j].strip()==')':
                end=j
                break
        break
assert start is not None and end is not None
body_lines=lines[start+1:end]
body_no_comments=[l.split('#',1)[0] for l in body_lines]
imports=[]
for part in ','.join(body_no_comments).split(','):
    n=part.strip()
    if n:
        imports.append(n)
missing=[n for n in imports if (n not in view_names)]
keep_external={'CatalogoMotivosView'} & set(missing)
missing=[n for n in missing if n not in keep_external]
new_imports=[]; seen=set()
for n in imports:
    if n in missing: continue
    if n in seen: continue
    seen.add(n); new_imports.append(n)

indent='    '
new_block=['from .views import (']
for n in new_imports:
    new_block.append(indent+n+",")
new_block.append(')')
new_lines=lines[:start]+new_block+lines[end+1:]

usages=set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.as_view\(", s))
extra_remove=set()
for u in usages:
    if (u not in view_names) and (u not in motivo_exports):
        extra_remove.add(u)
remove_names=set(missing)|extra_remove
final=[]
for l in new_lines:
    if 'path(' in l and any((name+".as_view(") in l for name in remove_names):
        continue
    final.append(l)
io.open(path,'w',encoding='utf-8').write('\n'.join(final))
print('REMOVED',sorted(remove_names))
