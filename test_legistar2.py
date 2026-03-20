import requests

MATTERS_URL = "https://webapi.legistar.com/v1/mwdh2o/matters/6401"
response = requests.get(MATTERS_URL)
m = response.json()
print(f"Matter 6401 Intro Date: {m.get('MatterIntroDate')}")
