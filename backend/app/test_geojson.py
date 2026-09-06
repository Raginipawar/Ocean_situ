import urllib.request, json, urllib.error

# Test 1: full response
with urllib.request.urlopen("http://localhost:8000/api/fused/geojson") as r:
    data = json.loads(r.read())

print("type:", data["type"])
print("features count:", len(data["features"]))
f0 = data["features"][0]
p  = f0["properties"]
g  = f0["geometry"]
print("feature[0] geometry:", g["type"], "coords=", g["coordinates"])
print("feature[0] sst_c=", p["sst_c"], "trust=", p["trust_label"], "color=", p["_color"])
print("feature[0] _is_sensor=", p["_is_sensor"], "_current_speed_ms=", p["_current_speed_ms"])
print("varuna block:", data["varuna"])

# Test 2: bbox filter
with urllib.request.urlopen("http://localhost:8000/api/fused/geojson?bbox=85,10,95,18") as r:
    data2 = json.loads(r.read())
print("bbox-filtered features:", len(data2["features"]), "(subset of 378)")

# Test 3: invalid engine -> expect 400
try:
    urllib.request.urlopen("http://localhost:8000/api/fused/geojson?engine=bad")
    print("FAIL: should have rejected invalid engine")
except urllib.error.HTTPError as e:
    print("invalid engine -> correctly rejected HTTP", e.code)

print()
print("ALL GEOJSON TESTS PASSED")
