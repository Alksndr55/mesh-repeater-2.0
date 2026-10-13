from pathlib import Path
import json,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Circle,Rectangle
OUT=Path(__file__).parent;data=json.loads((OUT/'MECHANICAL_RF_native.json').read_text(encoding='utf8'))
for name,region,nets in [('Logic',(29,59,0,27),['ANT']),('Power',(37,52,15,26),['LX','SYS_PRE','BAT_SYS'])]:
 b=data['boards'][name];fig,axs=plt.subplots(1,2,figsize=(14,6))
 for ax,layer in zip(axs,['F.Cu','B.Cu']):
  for p in b['gnd_copper'][layer]:
   ax.add_patch(Polygon(p['shell'],facecolor='#c0d6bd',edgecolor='#477046',linewidth=.4))
   for h in p['holes']:ax.add_patch(Polygon(h,facecolor='white',edgecolor='#477046',linewidth=.3))
  for t in b['tracks']:
   if t['kind']=='via':
    if region[0]<t['at'][0]<region[1] and region[2]<t['at'][1]<region[3]:
     ax.add_patch(Circle(t['at'],t['diameter_mm']/2,facecolor='#477046' if t['net']=='GND' else '#f0b45c'));ax.add_patch(Circle(t['at'],t['drill_mm']/2,facecolor='white'))
   elif t['layer']==layer and any(n in t['net'] for n in nets):ax.plot(*zip(t['start'],t['end']),color='#bc3434',linewidth=t['width_mm']*3.4,solid_capstyle='round')
  for ref,f in b['footprints'].items():
   if region[0]<=f['at'][0]<=region[1] and region[2]<=f['at'][1]<=region[3]:ax.text(*f['at'],ref,fontsize=8,color='#17203e',ha='center',va='bottom')
   for p in f['pads']:
    x,y=p['at'];sx,sy=p['size']
    if not(region[0]<=x<=region[1] and region[2]<=y<=region[3]):continue
    a=math.radians(f['angle']);corners=[]
    for dx,dy in [(-sx/2,-sy/2),(sx/2,-sy/2),(sx/2,sy/2),(-sx/2,sy/2)]:corners.append((x+dx*math.cos(a)+dy*math.sin(a),y-dx*math.sin(a)+dy*math.cos(a)))
    ax.add_patch(Polygon(corners,facecolor='#b35f54' if any(n in p['net'] for n in nets) else 'none',edgecolor='#444444',linewidth=.5))
    if p['drill'][0]:ax.add_patch(Circle((x,y),p['drill'][0]/2,facecolor='white',edgecolor='#444444',linewidth=.4))
  ax.set_xlim(region[:2]);ax.set_ylim(region[3],region[2]);ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_title(name+' '+layer+' saved ground and selected nets');ax.set_xlabel('Native X, mm');ax.set_ylabel('Native Y, mm')
 fig.tight_layout();fig.savefig(OUT/f'MECHANICAL_RF_{name}_copper.png',dpi=180);plt.close(fig)
