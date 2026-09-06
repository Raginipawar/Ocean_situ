"""
VARUNA Backend — quick smoke-test for the mock data service.

Run without a server: python -m app.smoke_test
"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.services.mock_data import (
    generate_model_snapshot,
    generate_observation_snapshot,
    generate_fused_snapshot,
    generate_alerts,
)

def hr(title): print(f"\n{'-'*55}\n  {title}\n{'-'*55}")

hr("MODEL SNAPSHOT")
m = generate_model_snapshot()
print(f"  region: {m['region']}")
print(f"  points: {len(m['points'])} grid points @ {m['resolution_deg']}° res")
p0 = m['points'][0]
print(f"  first:  lat={p0['lat']} lon={p0['lon']} sst={p0['sst_c']}°C  u={p0['current_u_ms']} v={p0['current_v_ms']}")

hr("OBSERVATION SNAPSHOT")
o = generate_observation_snapshot()
print(f"  sensors: {len(o['points'])}")
for s in o['points'][:4]:
    print(f"  [{s['sensor_type']:8s}] {s['sensor_id']:14s} lat={s['lat']} lon={s['lon']} sst={s['sst_c']}°C")

hr("FUSED SNAPSHOT")
f = generate_fused_snapshot()
print(f"  points: {len(f['points'])}")
print(f"  engine: {f['summary']['engine']}")
print(f"  mean_confidence: {f['summary']['mean_confidence']}")
print(f"  mean_abs_corr_sst: {f['summary']['mean_abs_correction_sst_c']}°C")
tl = [p['trust_label'] for p in f['points']]
print(f"  trust distribution: green={tl.count('green')} amber={tl.count('amber')} red={tl.count('red')}")

hr("ALERTS")
alerts = generate_alerts()
for a in alerts:
    print(f"  [{a['severity']:8s}] {a['message']}")

print("\nOK - All mock data generators passed\n")
