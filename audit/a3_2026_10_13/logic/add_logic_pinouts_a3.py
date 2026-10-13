"""Keep actual LOGIC connector pin maps next to their owner, no group scales."""
from label_logic_a3 import *

def main():
    b=k.LoadBoard(str(PCB));HELD.append(b)
    existing=[mm_box(t) for t in b.GetDrawings() if isinstance(t,k.PCB_TEXT)
              and t.GetLayer()==k.B_SilkS]
    pads=[mm_box(p) for f in b.GetFootprints() for p in f.Pads() if p.IsOnLayer(k.B_Mask)]
    specs=[
        ('J3','J3 I2C\n1 3V3 2 GND\n3 SCL 4 SDA',(80.5,23.6)),
        ('J4','J4 GPS\n1 NC 2 NC\n3 NC 4 RX\n5 TX 6 BACKUP\n7 POWER 8 GND',(52,9.5)),
        ('J5','J5 UART\n1 GND\n2 3V3\n3 TX\n4 RX',(6.5,14.31)),
        ('J10','J10 ISP\n1 MISO 2 3V3\n3 SCK 4 MOSI\n5 RST 6 GND',(35,40.9)),
        ('J13','1RF 2GND',(30,4.25)),
        ('J201','J201 1/3 SYS 5/7 RADIO\n2/4/6 GND 8 NC\n9 BAT 10 SDA\n11 MODE 12 SCL',(70.5,55.9)),
        ('branding','Designed by @Alksndritm',(44,52)),
    ]
    report=[]
    for owner,label,at in specs:
        accepted=None
        for dx,dy in ((0,0),(.2,0),(-.2,0),(0,.2),(0,-.2),(.5,0),(-.5,0),(0,.5),(0,-.5)):
            t=text(b,label,(at[0]+dx,at[1]+dy),0,k.B_SilkS,.8);bb=mm_box(t)
            if bb[0]<.35 or bb[1]<.35 or bb[2]>89.65 or bb[3]>59.65:continue
            if any(overlap(bb,p,.12) for p in pads):continue
            if any(overlap(bb,p,.12) for p in existing):continue
            accepted=t;break
        if accepted is None:raise RuntimeError('No clear local legend for '+owner)
        b.Add(accepted);existing.append(mm_box(accepted))
        report.append(dict(owner=owner,text=label,at=xy(accepted.GetPosition()),uuid=uid(accepted)))
    k.SaveBoard(str(PCB),b)
    (OUT/'pinouts_branding.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    check('pinouts_final')

if __name__=='__main__':main()
