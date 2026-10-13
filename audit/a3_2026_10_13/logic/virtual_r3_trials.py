"""Read-only, in-memory R3 text-placement trials; no CAD may be saved."""
import json
import label_power_a3 as p

def main():
    parts,groups=p.setup()
    original_load=p.c.k.LoadBoard
    trialposes=[(20.5,36.5,0),(20.,36.5,0),(20.5,36.,0),(21.,37.,0),
                (20.5,37.,0),(20.5,36.5,90),(20.,36.5,90),(21.,36.5,90)]
    result=[]
    for i,pose in enumerate(trialposes):
        out=p.OUT/('virtual_R3_'+str(i));out.mkdir(exist_ok=True)
        b=original_load(str(p.PCB));p.c.HELD.append(b)
        f=next(f for f in b.GetFootprints() if f.GetReference()=='R3')
        f.SetPosition(p.c.vec(pose[:2]));f.SetOrientationDegrees(pose[2])
        p.e.OUT=p.c.OUT=out;p.c.k.LoadBoard=lambda path:b
        try:
            report=p.e.main(save=False,profile='POWER',model_parts=parts,run_check=False)
            missing=[]
        except RuntimeError:
            data=json.loads((out/'proposal_unplaced.json').read_text(encoding='utf8'))
            missing=[r['ref'] for r in data['unplaced']]
        finally:p.c.k.LoadBoard=original_load
        row=dict(trial=i,virtual_R3_pose=pose,unplaced=missing,CAD_written=False)
        result.append(row);print(json.dumps(row),flush=True)
        if not missing:break
    (p.OUT/'virtual_R3_trials.json').write_text(json.dumps(result,indent=2),encoding='utf8')

if __name__=='__main__':main()
