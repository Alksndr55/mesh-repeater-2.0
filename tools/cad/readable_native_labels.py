"""Readable presentation of native KiCad assembly SVG, without CAD redrawing."""
from pathlib import Path
import argparse,json,xml.etree.ElementTree as ET

def build(directory):
    ns='http://www.w3.org/2000/svg'; ET.register_namespace('',ns); report=[]
    for source in directory.glob('*_assembly.svg'):
        doc=ET.parse(source); root=doc.getroot(); parent={c:p for p in root.iter() for c in p}; removed=0
        for e in list(root.iter()):
            if e.attrib.get('class')=='stroked-text' and '#AFAFAF' in parent[e].attrib.get('style','').upper():
                parent[e].remove(e); removed+=1
        import re
        for e in root.iter():
            for key,value in list(e.attrib.items()):
                e.attrib[key]=re.sub(r'#[0-9a-fA-F]{6}',lambda m:m[0] if m[0].upper() in ('#AFAFAF','#000000','#FFFFFF') else '#183B56',value)
        target=source.with_name(source.name.replace('_assembly.svg','_labels.svg')); doc.write(target,encoding='utf-8',xml_declaration=True)
        report.append(dict(source=source.name,output=target.name,unprinted_Fab_text_removed=removed))
    (directory/'label_view_method.json').write_text(json.dumps(dict(method='Exact native SVG paths; unprinted Fab text hidden; actual silk recolored for readability; gray Fab body geometry retained',views=report),indent=2),'utf-8')
    print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('directory',type=Path); a=p.parse_args(); build(a.directory)
