#!/usr/bin/env python3
import json, os, urllib.request
payload = {
    "model": "openai/gpt-5",
    "messages": [
        {"role": "system", "content": "Return only JSON."},
        {"role": "user", "content": "Return exactly {\"answer\":\"Yes\"}."},
    ],
}
request = urllib.request.Request(
    "https://models.github.ai/inference/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    },
)
with urllib.request.urlopen(request, timeout=180) as response:
    body = response.read().decode()
print(body)
