"""DETECTIVE OS — MiniMax text caller (for pipeline extraction only).

Uses the registered custom.minimax api_key via dynamic_credentials
(hsurr surrogate, never printed or stored). Endpoint and model are
the proven pair from the book-site Workers (sanguo/functions/api/chat.js):
POST https://api.minimaxi.com/v1/text/chatcompletion_v2, model MiniMax-M3.

Hard rules for this caller (pipeline use):
- It only EXTRACTS candidate facts from source texts the caller passes
  in. It never computes probabilities and never invents facts.
- Every extracted item must carry a verbatim quote; the pipeline
  rejects any item whose quote is not found in the source text.
- The caller caps extracted evidence at grade C (media) or H
  (unverified). A/B grades are never assigned by this path.
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

MODEL = "MiniMax-M3"
URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
HOSTS = ["api.minimax.io", "api.minimaxi.com", "api.minimaxi.chat"]
CREDENTIAL = "custom.minimax"


def call_minimax(messages, max_tokens=2048, temperature=0.2):
    """Call MiniMax-M3 chat completions. Returns the reply text."""
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    # The credential is attached as a surrogate by dynamic_credentials
    # and swapped in by authd only for a registered host. Never put the
    # key in code, env, args or logs.
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=HOSTS)
    # No redirects: an authenticated request must never leak the key.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError(f"unexpected redirect to {newurl}")
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("base_resp") or data["base_resp"].get("status_code") != 0:
        raise RuntimeError(f"minimax error: {json.dumps(data)[:300]}")
    choices = data.get("choices") or []
    text = (choices[0].get("message") or {}).get("content", "") if choices else ""
    if not text or not text.strip():
        raise RuntimeError("minimax returned empty content")
    return text.strip()


def call_minimax_retry(messages, max_tokens=8192, temperature=0.2, tries=5):
    """call_minimax with retries on empty content / transient errors.

    M3 is a reasoning model: it can spend its whole budget thinking and
    return nothing. A bigger budget plus a retry is the fix; a
    persistent empty reply is still a hard failure, never faked.
    5 tries (was 3): a single batch failing must not kill a whole run,
    and the pipeline also skips failed batches — but give each call
    every fair chance first.
    """
    import time
    last = None
    for attempt in range(tries):
        try:
            return call_minimax(messages, max_tokens=max_tokens,
                                temperature=temperature)
        except Exception as exc:  # noqa: BLE001 - retry then surface
            last = exc
            if attempt < tries - 1:
                time.sleep(8)
    raise RuntimeError(f"minimax failed after {tries} tries: {last}")


if __name__ == "__main__":
    # M3 is a reasoning model: max_tokens 1024 minimum, less and it
    # only thinks without answering (sanguo chat.js notes the same).
    print(call_minimax([
        {"role": "user", "content": "只回答一个词：今天是星期几？不知道就回答不知道。"},
    ], max_tokens=1024))
