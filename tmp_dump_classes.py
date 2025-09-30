import io,re
text=io.open(r"api/service/views.py",'rb').read().decode('utf-8','ignore')
for m in re.finditer(r"\nclass\s+(\w+)\s*\((.*?)\):", text, re.S):
    name=m.group(1)
    if name in {'IngresoDetalleView','GeneralEquiposView','AprobadosParaRepararView','PendientesGeneralView'}:
        i=m.start()
        snippet=text[i:i+1200]
        print('====',name)
        print(snippet)
