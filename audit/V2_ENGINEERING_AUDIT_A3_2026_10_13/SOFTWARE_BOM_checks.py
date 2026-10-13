"""Read-only independent firmware/BOM/export checks; outputs only beside this file."""
from pathlib import Path
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows = list(csv.DictReader((ROOT / 'bom/V2_A3_COMPONENT_BOM.csv').open(encoding='utf-8-sig')))
models = {b: json.loads((ROOT / f'design/MeshRepeater2_{b.title()}/model.json').read_text(encoding='utf-8')) for b in ('POWER', 'LOGIC')}
parts = {(b,p['ref']): p for b,m in models.items() for p in m['parts']}
disagreements = []
for row in rows:
    p = parts[(row['Board'],row['Reference'])]
    for col,key in [('Saved_Model_Footprint','footprint'),('Value_NaIon_COLD','value'),('MPN_NaIon_COLD','mpn'),('Value_NaIon_NoCOLD','value_naion_no_cold'),('MPN_NaIon_NoCOLD','mpn_naion_no_cold'),('Value_LTO_2S','value_lto2s'),('MPN_LTO_2S','mpn_lto2s')]:
        value = p.get(key,p.get(key.split('_')[0],''))
        if row[col] != str(value):
            disagreements.append([row['Board'],row['Reference'],col,row[col],value])
    for variant,key in [('NaIon_COLD','fit_naion'),('NaIon_NoCOLD','fit_naion_no_cold'),('LTO_2S','fit_lto2s')]:
        if (row['Fit_'+variant]=='yes') != bool(p.get(key)):
            disagreements.append([row['Board'],row['Reference'],'Fit_'+variant,row['Fit_'+variant],p.get(key)])
native = {}
for b in ('POWER','LOGIC'):
    doc = ET.parse(OUT / (b+'_netlist.xml')).getroot()
    native[b] = {'nets':[{**n.attrib,'nodes':[x.attrib for x in n.findall('node')]} for n in doc.findall('./nets/net')], 'components':{c.attrib['ref']:{'value':c.findtext('value'),'footprint':c.findtext('footprint')} for c in doc.findall('./components/comp')}}
    for row in rows:
        if row['Board'] != b: continue
        c = native[b]['components'].get(row['Reference'])
        if c is None:
            disagreements.append([b,row['Reference'],'missing in XML'])
        elif c['value'] != row['Value_NaIon_COLD'] or c['footprint'] != row['Saved_Model_Footprint']:
            disagreements.append([b,row['Reference'],'native XML default',c])
exports = {}
for b in ('POWER','LOGIC','SHIELD'):
    path = ROOT / f'output/{b}/MeshRepeater2_{b.title()}_exports.json'
    j = json.loads(path.read_text(encoding='utf-8'))
    exports[b] = {'pcb_sha_match':sha(ROOT/j['pcb'])==j['sha256'],'artifact_count':len(j['artifacts']),'bad_artifacts':[a['path'] for a in j['artifacts'] if not (ROOT/a['path']).exists() or sha(ROOT/a['path'])!=a['sha256']]}
class TextParser(HTMLParser):
    def __init__(self):super().__init__();self.ts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip += 1
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,t):
        if not self.skip and t.strip():self.ts.append(t.strip())
cards=[]
for p in sorted(OUT.glob('SOFTWARE_BOM_DAN_*.html')):
    parser=TextParser();parser.feed(p.read_text(encoding='utf-8'))
    text=' '.join(parser.ts)
    main=text.split('Легко оплатить')[0].split('Код товара:')[-1]
    article=p.stem.split('_')[-1]
    # Only inspect the main product, never the recommendation stock below it.
    marker='CHU-4 (XH 04F)' if article=='205451' else 'Код товара: '+article
    pos=text.rfind(marker) if article=='205451' else text.find(marker)
    section=text[pos:pos+550]
    if article=='205451':
        m=re.search('Товара нет в наличии',text)
        section=text[max(m.start()-160,0):m.end()+80] if m else section
    stock=re.search(r'На\s+складе:\s*([\d ]+)',section.replace('\xa0',' '))
    cards.append({'article':article,'retrieved_date':'2026-10-13','stock':int(stock.group(1).replace(' ','')) if stock else None,'out_of_stock':'Товара нет в наличии' in section,'main_product_excerpt':section,'html_sha256':sha(p)})
zip_path=OUT/'SOFTWARE_BOM_MeshCore_source.zip'
z=zipfile.ZipFile(zip_path)
source_queries={}
for name in z.namelist():
    if name.endswith(('.cpp','.h','.ini')):
        t=z.read(name).decode('utf-8',errors='replace')
        hits=[(i,l) for i,l in enumerate(t.splitlines(),1) if any(s in l for s in ('analogReference(','analogSampleTime(','ADC_MULTIPLIER'))]
        if hits and ('/variants/promicro/' in name or '/variants/' not in name):source_queries[name]=hits
source_paths=list(OUT.glob('SOFTWARE_BOM_MeshCore_*'))+list(OUT.glob('SOFTWARE_BOM_nRF52_*'))+list(OUT.glob('SOFTWARE_BOM_Adafruit_*'))+list(OUT.glob('SOFTWARE_BOM_RTClib_*'))+list(OUT.glob('SOFTWARE_BOM_Heltec_*'))+list(OUT.glob('SOFTWARE_BOM_TI_*'))
source_paths += [ROOT/p for p in ('design/watchdog_reference/main.c','design/watchdog_reference/Makefile','design/watchdog_reference/watchdog.hex','bom/V2_A3_COMPONENT_BOM.csv','bom/V2_COMPONENT_BOM.csv','bom/DAN_NEW_PARTS.csv','bom/NOTES_RU.txt','docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md','docs/V2_CHANGES_FROM_S4_16_RU.md','output/pdf/SCHEMATIC_MANIFEST.json')]
sources={str(p.relative_to(ROOT)):sha(p) for p in source_paths if p.is_file()}
result={
    'scope':'A3 read-only subaudit; these checks do not replace full PCB/schematic comparison or a main firmware build',
    'bom':{'row_count':len(rows),'unique_positions':len({(r['Board'],r['Reference']) for r in rows}),'model_count':len(parts),'disagreements':disagreements,'variants':{v:{'fitted_positions':sum(r['Fit_'+v]=='yes' for r in rows),'purchased_components':sum(r['Buy_Component_'+v]=='yes' for r in rows),'unselected_purchased_MPN':[r['Reference'] for r in rows if r['Buy_Component_'+v]=='yes' and ('TBD' in r['MPN_'+v] or 'not selected' in r['MPN_'+v])]} for v in ('NaIon_COLD','NaIon_NoCOLD','LTO_2S')}},
    'logic_interface_nets':[n for n in native['LOGIC']['nets'] if any(x in n['name'] for x in ('GPS','UART','RADIO','WDT','SDA','SCL','MCU_RESET','MODE'))],
    'exports':exports,'dan_cards':cards,
    'watchdog':{'original_hex_sha256':sha(ROOT/'design/watchdog_reference/watchdog.hex'),'rebuilt_hex_sha256':sha(OUT/'SOFTWARE_BOM_watchdog_rebuilt.hex'),'hex_identical':(ROOT/'design/watchdog_reference/watchdog.hex').read_bytes()==(OUT/'SOFTWARE_BOM_watchdog_rebuilt.hex').read_bytes(),'compiler':'AVR GCC 7.3.0 / Arduino atmel3.6.1-arduino7','flash_bytes':406,'ram_bytes':4},
    'main_firmware':{'repository':'https://github.com/meshcore-dev/MeshCore','sha':'a366955cb2f67b8e6842d4f00d2b6a554dddd88a','environment_reviewed':'ProMicro_repeater','source_version':'v1.17.1','archive_file_count':len(z.infolist()),'full_build_executed':False,'limitation':'No PlatformIO command/penv or locked nRF52 dependencies available; source archive reviewed in memory without extraction','adc_override_search':source_queries},
    'pcb_headers':{b:re.search(r'\(title_block(.*?)\n\t\)',(ROOT/f'design/MeshRepeater2_{b.title()}/MeshRepeater2_{b.title()}.kicad_pcb').read_text(encoding='utf-8'),re.S).group(0) for b in ('POWER','LOGIC','SHIELD')},
    'adc_ideal_calculation':{'divider_ratio':2,'reference_volts':0.6,'gain':'1/6','bits':12,'ideal_mV_per_count':3600*2/4096,'stock_mV_per_count':1.815,'stock_error_percent':(1.815/(3600*2/4096)-1)*100,'reading_at_3_915V_ideal':3.915*(1.815/(3600*2/4096)),'assumptions':'Ideal SAADC gain/reference and nominal external 2.2M/2.2M divider; actual cloned board leakage/reference not measured. Positive telemetry error does not establish a charging/UV safety fault.'},
    'source_hashes':sources,
}
if (OUT/'SOFTWARE_BOM_MAIN_BUILD_RESULT.json').exists():
    result['main_firmware'].update({'full_build_executed':True,'full_build_success':False,'attempt_executed':True,'compilation_started':True,'result_manifest':'SOFTWARE_BOM_MAIN_BUILD_RESULT.json','limitation':'Actual isolated PlatformIO attempt reached SDK compilation. Canonical CPLUS_INCLUDE_PATH fixed system-header probe, but ARM assembler cannot create object paths of 262-268 characters on Windows; final firmware not produced.'})
(OUT/'SOFTWARE_BOM_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'bom_disagreements':disagreements,'exports':exports,'watchdog_identical':result['watchdog']['hex_identical'],'dan_stock':[(c['article'],c['stock'],c['out_of_stock']) for c in cards]},ensure_ascii=False))
