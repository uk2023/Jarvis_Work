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

try:
    from ..runtime.log import log_event
except ImportError:  # pragma: no cover - defensive, keeps this module standalone-importable
    def log_event(tag: str, message: str, level: str = "info") -> None:
        pass


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
    def __init__(self, model_filename: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf", subdir: str = "Offline_LLM", n_ctx: int = 2048, n_threads: int = 2):
        if Llama is None:
            raise ImportError("llama-cpp-python is not installed.")
        model_path = os.path.join(BASE_DIR, "models", subdir, model_filename)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model file not found at: {model_path}. Run download.sh, or place the GGUF "
                f"file at models/{subdir}/{model_filename} manually."
            )
        log_event("llm_bridge", f"loading local model from {model_path} ...")
        safe_threads = max(1, min(int(n_threads), 2))
        safe_ctx = max(1024, min(int(n_ctx), 2048))
        self.llm = Llama(model_path=model_path, n_ctx=safe_ctx, n_threads=safe_threads, use_mlock=False, use_mmap=True, verbose=False)
        self.budgeter = CognitiveBudgeter(max_context_tokens=safe_ctx)
        log_event("llm_bridge", f"local model loaded from models/{subdir}/ (n_ctx={safe_ctx}, n_threads={safe_threads}).")

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

    # Response-time fix: with N configured keys, the old code could
    # block for up to N * (connect_timeout + read_timeout) seconds --
    # e.g. 6 keys * ~10.5s worst case ~= 63s -- before ever falling
    # back to local/degraded mode, because there was no ceiling on the
    # *total* time spent rotating through keys, only a per-key one.
    # This wall-clock budget caps the whole rotation regardless of how
    # many keys are configured, so a bad key (or a flaky network mid-
    # rotation) can no longer multiply response latency turn after turn.
    MAX_TOTAL_SECONDS = 12.0

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
        # SECOND PROVIDER (UK's explicit ask): Gemini, via Google's own
        # OpenAI-compatible endpoint -- so this reuses the SAME request/
        # response handling below, just a different base_url/key/model.
        # Optional: if GEMINI_API_KEY isn't set, gemini_available()
        # returns False and every caller degrades to Groq-only, exactly
        # as before this was added.
        gemini_keys_raw = os.getenv("GEMINI_API_KEY") or ""
        self.gemini_api_keys = [k.strip() for k in gemini_keys_raw.replace(" ", "").split(",") if k.strip()]
        self.gemini_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        self.gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
        self._gemini_current_index = 0

    def gemini_available(self) -> bool:
        return bool(self.gemini_api_keys)

    def _post_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Shared multi-key rotation + budget-bounded POST, factored out
        of generate() so generate_with_tools() (added for M2 tool-
        calling, 2026-09) can reuse the exact same rotation/timeout
        discipline instead of duplicating it -- returns the raw
        response JSON; callers pull out whichever part of `message`
        they need (plain .content for generate(), the full message
        dict incl. tool_calls for generate_with_tools())."""
        url = f"{self.base_url}/chat/completions"
        total_keys = len(self.api_keys)
        last_error = None
        deadline = time.time() + self.MAX_TOTAL_SECONDS
        for attempt in range(total_keys):
            remaining = deadline - time.time()
            if remaining <= 0.5:
                last_error = last_error or f"Groq rotation budget ({self.MAX_TOTAL_SECONDS}s) exhausted"
                break
            key_index = self._current_index
            self._current_index = (self._current_index + 1) % total_keys
            active_key = self.api_keys[key_index]
            key_num = key_index + 1
            headers = {"Authorization": f"Bearer {active_key}", "Content-Type": "application/json"}
            per_call_read_timeout = max(1.0, min(self.timeout, remaining - 0.5))
            try:
                log_event("llm_bridge", f"groq key #{key_num}/{total_keys} | model: {self.model}{' | tools' if payload.get('tools') else ''}")
                resp = requests.post(url, headers=headers, json=payload, timeout=(2.5, per_call_read_timeout))
                if resp.status_code in (404, 401, 403, 429):
                    log_event("llm_bridge", f"groq key #{key_num} failed HTTP {resp.status_code}: {resp.text.strip()[:200]}", level="warning")
                    last_error = f"HTTP {resp.status_code} ({resp.text.strip()})"
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                log_event("llm_bridge", f"groq key #{key_num} error: {exc}. trying next key...", level="warning")
                last_error = exc
        raise RuntimeError(f"Groq request failed within {self.MAX_TOTAL_SECONDS}s budget. Last error: {last_error}")

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7,
                 response_format: Optional[Dict[str, Any]] = None) -> str:
        # THE ACTUAL BUG UK CAUGHT LIVE, from the real terminal/web
        # logs: "groq API failed: name 'model' is not defined". This
        # method's signature never had a `model` parameter -- an
        # unfinished multi-provider (Gemini) edit left a reference to
        # a name that didn't exist here, so EVERY Groq call raised a
        # NameError and fell straight to "LLM unavailable". Reverted
        # to always using self.model (openai/gpt-oss-120b by default,
        # UK's explicit instruction) -- no per-call override at this
        # level.
        payload = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}], "temperature": temperature, "max_tokens": max_tokens}
        # ANOTHER ACTUAL BUG (found 2026-09-11 from real monitor.py
        # output: every single perception extraction showed
        # "primary:fail -> refined:fail -> safe_fallback"). Verified
        # against Groq's docs: openai/gpt-oss-120b is a REASONING
        # model -- asking it to "return ONLY valid JSON" in the system
        # prompt alone is unreliable, it can emit reasoning/preamble
        # text around the JSON even at temperature=0. response_format
        # was never set anywhere in this file, so every JSON-extraction
        # caller (perception.py, blueprint_brain.py's semantic
        # fallback) was silently relying on the model just happening
        # to behave -- which it mostly didn't, hence fallback_active
        # being true on nearly every turn. json_object mode (not the
        # stricter json_schema mode -- community-reported regression
        # risk for gpt-oss-120b as of Oct 2025) guarantees valid JSON
        # syntax at the API level, no more prompt-only hoping.
        if response_format:
            payload["response_format"] = response_format
        data = self._post_chat_completion(payload)
        return data["choices"][0]["message"]["content"].strip()

    def generate_with_tools(self, messages: list, tools: list, tool_choice: str = "auto",
                             max_tokens: int = 1024, temperature: float = 0.7,
                             reasoning_effort: Optional[str] = None) -> Dict[str, Any]:
        """Tool-calling entry point (M2, 2026-09-11 design discussion:
        cortex-basal-ganglia inspired -- the model PROPOSES a tool
        call here; it is Brain/tool_registry.py's job to GATE it
        (validate the referenced knowledge_id actually exists, etc.)
        before anything is actually executed -- see
        core/orchestration/tool_registry.py's run_tool_loop()).

        Unlike generate(), takes the full `messages` array (tool
        calling is inherently multi-turn within one logical exchange:
        assistant proposes a call -> a "tool" role message carries the
        result back -> model produces the final answer) and returns
        the full assistant message dict (content + tool_calls +
        executed_tools for built-in tools like browser_search), not
        just plain text, since the structured parts are exactly what
        the caller needs to act on.
        """
        payload = {"model": self.model, "messages": messages, "temperature": temperature,
                   "max_tokens": max_tokens, "tools": tools, "tool_choice": tool_choice}
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        data = self._post_chat_completion(payload)
        return data["choices"][0]["message"]


class HybridLLMBridge:
    CONNECTIVITY_CHECK_INTERVAL_SECONDS = 15
    CONNECTIVITY_TEST_HOST = "8.8.8.8"
    CONNECTIVITY_TEST_PORT = 53
    CONNECTIVITY_TIMEOUT = 1.5

    def __init__(self, model_filename: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx: int = 2048, n_threads: int = 2, force_mode: Optional[str] = None):
        self._model_filename = model_filename
        self._n_ctx = n_ctx
        self._n_threads = n_threads
        self._force_mode = force_mode
        self._groq_engine: Optional[GroqEngine] = None
        self._local_engine: Optional[LlamaCppEngine] = None
        self._slm_engine: Optional[LlamaCppEngine] = None
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
        # Per-LEVEL sub-budget (on top of the flat total above) -- see
        # config/cognition.json's max_calls_per_level. This is the
        # concrete implementation of the explicit budget model: at most
        # 2 calls at each of three conceptual levels (perception+
        # understanding, cognition-to-response, post-response reasoning/
        # evolution), typically 1 each (3 total), worst case 2 each (6
        # total) -- never a single flat pool where one greedy level
        # could silently starve the others.
        self._max_calls_per_level = 2
        self._level_calls: Dict[str, int] = {}
        self._level_overrides: Dict[str, int] = {}
        self._context_budgeter = CognitiveBudgeter(max_context_tokens=n_ctx)
        self._load_budget_policy()
        # LOCKED model choices (config/models.json is the single source of
        # truth -- see that file's "_locked_note"). Falls back to these
        # Python defaults only if the config file is missing/unreadable,
        # so a fresh checkout without config/ still boots.
        self._offline_model_config = {"subdir": "Offline_LLM", "model_filename": model_filename, "n_ctx": n_ctx, "n_threads": n_threads}
        self._slm_model_config = {"subdir": "SLM", "model_filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf", "n_ctx": 2048, "n_threads": 2}
        self._load_model_policy()

    def _load_model_policy(self) -> None:
        config_path = os.path.join(BASE_DIR, "config", "models.json")
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                models = json.load(handle)
            if isinstance(models.get("offline_llm"), dict):
                self._offline_model_config.update({
                    "subdir": models["offline_llm"].get("subdir", self._offline_model_config["subdir"]),
                    "model_filename": models["offline_llm"].get("model_filename", self._offline_model_config["model_filename"]),
                    "n_ctx": int(models["offline_llm"].get("n_ctx", self._offline_model_config["n_ctx"])),
                    "n_threads": int(models["offline_llm"].get("n_threads", self._offline_model_config["n_threads"])),
                })
            if isinstance(models.get("slm"), dict):
                self._slm_model_config.update({
                    "subdir": models["slm"].get("subdir", self._slm_model_config["subdir"]),
                    "model_filename": models["slm"].get("model_filename", self._slm_model_config["model_filename"]),
                    "n_ctx": int(models["slm"].get("n_ctx", self._slm_model_config["n_ctx"])),
                    "n_threads": int(models["slm"].get("n_threads", self._slm_model_config["n_threads"])),
                })
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass  # config/models.json missing/malformed -- keep the hardcoded defaults above

    def _load_budget_policy(self) -> None:
        config_path = os.path.join(BASE_DIR, "config", "cognition.json")
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                llm = json.load(handle).get("llm", {})
            self._budget_max_calls = max(1, int(llm.get("max_calls_per_turn", self._budget_max_calls)))
            self._budget_max_output_tokens = max(1, int(llm.get("max_output_tokens_per_turn", self._budget_max_output_tokens)))
            self._budget_semantic_tokens = max(1, int(llm.get("semantic_fallback_tokens", self._budget_semantic_tokens)))
            self._max_calls_per_level = max(1, int(llm.get("max_calls_per_level", self._max_calls_per_level)))
            overrides = llm.get("max_calls_per_level_overrides")
            self._level_overrides = {str(k): max(1, int(v)) for k, v in overrides.items()} if isinstance(overrides, dict) else {}
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def begin_turn_budget(self) -> None:
        self._load_budget_policy()
        self._turn_calls = 0
        self._turn_reserved_tokens = 0
        self._turn_active = True
        self._level_calls = {}

    def budget_status(self) -> Dict[str, Any]:
        return {
            "active": self._turn_active, "calls": self._turn_calls, "max_calls": self._budget_max_calls,
            "reserved_output_tokens": self._turn_reserved_tokens, "max_output_tokens": self._budget_max_output_tokens,
            "remaining_calls": max(0, self._budget_max_calls - self._turn_calls),
            "remaining_output_tokens": max(0, self._budget_max_output_tokens - self._turn_reserved_tokens),
            "max_calls_per_level": self._max_calls_per_level,
            "level_calls": dict(self._level_calls),
        }

    def _reserve_budget(self, requested_tokens: int, level: Optional[str] = None) -> int:
        if not self._turn_active:
            self.begin_turn_budget()
        requested = max(1, int(requested_tokens))
        if self._turn_calls >= self._budget_max_calls:
            raise CognitiveBudgetExceeded(f"LLM call budget exceeded: {self._budget_max_calls} calls per turn")
        if level and self._level_calls.get(level, 0) >= self._level_overrides.get(level, self._max_calls_per_level):
            cap = self._level_overrides.get(level, self._max_calls_per_level)
            raise CognitiveBudgetExceeded(
                f"LLM per-level call budget exceeded: '{level}' already used "
                f"{self._level_calls.get(level, 0)}/{cap} calls this turn"
            )
        remaining = self._budget_max_output_tokens - self._turn_reserved_tokens
        # Hard budget: a request that doesn't fully fit in what's left
        # must be rejected, not silently clamped down to whatever
        # remains. The old `reserved = min(requested, remaining)` here
        # meant a caller asking for 512 tokens with only 256 left would
        # just get 256 back with no signal at all -- a silently
        # truncated response is a worse failure mode than a clear,
        # catchable CognitiveBudgetExceeded (which callers already
        # handle: Brain's LLM route wraps generate_response() in a
        # try/except, and the perception extraction cascade treats it
        # as a stage failure and escalates, exactly as intended).
        if remaining <= 0 or requested > remaining:
            raise CognitiveBudgetExceeded(
                f"LLM output-token budget exceeded: requested {requested} tokens but only "
                f"{max(0, remaining)} remain of the {self._budget_max_output_tokens}-token turn budget"
            )
        self._turn_calls += 1
        if level:
            self._level_calls[level] = self._level_calls.get(level, 0) + 1
        self._turn_reserved_tokens += requested
        return requested

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
            # Response-time / correctness fix: socket.setdefaulttimeout()
            # sets the timeout for every socket created ANYWHERE in this
            # process from this point on -- including the web server's
            # own sockets (backend/server.py, WebSocket connections) --
            # not just this one connectivity probe. That is a real,
            # process-wide side effect this connectivity check should
            # never have had. Set the timeout on this one socket
            # instance instead.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.CONNECTIVITY_TIMEOUT)
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
        """Full offline conversational fallback -- models/Offline_LLM/,
        used only when Groq (online) is unavailable. See config/models.json."""
        if self._local_engine is None:
            cfg = self._offline_model_config
            self._local_engine = LlamaCppEngine(model_filename=cfg["model_filename"], subdir=cfg["subdir"], n_ctx=cfg["n_ctx"], n_threads=cfg["n_threads"])
        return self._local_engine

    def get_slm_engine(self) -> LlamaCppEngine:
        """SLM tier -- models/SLM/, a separate, much smaller model used
        ONLY for narrow classification/disambiguation (blueprint LEVEL
        4/5, see core/orchestration/slm_bridge.py). Deliberately a
        DIFFERENT engine instance from _get_local()'s offline-chat
        model -- these are two distinct roles with two distinct model
        sizes, not the same model wearing two hats."""
        if self._slm_engine is None:
            cfg = self._slm_model_config
            self._slm_engine = LlamaCppEngine(model_filename=cfg["model_filename"], subdir=cfg["subdir"], n_ctx=cfg["n_ctx"], n_threads=cfg["n_threads"])
        return self._slm_engine

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7, level: Optional[str] = None) -> str:
        return self.generate_response(system_prompt=system_prompt, user_input=user_input, max_tokens=max_tokens, temperature=temperature, level=level)

    def generate_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
                             tool_choice: str = "auto", max_tokens: int = 1024, temperature: float = 0.7,
                             level: Optional[str] = None, reasoning_effort: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Tool-calling entry point at the Hybrid (online/offline-aware)
        level. Unlike generate_response(), this deliberately does NOT
        fall back to the offline local GGUF model -- tool-calling
        reliability on a 1.5B quantized local model is not something
        to depend on, and the local model was never used for anything
        beyond plain conversational fallback to begin with. Returns
        None (not a string) when tool-calling isn't available right
        now (offline, no Groq key, or budget exhausted) -- callers
        (see core/orchestration/tool_registry.py) must treat None as
        "fall back to the plain conversational path", not as an error
        to surface to the user."""
        reserved_tokens = self._reserve_budget(max_tokens, level=level)
        online = self._is_online()
        have_groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY"))
        if not (online and have_groq_key):
            self.last_backend = "tools_unavailable_offline"
            return None
        try:
            message = self._get_groq().generate_with_tools(
                messages=messages, tools=tools, tool_choice=tool_choice,
                max_tokens=reserved_tokens, temperature=temperature, reasoning_effort=reasoning_effort,
            )
            self.last_error = None
            self.is_ready = True
            self.last_backend = "groq_tools"
            return message
        except Exception as exc:
            self.last_error = str(exc)
            self.last_backend = "groq_tools_error"
            log_event("llm_bridge", f"groq tool-call failed: {exc}", level="error")
            return None

    def generate_response(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7, level: Optional[str] = None, **kwargs) -> str:
        reserved_tokens = self._reserve_budget(max_tokens, level=level)
        bounded_system, bounded_user = self._context_budgeter.optimize_payload(system_prompt, user_input, max_tokens=reserved_tokens)
        online = self._is_online()
        have_groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY"))
        allow_local_fallback = self._force_mode == "offline" or os.getenv("JARVIS_ALLOW_LOCAL_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
        # Safety gate: online failures must not silently instantiate the
        # Offline_LLM GGUF (1.5B, still real RAM/CPU cost) on mobile/PRoot.
        # Keep local fallback explicitly opt-in twice.
        heavy_local_opt_in = os.getenv("JARVIS_ENABLE_HEAVY_LOCAL_MODEL", "false").strip().lower() in {"1", "true", "yes", "on"}
        allow_local_fallback = allow_local_fallback and (self._force_mode == "offline" or heavy_local_opt_in)
        if online and have_groq_key:
            try:
                result = self._get_groq().generate(system_prompt=bounded_system, user_input=bounded_user, max_tokens=reserved_tokens, temperature=temperature, response_format=kwargs.get("response_format"))
                self.last_error = None
                self.is_ready = True
                self.last_backend = "groq"
                return result
            except Exception as exc:
                self.last_error = str(exc)
                self.last_backend = "groq_error"
                log_event("llm_bridge", f"groq API failed: {exc}", level="error")
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


def can_afford_another_llm_call(llm_bridge: Any, min_calls_remaining_after: int = 1) -> bool:
    """Shared budget-awareness guard (blueprint: no retry mechanism may
    greedily spend the whole shared per-turn budget on itself).

    Originally lived only inside LLMPerceptionProvider -- but adding a
    SECOND independent retry stage (semantic understanding's own LLM
    fallback, see blueprint_brain.py's _configure_semantic_fallback)
    means the same discipline is needed in two places now. Extracted
    here once rather than duplicated, so both call sites stay in sync
    with however the budget system evolves.

    Worst case per turn with both retries possible: perception
    (primary+refined=2) + semantic understanding (primary+refined=2) +
    main response (1) = 5 calls -- see config/cognition.json's
    max_calls_per_turn, which is sized with this in mind.
    """
    budget_status = getattr(llm_bridge, "budget_status", None)
    if not callable(budget_status):
        return True  # bridge doesn't expose budget info; nothing to guard against
    try:
        status = budget_status()
    except Exception:
        return True
    remaining_calls = status.get("remaining_calls")
    if remaining_calls is None:
        return True
    return remaining_calls > min_calls_remaining_after
