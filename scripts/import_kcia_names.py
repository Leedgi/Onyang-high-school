"""유지보수 전용: 원본 PDF를 재배포하지 않고 표의 셀 경계로 명칭을 대조한다."""
from pathlib import Path
import xml.etree.ElementTree as ET
from pypdf import PdfReader
from pypdf.generic import ContentStream
import re,bisect,json
ns='{http://www.w3.org/1999/xhtml}'
import argparse, csv, hashlib
parser=argparse.ArgumentParser(description="검토한 KCIA PDF와 pdftotext -bbox 결과에서 명칭 사실만 추출")
parser.add_argument('pdf');parser.add_argument('bbox');parser.add_argument('output')
a=parser.parse_args()
metadata=json.loads(Path('data/reviewed/kcia_source_input.json').read_text(encoding='utf-8'))
if hashlib.sha256(Path(a.pdf).read_bytes()).hexdigest()!=metadata['pdf_sha256']:
 raise ValueError('검토한 PDF 체크섬이 아닙니다. 새 자료는 별도 검토가 필요합니다.')
pdf=PdfReader(a.pdf);rows=[];count=0
for event,page in ET.iterparse(a.bbox,events=('end',)):
 if page.tag!=ns+'page':continue
 h=float(page.get('height'));p=pdf.pages[count];count+=1
 words=[(float(w.get('xMin')),float(w.get('yMin')),float(w.get('xMax')),float(w.get('yMax')),w.text or '') for w in page.iter(ns+'word')]
 anchors=sorted([((y+y2)/2,int(t)) for x,y,x2,y2,t in words if 50<x<84 and x2<90 and re.fullmatch(r'\d{1,5}',t)])
 rects=[]
 boundaries=[]
 for args,op in ContentStream(p.get_contents(),pdf).operations:
  if op==b're':
   x,y,w,rh=map(float,args)
   if 45<x<790 and w>150 and rh>2:rects.append((h-y-rh,h-y,rh))
   if 45<x<65 and w>700 and 0<rh<1.5:boundaries.append(h-y-rh/2)
 for cy,code in anchors:
  borders=sorted(set(round(v,2) for v in boundaries))
  above=[v for v in borders if v<cy];below=[v for v in borders if v>cy]
  bands=[(max(above),min(below),min(below)-max(above))] if above and below else [rect for rect in rects if rect[0]<=cy<=rect[1] and sum(rect[0]<=a<=rect[1] for a,_ in anchors)==1]
  assert bands,(count,code)
  top,bottom,_=min(bands,key=lambda a:a[2]);cells=[[]for _ in range(4)]
  assert sum(top<=a<=bottom for a,_ in anchors)==1,(count,code,top,bottom)
  for x,y,x2,y2,text in words:
   if 90<=x<790 and top<=(y+y2)/2<=bottom:cells[bisect.bisect_right([264,439,613],x)].append((round(y,1),x,text))
  values=[' '.join(t for y,x,t in sorted(cell)).strip() for cell in cells]
  assert values[0],(count,code)
  rows.append(dict(zip(['kcia_id','name','inci','old_name','old_inci','page'],[str(code),*values,count])))
 page.clear()
assert count==len(pdf.pages)==1578
assert len(rows)==22021 and len({r['kcia_id'] for r in rows})==len(rows)
with Path(a.output).open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['kcia_id','name','inci','old_name','old_inci','page'],lineterminator='\n');w.writeheader();w.writerows(rows)
print('추출 명칭 행:',len(rows))
