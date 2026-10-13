"""Exact A3 authorization on top of the immutable S4.16 and INA219 A2 inputs.

NT2 is physical copper joining the two separately routed supply branches.
Its groups are joined only in a separate legacy projection; stored native
net names remain separate. Moving J11 changes its board identity, not GPIO.
"""
from pathlib import Path
import hashlib
import json
import v2_feature_contract as a2

ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = a2.FEATURE_PATH
A3_FEATURE_PATH = ROOT / 'design/feature_a3_single_face_split_power.json'
NEW_NETS = a2.NEW_NETS
INA_SOIC_PIN_NAMES = a2.INA_SOIC_PIN_NAMES
PINMAP = {'1':'SYS_3V3','2':'GND','3':'SYS_3V3','4':'GND','5':'RADIO_3V3',
          '6':'GND','7':'RADIO_3V3','8':None,'9':'BAT','10':'SDA','11':'MODE','12':'SCL'}
SHUNT_MPN = {'R1':'WSL2512R2800FEA','R40':'WSL2512R0220FEA','R41':'WSL2512R0220FEA',
             'R55':'WSL2512R0470FEA','R56':'RC2512FK-071R8L','R71':'RL2512FK-070R1L'}
SHUNT_FOOTPRINT = {ref: ('Meshcore:R_Vishay_WSL2512_A3' if ref in
                       {'R1','R40','R41','R55'} else 'Meshcore:R_2512_6332Metric')
                   for ref in SHUNT_MPN}
RADIO_OVERRIDES = {'FB1':{'1':'RADIO_3V3','2':'RADIO_LOCAL_3V3'},
                   'M2':{'3':'RADIO_LOCAL_3V3'},
                   'C23':{'1':'RADIO_LOCAL_3V3'},'C24':{'1':'RADIO_LOCAL_3V3'}}


def load_feature(contract_path):
    feature = a2.load_feature(contract_path)
    if not feature:
        raise ValueError('A3 requires the independently preserved A2 INA219 allowance')
    spec = json.loads(A3_FEATURE_PATH.read_text(encoding='utf-8'))
    if spec.get('baseline_contract_sha256') != a2.BASELINE_SHA256 or spec.get('baseline_contract_immutable') is not True:
        raise ValueError('A3 cannot replace its frozen source contract')
    if spec.get('interboard_pinmap') != PINMAP or set(spec.get('references_2512',[])) != set(SHUNT_MPN):
        raise ValueError('Unexpected A3 interconnect/shunt authorization')
    if spec.get('moved_reference') != {'J11':{'from':'LOGIC','to':'POWER'}}:
        raise ValueError('Only J11 is authorized to move between functional boards')
    if spec.get('new_reference') != {'NT2':{'board':'POWER','kind':'NetTie','nets':{'1':'SYS_3V3','2':'RADIO_3V3'}}}:
        raise ValueError('Only the NT2 copper star is an additional A3 position')
    feature = dict(feature)
    feature['a3'] = spec
    return feature


def original_board(ref, board):
    return 'POWER' if ref == 'J11' else board


def expected_value_field(ref, field, old):
    return '1.8R 1% 1W' if ref == 'R56' and field == 'Value_NaIon' else old


def expected_original_nets(board, ref, original, feature):
    expected = a2.expected_original_nets(board, ref, original, feature)
    if board == 'LOGIC':
        expected.update(RADIO_OVERRIDES.get(ref,{}))
    return expected


def feature_checks(models, feature):
    parts={b:{p['ref']:p for p in m['parts']} for b,m in models.items()}
    checks=[]
    def check(name, passed, detail=None):
        checks.append({'name':name,'pass':bool(passed),'detail':detail})
    power, logic = parts['POWER'], parts['LOGIC']
    check('INA219 six added A2 positions remain only POWER',all(r in power and r not in logic for r in NEW_NETS))
    for ref,nets in NEW_NETS.items():
        p=power.get(ref,{})
        check('INA219 exact circuit nets '+ref,p.get('nets')==nets,{'expected':nets,'actual':p.get('nets')})
        value,mpn,kind,fp=a2.NEW_FIELDS[ref]
        physical=p.get('source_footprint_before_v2_graphic_variant',p.get('footprint'))
        check('INA219 exact values, packages and fit variants '+ref,
              p.get('value')==value and p.get('mpn')==mpn and p.get('kind')==kind and physical==fp
              and all(p.get(k) is True for k in ['fit_naion','fit_naion_no_cold','fit_lto2s'])
              and p.get('value_lto2s',value)==value and p.get('value_naion_no_cold',value)==value,
              {'physical_footprint':physical,'expected_footprint':fp})
    for board,ref in [('POWER','J101'),('LOGIC','J201')]:
        check(board+' exact A3 twelve-pin interconnect',parts[board].get(ref,{}).get('nets')==PINMAP)
    check('J11 one removable bridge moves entirely to POWER',power.get('J11',{}).get('nets')=={'1':'FILTER_OUT','2':'SYS_3V3'} and 'J11' not in logic)
    check('NT2 is the only copper SYS/RADIO star',power.get('NT2',{}).get('kind')=='NetTie' and power.get('NT2',{}).get('nets')=={'1':'SYS_3V3','2':'RADIO_3V3'} and 'NT2' not in logic)
    check('Separate RADIO connector branch feeds only FB1 input on LOGIC',
          {(p['ref'],str(n)) for p in logic.values() for n,v in p['nets'].items() if v=='RADIO_3V3'}=={('J201','5'),('J201','7'),('FB1','1')})
    check('Local modem supply feeds only M2/C23/C24 after FB1',
          {(p['ref'],str(n)) for p in logic.values() for n,v in p['nets'].items() if v=='RADIO_LOCAL_3V3'}=={('FB1','2'),('M2','3'),('C23','1'),('C24','1')})
    check('FB1 no longer connects to SYS on LOGIC',logic.get('FB1',{}).get('nets')==RADIO_OVERRIDES['FB1'])
    for ref,mpn in SHUNT_MPN.items():
        p=power.get(ref,{})
        fp=p.get('source_footprint_before_v2_graphic_variant',p.get('footprint'))
        check('A3 exact 2512 package and MPN '+ref,fp==SHUNT_FOOTPRINT[ref] and p.get('mpn')==mpn,{'physical':fp,'expected_physical':SHUNT_FOOTPRINT[ref],'mpn':p.get('mpn')})
    check('R56 cold 1.8R/0R options retain proper 2512 ordering codes',power.get('R56',{}).get('value')=='1.8R 1% 1W' and power.get('R56',{}).get('mpn_lto2s')=='RC2512JK-070RL' and power.get('R56',{}).get('mpn_naion_no_cold')=='RC2512JK-070RL')
    for ref in ['R47','R51']:
        p=power.get(ref,{})
        check('Accepted 2R 0805 balancer remains '+ref,p.get('value')=='2R 1%' and p.get('source_footprint_before_v2_graphic_variant',p.get('footprint'))=='Meshcore:R_0805_2012Metric')
    check('Raw battery endpoints remain before R71',all(power.get(r,{}).get('nets',{}).get(n)=='BAT' for r,n in a2.RAW_ENDPOINTS))
    check('J8/J12 assembly names are Na-ion/LTO',power.get('J8',{}).get('value')=='Na-ion' and power.get('J12',{}).get('value')=='LTO')
    baseline=json.loads((ROOT/'design/v2_electrical_contract.json').read_text('utf-8'))
    changed=[]
    for source in baseline['parts']:
        ref=source['reference'];kind=source['original_model_part']['kind']
        if ref in SHUNT_MPN or kind.startswith('Connector') or kind in ['Switch','MountingHole','TestPoint','NetTie'] or ref=='SH1':
            continue
        p=parts[original_board(ref,source['board'])].get(ref,{})
        row=source['assembly_variant_row']
        for key,field in [('mpn','MPN_NaIon'),('mpn_lto2s','MPN_LTO_2S'),('mpn_naion_no_cold','MPN_NaIon_NoCold')]:
            actual=p.get(key,p.get('mpn',''))
            if actual!=row[field]:changed.append((ref,key,row[field],actual))
    check('Unchanged electrical MPNs retain all three frozen assembly variants',not changed,changed)
    return checks


def feature_native_checks(native, feature):
    # Preserve all A2 differential/Kelvin/pack separation checks. The old
    # returned-supply pin7 rule is superseded exactly by two SYS contacts.
    checks=a2.feature_native_checks(native,feature)[:-1]
    def group(ref,pin):return native.get(('POWER',ref,pin))
    vs,source=group('J101','1'),group('J11','1')
    endpoints={('J101','1'),('J101','3'),('J11','2'),('NT2','1'),('U12','5'),('C63','1')}
    checks.append({'name':'A3 native INA supply, two SYS contacts and J11 output exact common group','pass':vs is not None and source is not None and vs!=source and all(group(r,n)==vs for r,n in endpoints),'detail':None})
    checks.append({'name':'A3 native SYS/RADIO named groups meet only at copper NT2','pass':group('NT2','1') is not None and group('NT2','2') is not None and group('NT2','1')!=group('NT2','2') and group('NT2','2')==group('J101','5')==group('J101','7'),'detail':None})
    return checks


def legacy_union(union,native,feature):
    projected=a2.legacy_union(union,native,feature)
    a=native.get(('POWER','NT2','1'));b=native.get(('POWER','NT2','2'))
    if a is None or b is None or a==b:
        raise ValueError('Distinct native NT2 named groups required before copper-star projection')
    projected.join(a,b)
    return projected
