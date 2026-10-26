"""Model backends. Keys come only from the environment or ~/.config/nullspace.env."""
import json
import os
import time
import urllib.request
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "nullspace.env"


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class OllamaBackend:
    """Native Ollama chat API, so thinking can be switched off for qwen3."""

    def __init__(self, model="qwen3:8b", host="http://localhost:11434", temperature=0.7,
                 max_tokens=400, think=False, timeout=600):
        self.model, self.host = model, host
        self.temperature, self.max_tokens, self.think, self.timeout = temperature, max_tokens, think, timeout
        self.name = f"ollama:{model}"

    def complete(self, prompt, **kw):
        body = {"model": self.model, "stream": False, "think": self.think,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": kw.get("temperature", self.temperature),
                            "num_predict": kw.get("max_tokens", self.max_tokens),
                            "seed": kw.get("seed")}}
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["message"]["content"]


class OpenAICompatBackend:
    """Groq or Gemini through their OpenAI-compatible endpoints."""

    URLS = {"groq": "https://api.groq.com/openai/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/"}
    KEYS = {"groq": "GROQ_API_KEYS", "gemini": "GEMINI_API_KEY"}

    def __init__(self, provider, model, temperature=0.7, max_tokens=1500, retries=8,
                 reasoning_effort=None):
        from openai import OpenAI
        load_env()
        keys = [k for k in os.environ.get(self.KEYS[provider], "").split(",") if k]
        if not keys:
            raise RuntimeError(f"no key in env var {self.KEYS[provider]}")
        self.clients = [OpenAI(base_url=self.URLS[provider], api_key=k) for k in keys]
        self.i, self.model = 0, model
        self.temperature, self.max_tokens, self.retries = temperature, max_tokens, retries
        self.reasoning_effort = reasoning_effort
        self.name = f"{provider}:{model}" + (f"@{reasoning_effort}" if reasoning_effort else "")
        self.tool_failures = 0
        self.sleep = time.sleep

    TOOL_SAMPLES = 3

    def complete(self, prompt, **kw):
        """A model-side tool-call refusal (Groq 'tool_use_failed') is a property of the reply,
        not the transport: resample up to TOOL_SAMPLES times, then return "" (recorded by the
        caller as a failed reply). Transport/rate errors rotate keys and back off, then raise."""
        last, tool_tries = None, 0
        for attempt in range(self.retries + self.TOOL_SAMPLES):
            client = self.clients[self.i % len(self.clients)]
            try:
                extra = {"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}
                r = client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": prompt}],
                    temperature=kw.get("temperature", self.temperature),
                    max_tokens=kw.get("max_tokens", self.max_tokens), **extra)
                return r.choices[0].message.content or ""
            except Exception as e:
                if "tool_use_failed" in str(e):
                    self.tool_failures += 1
                    tool_tries += 1
                    if tool_tries >= self.TOOL_SAMPLES:
                        return ""
                    continue
                last = e
                if attempt - tool_tries >= self.retries - 1:
                    break
                self.i += 1
                self.sleep(min(2 ** (attempt - tool_tries), 60))
        raise RuntimeError(f"{self.name} failed after {self.retries} attempts: {last}")
