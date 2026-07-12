#!/usr/bin/env python3
import json, os, pathlib, urllib.error, urllib.request
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
try:
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read()
        diagnostic = {
            "ok": True,
            "status": response.status,
            "headers": dict(response.headers),
            "raw_length": len(raw),
            "raw_utf8": raw.decode(errors="replace"),
        }
except urllib.error.HTTPError as exc:
    raw = exc.read()
    diagnostic = {
        "ok": False,
        "status": exc.code,
        "reason": str(exc.reason),
        "headers": dict(exc.headers),
        "raw_length": len(raw),
        "raw_utf8": raw.decode(errors="replace"),
    }
except Exception as exc:
    diagnostic = {
        "ok": False,
        "exception": f"{type(exc).__name__}: {exc}",
    }
try:
    parsed = json.loads(diagnostic.get("raw_utf8", ""))
    diagnostic["parsed_keys"] = list(parsed) if isinstance(parsed, dict) else None
    diagnostic["message"] = parsed.get("choices", [{}])[0].get("message") if isinstance(parsed, dict) else None
except Exception as exc:
    diagnostic["parse_error"] = f"{type(exc).__name__}: {exc}"
pathlib.Path("gpt5_probe_response.json").write_text(json.dumps(diagnostic, indent=2))
print(json.dumps(diagnostic, indent=2))
