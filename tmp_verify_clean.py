import io,re
u=io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read()
v=io.open(r"api/service/views.py",'r',encoding='utf-8',errors='ignore').read()
imports=[]
collect=False
for l in u.splitlines():
    if l.strip().startswith('from .views import ('):
        collect=True
        continue
    if collect:
        if l.strip()==')':
            break
        imports.append(l)
body='\n'.join([l.split('#',1)[0] for l in imports])
imp=[n.strip() for n in body.split(',') if n.strip()]
view_names=set(re.findall(r"\nclass\s+(\w+)\s*\(", v))|set(re.findall(r"\ndef\s+(\w+)\s*\(", v))
missing=[n for n in imp if n not in view_names]
print('Remaining imports not in views:',missing)
# Check urlpatterns
usages=set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.as_view\(", u))
extra=[n for n in usages if n not in view_names and n!='CatalogoMotivosView']
print('Remaining routes not implemented:', extra)
