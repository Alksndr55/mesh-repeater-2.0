from pathlib import Path
from urllib.request import urlopen,Request
import json,hashlib
OUT=Path(__file__).parent
sources={
'Heltec_RA62_Rev1p1':'https://resource.heltec.cn/download/HT-RA62/HT-RA62(Rev1.1).pdf',
'Heltec_RA62_reference':'https://resource.heltec.cn/download/HT-RA62/HT-RA62_Reference_design.pdf',
'Heltec_RA62_schematic':'https://resource.heltec.cn/download/HT-RA62/HT-RA62_Schematic_diagram.pdf',
'Abracon_S869M000S003':'https://abracon.com/datasheets/AEL-Crystals/PN/S869M000S003.pdf',
'KLS_SMA002':'https://img.klsele.com/admin/product_upload/20250828165703L-KLS1-SMA002-B%26KLS1-SMA002-B-1.27.pdf'}
result={}
for name,url in sources.items():
 try:
  data=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();path=OUT/f'MECHANICAL_RF_{name}.pdf';path.write_bytes(data)
  result[name]={'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'path':path.name};print(name,len(data))
 except Exception as e:result[name]={'url':url,'error':str(e)};print(name,str(e))
(OUT/'MECHANICAL_RF_sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
