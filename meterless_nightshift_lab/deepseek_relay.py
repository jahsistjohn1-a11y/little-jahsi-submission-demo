"""Bounded host-only DeepSeek transport for Nightshift's normal relay provider."""
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time


class DeepSeekRelay:
    def __init__(self, api_key, evidence, origin, limit=8):
        if not isinstance(api_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", api_key):
            raise ValueError("Enter a valid DeepSeek API key; it is kept only in memory")
        self._key = api_key
        self.token = secrets.token_urlsafe(32)
        self.origin, self.evidence, self.limit = origin, Path(evidence), limit
        self.calls = 0
        self.lock = threading.Lock()

    def config(self):
        return {"enabled": True,
                "generator_model": "deepseek-v4-pro",
                "judge_model": "deepseek-v4-flash",
                "api_models": {"deepseek-v4-pro": "deepseek-v4-pro", "deepseek-v4-flash": "deepseek-flash"},
                "session_token": self.token,
                "remaining_calls": max(0, self.limit-self.calls)}

    def judge(self, payload, origin, authorization):
        if origin != self.origin or not secrets.compare_digest(authorization, "Bearer " + self.token):
            raise PermissionError("This relay accepts only its own local demo session")
        requested_model = payload.get("model")
        api_models = {"deepseek-v4-pro": "deepseek-v4-pro", "deepseek-v4-flash": "deepseek-flash"}
        if requested_model not in api_models:
            raise ValueError("Only the configured DeepSeek generator and verifier are available")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages or len(json.dumps(messages)) > 32000:
            raise ValueError("Invalid or oversized judge request")
        if requested_model == "deepseek-v4-flash":
            system = str(messages[0].get("content", ""))
            if not system.startswith(("You grade candidates against numbered criteria.", "You are a strict answer grader.")):
                raise ValueError("The DeepSeek verifier accepts only native Nightshift judge requests")
        with self.lock:
            if self.calls >= self.limit:
                raise ValueError("Paid judge-call budget exhausted; restart explicitly to authorize another bounded session")
            self.calls += 1
            sequence = self.calls
        body = {"model": api_models[requested_model], "messages": messages, "stream": False,
                "temperature": payload.get("temperature", 0),
                "max_tokens": min(1200, max(100, int(payload.get("max_tokens", 600)))),
                "thinking": {"type": "disabled"}}
        result = subprocess.run(["curl", "-sS", "--max-time", "45", "--config", "-",
                                 "https://api.deepseek.com/chat/completions",
                                 "-H", "Content-Type: application/json", "--data-binary", json.dumps(body),
                                 "-w", "\n%{http_code}"],
                                input=f'header = "Authorization: Bearer {self._key}"\n',
                                text=True, capture_output=True, timeout=50)
        raw, _, status_text = result.stdout.rpartition("\n")
        status = int(status_text) if status_text.isdigit() else 502
        try:
            response = json.loads(raw)
        except (ValueError, TypeError):
            response = {"error": {"message": "DeepSeek returned an unreadable response"}}
        self.evidence.mkdir(parents=True, exist_ok=True)
        record = {"at": time.time(), "sequence": sequence, "purpose": "generation" if requested_model == "deepseek-v4-pro" else "independent verification",
                  "transport": "Nightshift native meterless-proxy provider to official DeepSeek API",
                  "browser_request": payload, "provider_request": body, "http_status": status,
                  "provider_response": response, "curl_exit": result.returncode}
        saved = json.dumps(record, indent=2).replace(self._key, "[REDACTED]").replace(self.token, "[LOCAL SESSION]")
        (self.evidence / f"deepseek-relay-{time.time_ns()}-{sequence}.json").write_text(saved)
        if result.returncode or status != 200:
            raise RuntimeError(f"DeepSeek judge request failed: HTTP {status}; credential withheld")
        # Nightshift pins the provider-qualified catalog ID. DeepSeek's
        # API response reports only its native model ID, so normalize the
        # response metadata while preserving the untouched API receipt on
        # disk above.
        engine_response = dict(response)
        engine_response["model"] = "meterless-proxy/" + requested_model
        return engine_response
