from complete_owner_routes import *
b=k.LoadBoard(str(PCB));KEEP.append(b)
def vec(a):return k.VECTOR2I(k.FromMM(a[0]),k.FromMM(a[1]))
for t in b.GetTracks():
 uid=str(t.m_Uuid.AsString())
 if uid=='8059368a-a790-4ef7-9862-15b4f7333375':t.SetPosition(vec((23.65,30.0)))
 elif uid=='3e539133-eadb-441e-95e1-e7b967121ca3':t.SetEnd(vec((23.7375,29.9125)))
 elif uid=='dab29d35-edce-4db6-b6b2-39b3e335d3fc':t.SetStart(vec((23.7375,29.9125)));t.SetEnd(vec((23.65,30.0)))
 elif uid=='4d81c364-728a-423d-9869-46d670ef5b5b':t.SetStart(vec((23.65,30.0)));t.SetEnd(vec((26.6,32.95)))
 elif uid=='6813504d-c9c7-49c7-a1c5-642eacf05ab3':t.SetStart(vec((26.6,32.95)))
save(b)
print('Shifted broad BAT_SYS takeoff 0.4mm preserving strict45/90')
