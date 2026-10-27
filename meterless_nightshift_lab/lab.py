"""Fetch verified public Nightshift assets and serve an isolated local lab."""
from __future__ import annotations

import argparse
import getpass
import sys
import warnings
from contextlib import contextmanager
import hashlib
import http.server
import json
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import os
import time
import urllib.error
import urllib.request
from graduation_demo import ensure_demo, wire_demo
from deepseek_relay import DeepSeekRelay

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / ".runtime" / "web"
LOCK = Path(__file__).with_name("assets.lock.json")
MODEL_LOCK = Path(__file__).with_name("models.lock.json")
UPSTREAM = "https://meterless.ai/Nightshift/WEB/"


def asset_path(name: str) -> Path:
    """Reject remote URLs and escapes from the downloaded asset directory."""
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name:
        raise ValueError("unsafe asset path")
    dest = ASSETS.joinpath(*path.parts)
    if not dest.resolve().is_relative_to(ASSETS.resolve()):
        raise ValueError("asset symlink escapes cache")
    return dest


def checked_bytes(data: bytes, spec: dict) -> bytes:
    if len(data) != spec["bytes"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("upstream asset differs from the recorded build; refusing to execute it")
    return data


def fetch_bytes(url: str) -> bytes:
    """Use normal certificate validation; curl handles macOS Python CA gaps."""
    try:
        with urllib.request.urlopen(url, timeout=45) as response:
            return response.read(24 * 1024 * 1024)
    except urllib.error.URLError:
        curl = shutil.which("curl")
        if not curl:
            raise
        return subprocess.check_output([curl, "-fsSL", "--max-time", "45", "--proto", "=https", url])


def bootstrap() -> None:
    manifest = json.loads(LOCK.read_text())
    reserve = 10 * 1024**3
    needed = sum(s["bytes"] for n, s in manifest.items() if not asset_path(n).exists())
    if shutil.disk_usage(ROOT).free < reserve + 2 * needed:
        raise RuntimeError("insufficient free disk: preserve 10 GiB plus download working space")
    for name, spec in sorted(manifest.items()):
        dest = asset_path(name)
        if dest.exists():
            checked_bytes(dest.read_bytes(), spec)
            continue
        data = checked_bytes(fetch_bytes(UPSTREAM + name), spec)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    print(f"Verified {len(manifest)} Nightshift assets. No models downloaded.")
    ensure_demo(ROOT, fetch_bytes, checked_bytes)


def local_environment(proxy_base="") -> bytes:
    """Only host configuration changes; upstream inference and grading stay intact."""
    value = {"proxyBase": proxy_base, "turnstileSiteKey": "", "byokProviders": [], "localNetwork": True,
             "hotspotRelay": "", "hotspot": False, "companionSha256": "", "companionBytes": 0}
    return ("window.NS_WEB_ENV=" + json.dumps(value) + ";\n").encode()


class LabHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ASSETS), **kwargs)

    def do_GET(self):
        name = self.path.split("?", 1)[0]
        if name == "/judge-config":
            relay = getattr(self.server, "judge_relay", None)
            self.send_json(relay.config() if relay else {"enabled": False})
            return
        if name == "/graduation-loop.html":
            original = ensure_demo(ROOT, fetch_bytes, checked_bytes)
            body = wire_demo(original.read_text(encoding="utf-8")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if name in ("/proof.html", "/proof.js", "/graduation_bridge.mjs"):
            body = Path(__file__).with_name(name[1:]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if name.endswith("html") else "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?", 1)[0] == "/js/web/web-env.js":
            relay = getattr(self.server, "judge_relay", None)
            body = local_environment(relay.origin + "/deepseek-relay" if relay else "")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def send_json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        relay = getattr(self.server, "judge_relay", None)
        if self.path != "/deepseek-relay/v1/chat/completions" or not relay:
            self.send_json({"error": "No configured endpoint"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 40000:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            response = relay.judge(request, self.headers.get("Origin", ""), self.headers.get("Authorization", ""))
            self.send_json(response)
        except PermissionError:
            self.send_json({"error": "Local session authorization required"}, 403)
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.send_json({"error": str(error)}, 502)

    def end_headers(self):
        # An HTTP policy can further restrict the upstream meta policy.
        self.send_header("Content-Security-Policy", "connect-src 'self' http://127.0.0.1:11435 http://localhost:11435; form-action 'none'")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Do not log query strings, headers or request bodies.
        pass


def serve(port: int = 8765, api_key=None) -> None:
    bootstrap()
    print(f"Nightshift local proof: http://127.0.0.1:{port}/proof.html", flush=True)
    print(f"Little Jahsi live demo: http://127.0.0.1:{port}/graduation-loop.html", flush=True)
    if api_key:
        print("DeepSeek Pro generates; DeepSeek Flash independently verifies. This session allows up to eight paid API calls. Ctrl+C stops this server.", flush=True)
    else:
        print("Connect Ollama under Setup > Local Network Compute at http://127.0.0.1:11435/v1. Ctrl+C stops this server.", flush=True)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), LabHandler) as server:
        server.judge_relay = DeepSeekRelay(api_key, ROOT / ".runtime" / "evidence",
                                          f"http://127.0.0.1:{port}") if api_key else None
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def local_json(endpoint: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request("http://127.0.0.1:11435" + endpoint, data=data,
                                     headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=900) as response:
        return json.load(response)


@contextmanager
def model_server(port: int = 8765):
    """Own one process; never stop another Ollama or modify global configuration."""
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError("Install Ollama from https://ollama.com/download first. No installer is run by this lab.")
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 11435)) == 0:
            raise RuntimeError("Port 11435 is already occupied. Stop your earlier lab process, or use serve with an already configured local server.")
    state = ROOT / ".runtime"
    state.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(OLLAMA_MODELS=str(state / "models"), OLLAMA_HOST="127.0.0.1:11435",
               OLLAMA_NO_CLOUD="1", OLLAMA_NOPRUNE="1", OLLAMA_MAX_LOADED_MODELS="1",
               OLLAMA_NUM_PARALLEL="1", OLLAMA_ORIGINS=f"http://127.0.0.1:{port}")
    with (state / "ollama.log").open("a") as log:
        proc = subprocess.Popen([executable, "serve"], env=env, stdout=log, stderr=log)
        try:
            for _ in range(80):
                if proc.poll() is not None:
                    raise RuntimeError("Ollama exited. Inspect .runtime/ollama.log locally.")
                try:
                    local_json("/api/version")
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Ollama did not become ready on loopback.")
            yield
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def verify_models() -> list[str]:
    pinned = json.loads(MODEL_LOCK.read_text())
    tags = {m["name"]: m for m in local_json("/api/tags")["models"]}
    missing = []
    for name, spec in pinned.items():
        if name not in tags:
            missing.append(name)
        elif tags[name]["digest"] != spec["digest"]:
            raise RuntimeError(f"Model {name} differs from the tested manifest. Stop and review the version change.")
    return missing


def setup_models() -> None:
    pinned = json.loads(MODEL_LOCK.read_text())
    missing = verify_models()
    growth = sum(pinned[name]["bytes"] for name in missing)
    peak = growth + max((pinned[name]["bytes"] for name in missing), default=0)
    if shutil.disk_usage(ROOT).free < 10 * 1024**3 + peak:
        raise RuntimeError("Model download would leave too little disk headroom. Need 10 GiB plus estimated download peak.")
    for name in missing:
        print(f"Downloading {name} to .runtime/models (about {pinned[name]['bytes']/1e9:.1f} GB).", flush=True)
        result = local_json("/api/pull", {"model": name, "stream": False})
        if result.get("status") != "success":
            raise RuntimeError(f"Model download failed: {result.get('error', 'unknown error')}")
    if verify_models():
        raise RuntimeError("One or more models remain missing.")
    print("All local model manifests match the tested versions.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "serve", "setup-models", "start"], default="start", nargs="?")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--deepseek", action="store_true", help="Enable bounded paid generation and judging; enter your key at a hidden terminal prompt")
    args = parser.parse_args(argv)
    if args.deepseek and args.command not in ("start", "serve"):
        parser.error("--deepseek is available only with start or serve")
    api_key = None
    if args.deepseek:
        if not sys.stdin.isatty():
            parser.error("Run --deepseek in an interactive terminal so the API key can be entered without echo")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                api_key = getpass.getpass("DeepSeek API key (hidden; not saved): ")
        except getpass.GetPassWarning:
            parser.error("This terminal cannot hide key entry; use an interactive terminal with echo control")
        except (EOFError, KeyboardInterrupt):
            parser.exit(1, "\nKey entry cancelled.\n")
        if not api_key:
            parser.error("A DeepSeek API key is required for this mode")
        # Validate before fetching assets or starting any server.
        DeepSeekRelay(api_key, ROOT / ".runtime" / "evidence", f"http://127.0.0.1:{args.port}")
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "serve" or (args.command == "start" and args.deepseek):
        serve(args.port, api_key)
    else:
        with model_server(args.port):
            if args.command == "setup-models":
                setup_models()
            else:
                if verify_models():
                    raise RuntimeError("Run setup-models first to download the tested local models.")
                serve(args.port)


if __name__ == "__main__":
    main()
