import requests


import requests
import json

with requests.get(r"", stream=True) as r:
    r.raise_for_status()
    r.content.decode("utf-8")
    lines = r.content.decode("utf-8").split("\n")
    print(lines)
