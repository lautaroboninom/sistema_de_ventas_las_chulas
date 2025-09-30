import re, io
u = io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read()
imp_block = re.search(r'from \.views import \((.*?)\)\s*', u, re.S)
imports = []
if imp_block:
    body = imp_block.group(1)
    body = re.sub(r'#.*','',body)
    for name in body.split(','):
        n = name.strip()
        if not n: continue
        imports.append(n)
print('IMPORTS:', len(imports))
print('\n'.join(imports))

usages = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\.as_view\(', u))
print('USAGES:', len(usages))
print('\n'.join(sorted(usages)))
