import requests
requests.packages.urllib3.disable_warnings()

ip = "192.168.123.102"

# GPM Plus utilise souvent ces endpoints
urls = [
    f"http://{ip}",
    f"http://{ip}/api",
    f"http://{ip}/api/data",
    f"http://{ip}/gpmplus",
    f"http://{ip}/GPMPlus",
    f"https://{ip}/api",
    f"https://{ip}/api/data",
]

for url in urls:
    try:
        r = requests.get(url, verify=False, timeout=3)
        if r.status_code == 200:
            print(f"✅ {url}")
            print(f"   {r.text[:300]}")
        else:
            print(f"✗ {url} → {r.status_code}")
    except Exception as e:
        print(f"✗ {url} → erreur")