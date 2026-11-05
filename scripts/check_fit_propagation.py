"""Read-only consistency check of the R3 whole robot and print packages."""
import csv
import hashlib
import json
import zipfile
from verify_current import ROOT,CURRENT,QUANTITIES,cq,check_mesh

report=json.loads((CURRENT/'validation.json').read_text(encoding='utf-8'))
assert report['revision']=='R3' and not report['static_intersections_over_0p05_mm3']
assert (CURRENT/'fit_propagation_native.tsv').is_file()
expected_volumes=[]
cache={}
for name,file,transform in csv.reader((CURRENT/'assembly_manifest.tsv').open(encoding='utf-8-sig'),delimiter='\t'):
    from pathlib import Path
    p=Path(file)
    source=p.with_suffix('.step') if 'hardware' in p.parts else CURRENT/'step'/(p.stem+'.step')
    if source not in cache:
        shape=cq.importers.importStep(str(source)).val()
        assert shape.isValid() and len(shape.Solids())==1,source
        cache[source]=shape.Volume()
    expected_volumes.append(cache[source])
assembly=cq.importers.importStep(str(CURRENT/'robot.step')).val()
actual_volumes=sorted(s.Volume() for s in assembly.Solids())
assert len(actual_volumes)==len(expected_volumes)==35
max_volume_error=max(abs(a-b) for a,b in zip(actual_volumes,sorted(expected_volumes)))
assert max_volume_error<.02,max_volume_error
full=zipfile.ZipFile(ROOT/'releases/QuadrupedRobot_Print_R3.zip')
trial=zipfile.ZipFile(ROOT/'releases/QuadrupedRobot_Fit_Test_R3.zip')
assert full.testzip() is None and trial.testzip() is None
checks={}
for name,quantity in QUANTITIES.items():
    filename=f'{name}_x{quantity}.stl';raw=(CURRENT/'print'/filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==report['parts'][name]['sha256']
    assert full.read(filename)==raw
    check_mesh(raw)
    if name in ('shin','knee_horn_clamp','thigh_left','hip_horn_clamp'):
        folder='01_RETEST' if name in ('shin','knee_horn_clamp') else '02_OPTIONAL'
        assert trial.read(f'{folder}/{name}_R3_x1.stl')==raw
    checks[name]={'quantity':quantity,'whole_set_matches_current_stl':True}
result={'revision':'R3','native_check':'fit_propagation_native.tsv',
        'assembly_step_solids':35,'max_component_volume_error_mm3':max_volume_error,
        'whole_and_trial_meshes_identical_for_matching_parts':True,'parts':checks,
        'static_intersections_over_0p05_mm3':[],
        'physical_validation_pending':['M2 hardware fit','full seating depth and clamp play',
                                      'fastener and wire clearance','load and walking tests']}
(CURRENT/'fit_propagation_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
