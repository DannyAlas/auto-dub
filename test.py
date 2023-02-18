import requests


import requests
import json

with requests.get(r"https://firebasestorage.googleapis.com/v0/b/test-emulator-ai-dubbing.appspot.com/o/2etXyEaLrsSJQ6qAgwnlOv2YV8G3%2Forders%2FJyh9aWxS4o87ZtpMRoy3%2Fmain.srt?alt=media&token=a6e79352-009b-4751-8770-378cd365ab6a", stream=True) as r:
    r.raise_for_status()
    r.content.decode("utf-8")
    lines = r.content.decode("utf-8").split("\n")
    print(lines)
