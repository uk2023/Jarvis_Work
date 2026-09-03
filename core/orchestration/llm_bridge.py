from __future__ import annotations

import json
import os
import socket
import time
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

try:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
except ImportError:
    pass

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class CognitiveBudgetExceeded(RuntimeError):
    """Raised when one runtime turn exceeds its configured LLM budget."""


class CognitiveBudgeter:
    """Hard working-memory/context budgeter for every LLM backend."""
    def __init__(self, max_context_tokens: int = 4096, safety_tokens: int = 128):
        self.max_context_tokens = max(256, int(max_context_tokens))
        self.safety_tokens = max(0, int(safety_tokens))

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return int(len(text.split()) * 1.3) + 4

    @staticmethod
    def _trim_to_tokens(text: str, token_budget: int) -> str:
        if not text or token_budget <= 0:
            return ""
        words = text.split()
        if not words:
            return ""
        marker = "\n[context truncated by 4096-token budget]"

        def fits(candidate: str) -> bool:
            return CognitiveBudgeter.estimate_tokens(candidate) <= token_budget

        if fits(text):
            return text
        lo, hi = 0, len(words)
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = " ".join(words[:mid]) + marker
            if fits(candidate):
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def optimize_payload(self, system_prompt: str, user_input: str, max_tokens: int = 512) -> tuple[str, str]:
        output_budget = max(1, int(max_tokens))
        input_budget = self.max_context_tokens - output_budget - self.safety_tokens
        if input_budget <= 0:
            raise CognitiveBudgetExceeded("No input context budget remains for this LLM call")
        sys_tokens = self.estimate_tokens(system_prompt)
        usr_budget = max(1, input_budget - min(sys_tokens, input_budget // 2))
        bounded_user = self._trim_to_tokens(user_input, usr_budget)
        remaining_for_system = max(0, input_budget - self.estimate_tokens(bounded_user))
        bounded_system = self._trim_to_tokens(system_prompt, remaining_for_system)
        total = self.estimate_tokens(bounded_system) + self.estimate_tokens(bounded_user)
        while total > input_budget and bounded_user:
            bounded_user = " ".join(bounded_user.split()[:-1])
            total = self.estimate_tokens(bounded_system) + self.estimate_tokens(bounded_user)
        while total > input_budget and bounded_system:
            bounded_system = " ".join(bounded_system.split()[:-1])
            total = self.estimate_tokens(bounded_system) + self.estimate_tokens(bounded_user)
        if total > input_budget:
            raise CognitiveBudgetExceeded(f"Unable to fit LLM input within {input_budget} tokens")
        return bounded_system, bounded_user


class LlamaCppEngine:
    def __init__(self, model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf", n_ctx: int = 4096, n_threads: int = 4):
        if Llama is None:
            raise ImportError("llama-cpp-python is not installed.")
        model_path = os.path.join(BASE_DIR, "models", model_filename)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at: {model_path}. Place the GGUF file in models/")
        print(f"[JARVIS LLM] Loading offline model from {model_path} ...")
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, use_mlock=False, use_mmap=True, verbose=False)
        self.budgeter = CognitiveBudgeter(max_context_tokens=n_ctx)
        print(f"[JARVIS LLM] Offline model loaded (n_ctx={n_ctx}).")

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        opt_system, opt_user = self.budgeter.optimize_payload(system_prompt, user_input, max_tokens=max_tokens)
        response = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": opt_system}, {"role": "user", "content": opt_user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response["choices"][0]["message"]["content"].strip()


class GroqEngine:
    VALID_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound", "groq/compound-mini", "allam-2-7b"]

    def __init__(self, api_keys: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 8.0):
        if requests is None:
            raise ImportError("The 'requests' package is not installed (pip install requests).")
        raw_keys = api_keys or os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or ""
        self.api_keys = [k.strip() for k in raw_keys.replace(" ", "").split(",") if k.strip()]
        if not self.api_keys:
            raise RuntimeError("No Groq API key (gsk_...) found in .env file.")
        target_model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
        if target_model not in self.VALID_MODELS:
            target_model = "openai/gpt-oss-120b"
        self.model = target_model
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        self.timeout = max(2.0, float(timeout))
        self._current_index = 0

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}], "temperature": temperature, "max_tokens": max_tokens}
        total_keys = len(self.api_keys)
        last_error = None
        for _ in range(total_keys):
            key_index = self._current_index
            self._current_index = (self._current_index + 1) % total_keys
            active_key = self.api_keys[key_index]
            key_num = key_index + 1
            headers = {"Authorization": f"Bearer {active_key}", "Content-Type": "application/json"}
            try:
                print(f"[JARVIS LLM] Groq Key #{key_num}/{total_keys} | Model: {self.model}")
                resp = requests.post(url, headers=headers, json=payload, timeout=(2.5, self.timeout))
                if resp.status_code in (404, 401, 403, 429):
                    print(f"[JARVIS LLM] Key #{key_num} failed HTTP {resp.status_code}: {resp.text.strip()}")
                    last_error = f"HTTP {resp.status_code} ({resp.text.strip()})"
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                print(f"[JARVIS LLM] Key #{key_num} error: {exc}. Trying next key...")
                last_error = exc
        raise RuntimeError(f"All {total_keys} Groq API keys failed. Last error: {last_error}")


class HybridLLMBridge:
    CONNECTIVITY_CHECK_INTERVAL_SECONDS = 15
    CONNECTIVITY_TEST_HOST = "8.8.8.8"
    CONNECTIVITY_TEST_PORT = 53
    CONNECTIVITY_TIMEOUT = 1.5

    def __init__(self, model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf", n_ctx: int = 4096, n_threads: int = 4, force_mode: Optional[str] = None):
        self._model_filename = model_filename
        self._n_ctx = n_ctx
        self._n_threads = n_threads
        self._force_mode = force_mode
        self._groq_engine: Optional[GroqEngine] = None
        self._local_engine: Optional[LlamaCppEngine] = None
        self._last_check_time = 0.0
        self._last_online_result = False
        self.last_error: Optional[str] = None
        self.last_backend = "idle"
        self.is_ready = False
        self._budget_max_calls = 2
        self._budget_max_output_tokens = 768
        self._budget_semantic_tokens = 256
        self._turn_calls = 0
        self._turn_reserved_tokens = 0
        self._turn_active = False
        self._context_budgeter = CognitiveBudgeter(max_context_tokens=n_ctx)
        self._load_budget_policy()

    def _load_budget_policy(self) -> None:
        config_path = os.path.join(BASE_DIR, "config", "cognition.json")
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                llm = json.load(handle).get("llm", {})
            self._budget_max_calls = max(1, int(llm.get("max_calls_per_turn", self._budget_max_calls)))
            self._budget_max_output_tokens = max(1, int(llm.get("max_output_tokens_per_turn", self._budget_max_output_tokens)))
            self._budget_semantic_tokens = max(1, int(llm.get("semantic_fallback_tokens", self._budget_semantic_tokens)))
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def begin_turn_budget(self) -> None:
        self._load_budget_policy()
        self._turn_calls = 0
        self._turn_reserved_tokens = 0
        self._turn_active = True

    def budget_status(self) -> Dict[str, Any]:
        return {"active": self._turn_active, "calls": self._turn_calls, "max_calls": self._budget_max_calls, "reserved_output_tokens": self._turn_reserved_tokens, "max_output_tokens": self._budget_max_output_tokens, "remaining_calls": max(0, self._budget_max_calls - self._turn_calls), "remaining_output_tokens": max(0, self._budget_max_output_tokens - self._turn_reserved_tokens)}

    def _reserve_budget(self, requested_tokens: int) -> int:
        if not self._turn_active:
            self.begin_turn_budget()
        requested = max(1, int(requested_tokens))
        if self._turn_calls >= self._budget_max_calls:
            raise CognitiveBudgetExceeded(f"LLM call budget exceeded: {self._budget_max_calls} calls per turn")
        remaining = self._budget_max_output_tokens - self._turn_reserved_tokens
        if remaining <= 0:
            raise CognitiveBudgetExceeded(f"LLM output-token budget exceeded: {self._budget_max_output_tokens} tokens per turn")
        reserved = min(requested, remaining)
        self._turn_calls += 1
        self._turn_reserved_tokens += reserved
        return reserved

    def verify_offline_ready(self) -> bool:
        try:
            self._get_local()
            self.is_ready = True
            self.last_error = None
            self.last_backend = "local"
            return True
        except Exception as exc:
            self.is_ready = False
            self.last_error = str(exc)
            return False

    def _is_online(self) -> bool:
        if self._force_mode == "online":
            return True
        if self._force_mode == "offline":
            return False
        now = time.time()
        if (now - self._last_check_time) < self.CONNECTIVITY_CHECK_INTERVAL_SECONDS:
            return self._last_online_result
        online = False
        try:
            socket.setdefaulttimeout(self.CONNECTIVITY_TIMEOUT)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.CONNECTIVITY_TEST_HOST, self.CONNECTIVITY_TEST_PORT))
            online = True
        except OSError:
            online = False
        self._last_check_time = now
        self._last_online_result = online
        return online

    def _get_groq(self) -> GroqEngine:
        if self._groq_engine is None:
            self._groq_engine = GroqEngine()
        return self._groq_engine

    def _get_local(self) -> LlamaCppEngine:
        if self._local_engine is None:
            self._local_engine = LlamaCppEngine(model_filename=self._model_filename, n_ctx=self._n_ctx, n_threads=self._n_threads)
        return self._local_engine

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        return self.generate_response(system_prompt=system_prompt, user_input=user_input, max_tokens=max_tokens, temperature=temperature)

    def generate_response(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> str:
        reserved_tokens = self._reserve_budget(max_tokens)
        bounded_system, bounded_user = self._context_budgeter.optimize_payload(system_prompt, user_input, max_tokens=reserved_tokens)
        online = self._is_online()
        have_groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY"))
        allow_local_fallback = self._force_mode == "offline" or os.getenv("JARVIS_ALLOW_LOCAL_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
        if online and have_groq_key:
            try:
                result = self._get_groq().generate(system_prompt=bounded_system, user_input=bounded_user, max_tokens=reserved_tokens, temperature=temperature)
                self.last_error = None
                self.is_ready = True
                self.last_backend = "groq"
                return result
            except Exception as exc:
                self.last_error = str(exc)
                self.last_backend = "groq_error"
                print(f"[JARVIS LLM] Groq API failed: {exc}")
                if not allow_local_fallback:
                    self.is_ready = False
                    return "[LLM unavailable: Groq request failed; local fallback is disabled]"
        if not allow_local_fallback:
            self.last_backend = "blocked"
            self.is_ready = False
            self.last_error = self.last_error or "No usable online LLM backend"
            return "[LLM unavailable: local fallback is disabled]"
        try:
            result = self._get_local().generate(system_prompt=bounded_system, user_input=bounded_user, max_tokens=reserved_tokens, temperature=temperature)
            self.last_error = None
            self.is_ready = True
            self.last_backend = "local"
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self.last_backend = "local_error"
            self.is_ready = False
            return f"[Model Generation Error: {exc}]"


LlamaCppBridge = HybridLLMBridge
