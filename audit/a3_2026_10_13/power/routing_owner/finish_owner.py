from pathlib import Path
import json,sys,math
from complete_owner_routes import ROOT,HERE,PCB,KEEP,k,save,drc,pad,exact,lookup
import router

def main():
 log=[]
 for iteration in range(6):
  data=drc('trim_'+str(iteration));dangling=[v for v in data['violations']if v['type']in('track_dangling','via_dangling')]
  if not dangling:break
  b=k.LoadBoard(str(PCB));KEEP.append(b);items=lookup(b)
  for issue in dangling:
   for item in issue['items']:
    t=items.get(item['uuid'])
    if t is not None:
     log.append({'uuid':item['uuid'],'net':t.GetNetname(),'iteration':iteration});b.Remove(t);KEEP.append(t)
  p=pad(b,'TP6','1');p.SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
  save(b)
 (HERE/'dangling_trim.json').write_text(json.dumps(log,indent=2),encoding='utf8')
 b=k.LoadBoard(str(PCB));KEEP.append(b)
 # Raw battery ADC feed is routed before Kelvin taps so it cannot choose a
 # monitor resistor as its main graph source. It carries only the ADC divider.
 routes=[]
 routes.append(exact(b,'BAT',pad(b,'R71','2'),pad(b,'J101','9'),.2))
 # Dense neighbouring 2512 lands require a 0.15mm low-current compensation
 # branch rather than forcing a 0.2mm candidate through blocked endpoints.
 a,z=pad(b,'U1','9'),pad(b,'R6','1')
 assert a.GetNetname()==z.GetNetname()=='Net-(U1-COM2)'
 try:routes.append(exact(b,a.GetNetname(),a,z,.15))
 except RuntimeError:
  router.CLEAR=.205
  routes.append(exact(b,a.GetNetname(),a,z,.15))
  router.CLEAR=.225
 save(b)
 (HERE/'finish_routes.json').write_text(json.dumps(routes,indent=2),encoding='utf8')
if __name__=='__main__':main()
