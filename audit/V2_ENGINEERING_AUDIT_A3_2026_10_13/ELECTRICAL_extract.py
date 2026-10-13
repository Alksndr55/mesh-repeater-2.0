"""Read-only extraction from actual A3 native CAD; writes audit evidence only."""
from pathlib import Path
import json, re, xml.etree.ElementTree as ET, math
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
def parse(path):
    txt = path.read_text(encoding='utf-8')
    stack = []; root = None
    for m in TOK.finditer(txt):
        t=m.group()
        if t=='(':
            n=[]
            if stack: stack[-1].append(n)
            else: root=n
            stack.append(n)
        elif t==')': stack.pop()
        else: stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return root
def nodes(n,key): return [x for x in n if isinstance(x,list) and x and x[0]==key]
def one(n,key): return next(iter(nodes(n,key)),None)
def prop(n,key): return next((x[2] for x in nodes(n,'property') if x[1]==key),None)
def floats(n,key):
    x=one(n,key)
    return x[1:] if x else None
e={}
for name in ('Power','Logic'):
    d=ROOT/'design'/f'MeshRepeater2_{name}'
    model=json.loads((d/'model.json').read_text(encoding='utf-8'))
    mp={p['ref']:p for p in model['parts']}
    board=parse(d/f'MeshRepeater2_{name}.kicad_pcb')
    pinfo={}
    for fp in nodes(board,'footprint'):
        ref=prop(fp,'Reference')
        if ref not in mp: continue
        pads=[]
        for pad in nodes(fp,'pad'):
            net=one(pad,'net')
            pads.append({'pin':pad[1],'net':net[-1] if net else None,'at':floats(pad,'at'),'size':floats(pad,'size'),'drill':floats(pad,'drill')})
        pinfo[ref]={'board_at':floats(fp,'at'),'pads':pads,'model_nets':mp[ref]['nets'],'value':mp[ref]['value'],'mpn':mp[ref].get('mpn'),'lto_value':mp[ref].get('value_lto2s'),'lto_mpn':mp[ref].get('mpn_lto2s'),'fit':{k:mp[ref].get(k) for k in ('fit_naion','fit_lto2s','fit_naion_no_cold')},'schematic':[]}
    for sch in d.glob('*.kicad_sch'):
        txt=sch.read_text(encoding='utf-8')
        for sym in nodes(parse(sch),'symbol'):
            ref=prop(sym,'Reference')
            if ref not in pinfo: continue
            needle=f'(property "Reference" "{ref}"'
            offset=txt.find(needle)
            pinfo[ref]['schematic'].append({'file':str(sch.relative_to(ROOT)),'line':txt[:offset].count('\n')+1,'at':floats(sym,'at'),'value':prop(sym,'Value'),'mpn':prop(sym,'MPN'),'lto_value':prop(sym,'Value_LTO_2S')})
    netxml=ET.parse(OUT/f'{name.upper()}_netlist.xml')
    nets={n.attrib['name']:[x.attrib['ref']+'.'+x.attrib['pin'] for x in n.findall('node')] for n in netxml.findall('./nets/net')}
    e[name]={'parts':pinfo,'native_nets':nets}

# Analytic corner calculations; no transient simulation or bench measurement.
tol=.001; tc=25e-6; dt=65; rt=tol+tc*dt
def cv(top,bottom=100000):
    return {'nominal_V':2.416*(1+top/bottom)+50e-9*top,
            'min_V':2.392*(1+top*(1-rt)/(bottom*(1+rt))),
            'max_V':2.44*(1+top*(1+rt)/(bottom*(1-rt)))+300e-9*top*(1+rt)}
c={'type':'analytic DC corners only; no simulation/bench',
   'CN3722':{'resistor_error':rt,'delta_T_C':dt,'Na':cv(61900),'LTO':cv(121000)},
   'balancer':{'top_ohm':122490,'bottom_ohm':100000,'ballast_ohm':2,'reference_V':1.24,'Iref_nom_A':.15e-6},
   'LC':{'L_each_H':2.4e-6,'L_tol':.3,'C_each_nom_F':.001,'C_each_required_F':.00033,'Rfeed_ohm':.047,'Rdamper_each_ohm':.022},
   'R71':{'R_ohm':.1,'tol':.01,'TCR_per_C':600e-6,'I_nom_A':1.25,'P_nom_W':1.25**2*.1,'drop_nom_V':1.25*.1,'P_at_4A_W':4**2*.1},
   'ADC':{'top_ohm':2.2e6,'bottom_ohm':2.2e6,'cap_F':100e-9,'tau_s':1.1e6*100e-9,'settle_1pct_s':-math.log(.01)*.11,'settle_0p1pct_s':-math.log(.001)*.11},
   'EN':{}}
recovery={'native_topology':'R15.1=BAT(rawbeforeR71); R71.2=BAT,R71.1=BAT_SYS,U2.10=BAT_SYS. R71voltage dropdoesnotdirectlyfeedEN.',
          'datasheet':'TI SLVSEU9D p6 table8.5: EN rising1.07/1.10/1.13V,falling0.97/1.00/1.03V; no separateENhysteresisrow. p5 VIN>1.8VuntilPG; p6 UVLOrising1.6/1.7/1.79V,falling1.2/1.25/1.29VonceVOUT>=1.8V.',
          'Pout_W':3.3*.5,'eta_assumed':.9,'R71_ohm':.1,'EN_hysteresis':{},'cases':[],
          'LCbank_energy_min_J':.5*.00066*3.3**2,'LCbank_charge_min_C':.00066*3.3,
          'note':'Analyticconstantpower/resistivesourceestimatesonly. eta90%assumptionnotlowBATguarantee; actualstartup/currentlimit/celldynamicsunknown.'}
for label,top in [('Na',40200),('LTO',130000)]:
    rat=1+top/49900; lo=1+top*.999/(49900*1.001); hi=1+top*1.001/(49900*.999)
    recovery['EN_hysteresis'][label]={'nominal_raw_V':.1*rat,'derived_min_raw_V':.04*lo,'derived_max_raw_V':.16*hi,'assumptions':'R0.1%; arithmeticboundsfromindependentENthresholdrows; equalENleakageatboththresholds, noTCR.'}
def supplycase(eocv,esr):
    rt=.1+esr; p=1.65/.9; disc=eocv**2-4*rt*p
    if disc<0: return {'Eoc_V':eocv,'cell_ESR_ohm':esr,'static_solution':'noneforassumedconstantpower'}
    current=(eocv-math.sqrt(disc))/(2*rt)
    return {'Eoc_V':eocv,'cell_ESR_ohm':esr,'Ibat_A':current,'raw_BAT_V':eocv-current*esr,'VIN_BAT_SYS_V':eocv-current*rt,'drop_R71_V':current*.1}
for eocv,esr in [(1.8,0),(1.1*(1+40200/49900),0),(1.1*(1+40200/49900),.2),(2.0,.2),(1.1*(1+130000/49900),0)]: recovery['cases'].append(supplycase(eocv,esr))
recovery['additional_input_current_to_charge_LC_2ms_A']=recovery['LCbank_energy_min_J']/(.9*1.986*0.002)
(OUT/'ELECTRICAL_RECOVERY.json').write_text(json.dumps(recovery,ensure_ascii=False,indent=2),encoding='utf-8')
for name,d in c['CN3722'].items():
    if isinstance(d,dict): d['no_battery_OVP_nom_V']=d['nominal_V']*1.08; d['no_battery_OVP_max_V']=d['max_V']*1.1
b=c['balancer']; b['Vz_nom_V']=1.24*(1+122490/100000)+.15e-6*122490
b['Vz_min_25C_V']=1.228*(1+122490*.999/(100000*1.001))
b['Vz_min_fulltemp_V']=1.215*(1+122490*.999/(100000*1.001))
for v in (2.75,2.85): b[f'I_nom_at_cell_{v}V_A']=max(0,(v-b['Vz_nom_V'])/2-b['Vz_nom_V']/222490)
b['I_at_2p75V_lowref_25C_A']=(2.75-b['Vz_min_25C_V'])/(2*.99)-2.75/222490
b['I_at_2p75V_lowref_fulltemp_A']=(2.75-b['Vz_min_fulltemp_V'])/(2*.99)-2.75/222490
for label,top in [('Na',40200),('LTO',130000)]:
    lo=1+top*.999/(49900*1.001); hi=1+top*1.001/(49900*.999)
    c['EN'][label]={'off_nom_V':1+top/49900,'off_min_V':.97*lo,'off_max_V':1.03*hi+.2e-6*top*1.001,'on_min_V':1.07*lo,'on_max_V':1.13*hi+.2e-6*top*1.001,'note':'25C resistor tolerance only; positive input current0..0.2uA. TCR unknown for LTO top.'}
for key in ('C_each_nom_F','C_each_required_F'): c['LC'][f'f0_{key}_Hz']=1/(2*math.pi*math.sqrt(2.4e-6*c['LC'][key])); c['LC'][f'Z0_{key}_ohm']=math.sqrt(2.4e-6/c['LC'][key])
# Passive frequency-domain calculation only: SYS_PRE is assumed ideal AC source.
# Excludes TPS63802 control, wiring/contacts, ESR/ESL, radio dynamic load and EMI.
lc=[]
for capacitance in (.00033,.001):
    for l1 in (2.4e-6*.7,2.4e-6,2.4e-6*1.3):
        for l2 in (2.4e-6*.7,2.4e-6,2.4e-6*1.3):
            gainmax=(0,0); zoutmax=(0,0)
            for i in range(2001):
                freq=10**(1+i*4/2000); s=2j*math.pi*freq
                zc=.022+1/(s*capacitance); za=.047+.0105+s*l1; zb=.0105+s*l2
                zm=1/(1/zc+1/(zb+zc)); h=zm/(za+zm)*zc/(zb+zc)
                zo=1/(1/zc+1/(zb+1/(1/zc+1/za)))
                if abs(h)>gainmax[0]: gainmax=(abs(h),freq)
                if abs(zo)>zoutmax[0]: zoutmax=(abs(zo),freq)
            lc.append({'C_each_F':capacitance,'L1_H':l1,'L2_H':l2,'gain_peak':gainmax[0],'gain_peak_Hz':gainmax[1],'Zout_peak_ohm':zoutmax[0],'Zout_peak_Hz':zoutmax[1]})
(OUT/'ELECTRICAL_LC_PASSIVE.json').write_text(json.dumps({'method':'Complex impedances; log sweep10Hz..100kHz,2001points/corner,18corners; ideal regulatedSYS_PRE. Linear passive AC calculation, not converter/transient simulation orbench.', 'DCR_each_ohm':.0105,'Rfeed_ohm':.047,'Rdamper_each_ohm':.022,'omitted':['TPS63802loop/outputimpedance','wiring/contactreturn','capacitorESR/ESL/biascurve','actualradio/GPSload'], 'corners':lc},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'ELECTRICAL_native_evidence.json').write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'ELECTRICAL_calculations.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(c,ensure_ascii=False,indent=2))
