import re
def split_body(d):
    s=d.index('<w:body>')+8; e=d.index('</w:body>')
    body=d[s:e]; i=0; items=[]
    while i<len(body):
        m=re.match(r'<(w:p|w:tbl|w:sectPr)\b',body[i:])
        if not m:
            j=body.find('<',i+1); i=j if j>0 else len(body); continue
        tag=m.group(1)
        if tag=='w:sectPr':
            j=body.index('</w:sectPr>',i)+len('</w:sectPr>')
        else:
            depth=0
            pat=re.compile(r'<(/?)%s(?=[\s>/])[^>]*?(/?)>'%tag)
            for mm in pat.finditer(body,i):
                if mm.group(1)=='' and mm.group(2)=='': depth+=1
                elif mm.group(1)=='/': depth-=1
                if depth==0: j=mm.end(); break
        items.append((tag,body[i:j])); i=j
    return d[:s], items, d[e:]
