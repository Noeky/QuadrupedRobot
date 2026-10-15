"""Generate a non-load-bearing servo ear fit coupon, dimensions in mm."""
import sys, json
from pathlib import Path
from project_paths import COUPON_DIR

import cadquery as cq

# Print XY flat. Model X becomes coupon X; model Z becomes coupon Y.
# Nominal model body 22.3 x 12.5; hole spacing 27.7; holes nominal dia 2.
params = dict(outer_x=36.0, outer_y=20.0, thickness=2.5,
              body_x=22.3, body_y=12.5, clearance_each_side=0.4,
              hole_spacing=27.7, hole_diameter=2.2)
p = params
coupon = cq.Workplane('XY').rect(p['outer_x'],p['outer_y']).extrude(p['thickness'])
coupon = coupon.faces('>Z').workplane().rect(p['body_x']+2*p['clearance_each_side'],p['body_y']+2*p['clearance_each_side']).cutThruAll()
coupon = coupon.faces('>Z').workplane().pushPoints([(-p['hole_spacing']/2,0),(p['hole_spacing']/2,0)]).hole(p['hole_diameter'])
assert coupon.val().isValid() and len(coupon.val().Solids()) == 1
folder = COUPON_DIR
folder.mkdir(exist_ok=True)
cq.exporters.export(coupon,str(folder / 'servo_fit_coupon.step'))
cq.exporters.export(coupon,str(folder / 'servo_fit_coupon.stl'),tolerance=0.02,angularTolerance=0.1)
(folder / 'fit_coupon_parameters.json').write_text(json.dumps(params,indent=2),encoding='utf-8')
print('Fit coupon valid; volume mm^3:',coupon.val().Volume())
