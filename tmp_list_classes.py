import re, io
text = io.open(r"api/service/views.py", 'rb').read().decode('utf-8','ignore')
classes = re.findall(r"\nclass\s+(\w+)\s*\(", text)
for c in classes:
    print(c)
print('TOTAL', len(classes))
