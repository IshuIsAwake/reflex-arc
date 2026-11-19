"""Talking to Ollama: one streamed request, which model answers, and the fallback when the
planner's model can't be reached. Ollama's HTTP API, standard library only."""

import json
import queue
import threading
import time
import urllib.error
import urllib.request

import settings


def installed_models(timeout=2):
    """What `ollama list` shows, as tags, or None if Ollama didn't answer."""
    url = settings.OLLAMA_HOST.rsplit("/api/", 1)[0] + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return sorted(m["name"] for m in json.load(r).get("models", ()))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        return None


def host_for(model, day):
    """Where a request to `model` goes on sol `day`. An --outage sol sends the planner's
    model to a dead port, so it fails the way a real outage does."""
    if model == settings.MODEL and day in settings.OUTAGE_SOLS:
        return settings.OUTAGE_HOST
    return settings.OLLAMA_HOST


def probe(model, host):
    """One token from `model`. True if it answered at all."""
    body = json.dumps({"model": model, "stream": False, "keep_alive": settings.MODEL_KEEP_ALIVE,
                       "messages": [{"role": "user", "content": "ok"}],
                       "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request(host, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=settings.PROBE_TIMEOUT) as r:
            return "error" not in json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def stream(model, host, messages, tools, q):
    """One streamed request. Puts ("think", text), ("say", text), then ("done", (last
    message, tool calls)) or ("error", why) on the queue `q`. Runs on a thread."""
    options = {"num_ctx": settings.MODEL_CTX}
    # MODEL_TEMP None sends no sampler options at all: the model's own defaults.
    if settings.MODEL_TEMP is not None:
        options["temperature"] = settings.MODEL_TEMP
    # A fixed seed doesn't make the model repeat itself, but leaving it unset guarantees it won't.
    if settings.MODEL_SEED is not None:
        options["seed"] = settings.MODEL_SEED
    payload = {
        "model": model, "messages": messages, "stream": True,
        "think": settings.MODEL_THINK, "keep_alive": settings.MODEL_KEEP_ALIVE,
        "options": options, "tools": tools,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(host, body, {"Content-Type": "application/json"})
    wanted = []
    finished = False
    try:
        with urllib.request.urlopen(req, timeout=settings.MODEL_TIMEOUT) as r:
            for raw in r:
                if not raw.strip():
                    continue
                d = json.loads(raw)
                # Ollama reports an unreachable model as a line in the stream, not a status.
                if d.get("error"):
                    raise ValueError(f"Ollama: {d['error']}")
                m = d.get("message") or {}
                if m.get("thinking"):
                    q.put(("think", m["thinking"]))
                if m.get("content"):
                    q.put(("say", m["content"]))
                for tc in m.get("tool_calls") or ():
                    wanted.append(tc.get("function") or {})
                if d.get("done"):
                    # The calls come with `done`, so pump() sees a whole turn at once.
                    q.put(("done", (d, wanted)))
                    finished = True
        if not finished:
            raise ValueError("the stream ended without finishing")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        q.put(("error", f"{type(e).__name__}: {e}"))


class Link:
    """Which model is answering, for the whole run. When MODEL fails, requests go to
    MODEL_FALLBACK, and MODEL is probed every PROBE_SECONDS on a thread until it answers again.
    Every cost row on the tape names the model that answered."""

    def __init__(self, probe_fn=None):
        self.down = False  # MODEL failed, and hasn't answered a probe since
        self.hold = False  # a sol's first request waits for the morning probe
        self.probe = probe_fn or probe
        self.next_probe = 0.0
        self.results = queue.Queue()
        self.probing = False

    @property
    def model(self):
        if self.down:
            return settings.MODEL_FALLBACK
        return settings.MODEL

    def failed(self, model):
        """A request to `model` got no answer. True if the link has switched to the fallback."""
        if self.down or model != settings.MODEL:
            return False
        if not settings.MODEL_FALLBACK or settings.MODEL_FALLBACK == settings.MODEL:
            return False
        self.down = True
        self.next_probe = time.monotonic() + settings.PROBE_SECONDS
        return True

    def morning(self):
        """A new sol tries MODEL at once, and holds its first request until that probe answers."""
        if self.down:
            self.hold = True
            if not self.probing:
                self.next_probe = 0.0

    def poll(self, day):
        """Once a frame. True at the moment MODEL is back."""
        try:
            answered = self.results.get_nowait()
        except queue.Empty:
            answered = None
        if answered is not None:
            self.probing = False
            self.hold = False
            if answered and self.down:
                self.down = False
                return True
            self.next_probe = time.monotonic() + settings.PROBE_SECONDS
        if self.down and not self.probing and time.monotonic() >= self.next_probe:
            self.probing = True
            model = settings.MODEL
            host = host_for(model, day)
            threading.Thread(target=self.probe_in_background, args=(model, host),
                             daemon=True).start()
        return False

    def probe_in_background(self, model, host):
        self.results.put(self.probe(model, host))
