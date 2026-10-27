"""Read bounded synthetic context from a real Zetaris SQL endpoint."""
import ipaddress
import json
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.parse import urlsplit
import uuid


class ZetarisContext:
    def __init__(self, origin, org_id, credential, sql, evidence, local_origin, route="ui"):
        parsed = urlsplit(origin)
        try:
            loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            loopback = parsed.hostname == "localhost"
        if (parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")
                or parsed.scheme == "http" and not loopback):
            raise ValueError("Use an HTTPS Zetaris origin; HTTP is allowed only on loopback")
        if not str(org_id).isdigit():
            raise ValueError("Zetaris organization ID must be numeric")
        if not isinstance(credential, str) or not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", credential):
            raise ValueError("Enter a valid Zetaris bearer token or API key")
        if (not isinstance(sql, str) or len(sql) > 4000 or not re.match(r"^\s*SELECT\b", sql, re.I)
                or not re.search(r"\bFROM\s+", sql, re.I)
                or re.search(r";|--|/\*|\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|MERGE|CALL|COPY|INTO|GRANT|EXEC|TRUNCATE)\b", sql, re.I)):
            raise ValueError("Use one SELECT from a real synthetic demo table; writes and multi-statement SQL are refused")
        if route not in ("ui", "legacy", "raw"):
            raise ValueError("Zetaris route must be ui, legacy or raw")
        self.origin, self.org_id, self.sql = origin.rstrip("/"), str(org_id), sql.strip()
        self._credential, self.local_origin, self.route = credential, local_origin, route
        self.evidence = Path(evidence)
        self.token = secrets.token_urlsafe(32)

    def config(self):
        return {"enabled": True, "verified": False, "session_token": self.token,
                "notice": "Synthetic context only. Connection is verified only after actual rows are retrieved."}

    def retrieve(self, origin, authorization):
        if origin != self.local_origin or not secrets.compare_digest(authorization, "Bearer " + self.token):
            raise PermissionError("Local session authorization required")
        request_id = str(uuid.uuid4())
        if self.route == "ui":
            url = self.origin + "/api/proxy/query/sql/start"
            body = {"select": self.sql, "pageLimit": 5}
        elif self.route == "legacy":
            url = self.origin + "/api/proxy/sql-editor/sqls/run-query"
            body = {"sql": self.sql, "limit": 5}
        else:
            url = self.origin + "/api/v1.0/sql-editor/sqls/run"
            body = {"queryId": request_id, "sql": self.sql, "source": "SqlEditor", "limit": 5}
        config = (f'header = "Authorization: Bearer {self._credential}"\n'
                  f'header = "X-Org-ID: {self.org_id}"\n'
                  f'header = "X-Request-ID: {request_id}"\n')
        result = subprocess.run(["curl", "-sS", "--max-time", "30", "--max-filesize", "262144", "--config", "-",
                                 url, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body),
                                 "-w", "\n%{http_code}"], input=config, text=True, capture_output=True, timeout=35)
        raw, _, status_text = result.stdout.rpartition("\n")
        status = int(status_text) if status_text.isdigit() else 502
        try:
            response = json.loads(raw)
        except (ValueError, TypeError):
            response = {"error": "Unreadable Zetaris response"}
        evidence_id = f"zetaris-{time.time_ns()}-{request_id}.json"
        record = {"at": time.time(), "request_id": request_id, "endpoint": url, "request": body,
                  "http_status": status, "response": response, "curl_exit": result.returncode}
        self.evidence.mkdir(parents=True, exist_ok=True)
        saved = json.dumps(record, indent=2).replace(self._credential, "[REDACTED]").replace(self.token, "[LOCAL SESSION]")
        (self.evidence / evidence_id).write_text(saved)
        if result.returncode or status != 200:
            raise RuntimeError(f"Zetaris context query failed: HTTP {status}; no plan was generated")
        data = response.get("data") if isinstance(response, dict) else None
        rows = data if isinstance(data, list) else data.get("rows") if isinstance(data, dict) else None
        if rows is None and isinstance(response, dict):
            rows = response.get("rows")
        if not isinstance(rows, list) or not rows or len(rows) > 5 or len(json.dumps(rows)) > 12000:
            raise RuntimeError("Zetaris returned no usable bounded context rows; no plan was generated")
        return {"verified": True, "source": "Zetaris SQL", "endpoint": url, "request_id": request_id,
                "sql": self.sql, "rows": rows, "row_count": len(rows), "http_status": status, "evidence_id": evidence_id}
