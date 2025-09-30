import re, io
u = io.open(r"api/service/urls.py",'r',encoding='utf-8',errors='ignore').read()
imp_block = re.search(r'from \\.views import \\((.*?)\\)\\s*', u, re.S)
print('FOUND', bool(imp_block))
if imp_block:
    print(imp_block.group(1))
