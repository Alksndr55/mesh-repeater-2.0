from complete_owner_routes import *
b=k.LoadBoard(str(HERE/'before_maker_lands.kicad_pcb'));KEEP.append(b)
for t in b.GetTracks():
 if t.GetNetname()=='Net-(U1-COM2)':
  print(str(t.m_Uuid.AsString()),'via' if isinstance(t,k.PCB_VIA) else t.GetLayerName(),xy(t.GetPosition()),''if isinstance(t,k.PCB_VIA)else xy(t.GetEnd()),t.GetWidth(k.F_Cu)/1e6 if isinstance(t,k.PCB_VIA)else t.GetWidth()/1e6)
