from __future__ import annotations

import json
import os
import re
import socket
import time
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

# Explicitly load .env relative to project root
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


class CognitiveBudgeter:
    """
    Biological Cognitive Working Memory & Dynamic Token Budgeter.
    Prevents context window overflow dynamically without hardcoded limits.
    """
    def __init__(self, max_context_tokens: int = 4096):
        self.max_context_tokens = max_context_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation (Word count * 1.3 + safety margin)."""
        if not text:
            return 0
        return int(len(text.split()) * 1.3) + 4

    def optimize_payload(
        self, system_prompt: str, user_input: str, max_tokens: int = 512
    ) -> tuple[str, str]:
        """
        Calculates token load dynamically. If system prompt/facts exceed context window capacity,
        it prunes facts from bottom up to avoid Llama model crash.
        """
        budget = self.max_context_tokens - max_tokens - 128  # Safety margin buffer
        
        sys_tokens = self.estimate_tokens(system_prompt)
        usr_tokens = self.estimate_tokens(user_input)
        
        if (sys_tokens + usr_tokens) <= budget:
            return system_prompt, user_input

        # Dynamic System Prompt Pruning (Line by line memory trimming)
        lines = system_prompt.split("\n")
        trimmed_lines = []
        current_tokens = usr_tokens

        for line in lines:
            line_tokens = self.estimate_tokens(line)
            if current_tokens + line_tokens <= budget:
                trimmed_lines.append(line)
                current_tokens += line_tokens
            else:
                break

        optimized_system_prompt = "\n".join(trimmed_lines)
        return optimized_system_prompt, user_input


class LlamaCppEngine:
    """
    Offline local LLM Engine using llama-cpp-python.
    """
    def __init__(
        self,
        model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf",
        n_ctx: int = 4096,  # ✅ Default updated to 4096
        n_threads: int = 4,
    ):
        if Llama is None:
            raise ImportError("llama-cpp-python is not installed.")

        model_path = os.path.join(BASE_DIR, "models", model_filename)

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model file not found at: {model_path}. Place the GGUF file in models/"
            )

        print(f"[JARVIS LLM] Loading offline model from {model_path} ...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            # use_mlock pins pages in RAM (fights the OS out of swapping
            # them out); on an 8GB Android device that's a liability, not
            # a feature, so it stays off unless explicitly requested.
            use_mlock=False,
            # mmap keeps the resident set small until pages are actually
            # touched -- important headroom on 8GB RAM devices.
            use_mmap=True,
            verbose=False,
        )
        self.budgeter = CognitiveBudgeter(max_context_tokens=n_ctx)
        print(f"[JARVIS LLM] Offline model loaded (n_ctx={n_ctx}).")

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        # ✅ Apply Dynamic Cognitive Budgeting before model inference
        opt_system, opt_user = self.budgeter.optimize_payload(
            system_prompt, user_input, max_tokens=max_tokens
        )

        messages = [
            {"role": "system", "content": opt_system},
            {"role": "user", "content": opt_user},
        ]
        response = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response["choices"][0]["message"]["content"].strip()


class GroqEngine:
    """
    Groq API Engine with Auto-Model Sanitization, Multi-Key Rotation, and Detailed Debug Logging.
    """

    VALID_MODELS = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-20b",
        "groq/compound",
        "groq/compound-mini",
        "allam-2-7b",
    ]

    def __init__(
        self,
        api_keys: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 20.0,
    ):
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
        self.base_url = "https://api.groq.com/openai/v1"
        self.timeout = timeout
        self._current_index = 0

<<<<<<< HEAD
    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
=======
        # THE ACTUAL CRASH CAUSE (found 2026-09-15, from UK's own
        # spike-capture thread dumps).
        #
        # Every call here used the bare module-level `requests.post()`.
        # That function is a convenience wrapper that opens a brand new
        # `requests.Session()` -- and therefore a brand new TCP
        # connection and a FULL TLS handshake, including full
        # certificate-chain verification against the CA bundle -- for
        # EVERY SINGLE CALL, then tears it down. No connection pooling,
        # no keep-alive, nothing reused.
        #
        # UK's captured stack traces showed the RSS spike happening
        # with TWO THREADS simultaneously inside `ssl.do_handshake()` /
        # a blocking socket read, one from cli.py's direct query path
        # and one from the web backend's task_loop -- i.e. two
        # concurrent, fully independent TLS handshakes to the same
        # host (api.groq.com), each paying the full certificate-
        # verification cost from scratch, at the same moment. In this
        # proot/Termux environment that cost is apparently large enough
        # (roughly matching the observed ~1.7-2GB jumps) that two of
        # them at once is what was tipping the device into Android's
        # low-memory killer.
        #
        # A persistent Session reuses its underlying connection pool
        # (urllib3's HTTPAdapter) across calls to the same host: after
        # the first handshake, subsequent requests reuse the already-
        # verified TLS connection instead of repeating the full
        # handshake and certificate verification every time. This is
        # also simply the correct way to use `requests` for repeated
        # calls to the same API regardless of the memory angle.
        self._session = requests.Session()

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
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        total_keys = len(self.api_keys)
        last_error = None

        for attempt in range(total_keys):
            key_index = self._current_index
            self._current_index = (self._current_index + 1) % total_keys

            active_key = self.api_keys[key_index]
            key_num = key_index + 1

            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json",
            }

            try:
<<<<<<< HEAD
                print(f"[JARVIS LLM] Groq Key #{key_num}/{total_keys} | Model: {self.model}")
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

=======
                log_event("llm_bridge", f"groq key #{key_num}/{total_keys} | model: {self.model}{' | tools' if payload.get('tools') else ''}")
                resp = self._session.post(url, headers=headers, json=payload, timeout=(2.5, per_call_read_timeout))
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
                if resp.status_code in (404, 401, 403, 429):
                    print(f"[JARVIS LLM] Key #{key_num} failed HTTP {resp.status_code}: {resp.text.strip()}")
                    print(f"[JARVIS LLM] Switching key...")
                    last_error = f"HTTP {resp.status_code} ({resp.text.strip()})"
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

            except Exception as exc:
                print(f"[JARVIS LLM] Key #{key_num} error: {exc}. Trying next key...")
                last_error = exc

<<<<<<< HEAD
        raise RuntimeError(f"All {total_keys} Groq API keys failed. Last error: {last_error}")
=======
    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7,
                 response_format: Optional[Dict[str, Any]] = None, reasoning_effort: Optional[str] = None) -> str:
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
        # Bug 13 (latency, 2026-09-11): perception/semantic-fallback
        # calls are simple classification/extraction, not deep
        # reasoning -- gpt-oss-120b spends real time on internal
        # reasoning tokens by default even for these, adding latency
        # that never shows up in the final answer. Groq's own docs
        # recommend reasoning_effort="low" for exactly this kind of
        # call (they say the same for browser_search, already applied
        # there). This does NOT touch the main response-generation
        # call, which benefits from full reasoning.
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
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
>>>>>>> 90fbd2a (Save local project changes before branch checkout)


class HybridLLMBridge:
    CONNECTIVITY_CHECK_INTERVAL_SECONDS = 15
    CONNECTIVITY_TEST_HOST = "8.8.8.8"
    CONNECTIVITY_TEST_PORT = 53
    CONNECTIVITY_TIMEOUT = 1.5
    # See _reserve_budget(): tokens that preparatory calls (perception,
    # semantic fallback) may never consume, so the final reply always
    # has room to be generated.
    RESPONSE_TOKEN_FLOOR = 2000

    # =============================================================
    # ONE-CALL RESPONSE + MEMORY SIGNAL
    # =============================================================
    #
    # Architecture decision from the blueprint review: instead of
    # (1) a full call to generate the chat reply and then (2) a
    # SECOND full call just to extract a subject/predicate/value
    # fact triple out of the same turn, Qwen is asked to do both in
    # ONE call and return structured JSON. This halves LLM calls,
    # tokens, and latency per turn on the offline 3B model, which is
    # exactly where it matters most (Android, 8GB RAM).
    #
    # Qwen's job here is strictly: understand, reason, respond,
    # generate a memory SIGNAL. It never writes to the database
    # itself -- the signal is only a candidate that the learning
    # pipeline (ExperienceEngine -> SelfEvaluator -> KnowledgeBuilder)
    # evaluates and may accept. That separation is intentional and
    # must not be collapsed even when it's convenient to do so.
    _MEMORY_SIGNAL_INSTRUCTIONS = (
        "\n\nOUTPUT FORMAT (STRICT -- do not break this):\n"
        "Respond with ONLY one raw JSON object, no markdown fences, "
        "no text before or after it, matching exactly this shape:\n"
        '{"response": "<your natural in-character reply to the user>", '
        '"memory": {"has_fact": true|false, "subject": "<short lowercase phrase>", '
        '"predicate": "<short lowercase phrase>", "value": "<the fact>"}}\n'
        "Set memory.has_fact to true ONLY if the user's message stated a "
        "durable fact worth remembering long-term (a name, a preference, "
        "a relationship, a date, an event). The user often writes in "
        "Hinglish with typos -- correct typos silently and extract the "
        "clean fact. If no such fact exists in this turn, output exactly "
        '{"has_fact": false} for memory. Never omit the "response" field.'
    )

    @staticmethod
    def _parse_combined(raw: Any) -> Dict[str, Any]:
        """
        Parse a combined {response, memory} payload out of raw model
        output. Falls back to treating the whole output as the reply
        (with no memory signal) if the model didn't obey the JSON
        contract -- a malformed reply must never become an error the
        user sees, it should just mean "nothing learned this turn".
        """
        if not isinstance(raw, str) or not raw.strip():
            return {"response": "", "memory_signal": None}

        cleaned = re.sub(
            r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE
        ).strip()

        try:
            data = json.loads(cleaned)
        except Exception:
            return {"response": raw.strip(), "memory_signal": None}

        if not isinstance(data, dict) or "response" not in data:
            return {"response": raw.strip(), "memory_signal": None}

        memory_signal = None
        mem = data.get("memory")
        if isinstance(mem, dict) and mem.get("has_fact"):
            subject = str(mem.get("subject", "")).strip()
            predicate = str(mem.get("predicate", "")).strip()
            value = mem.get("value")
            if subject and predicate and value not in (None, ""):
                memory_signal = {
                    "subject": subject,
                    "predicate": predicate,
                    "value": value,
                }

        return {
            "response": str(data.get("response", "")).strip(),
            "memory_signal": memory_signal,
        }

    def generate_combined(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        ONE model call -> {"response": str, "memory_signal": dict|None}

        Replaces the old "generate reply, then separately re-call the
        model to extract a fact" pattern used by Brain.think_and_respond.
        """
        augmented_system_prompt = system_prompt + self._MEMORY_SIGNAL_INSTRUCTIONS
        raw = self.generate_response(
            system_prompt=augmented_system_prompt,
            user_input=user_input,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._parse_combined(raw)

    def __init__(
        self,
        model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf",
        n_ctx: int = 4096,  # ✅ Default updated to 4096
        n_threads: int = 4,
        force_mode: Optional[str] = None,
    ):
        self._model_filename = model_filename
        self._n_ctx = n_ctx
        self._n_threads = n_threads
        self._force_mode = force_mode

        self._groq_engine: Optional[GroqEngine] = None
        self._local_engine: Optional[LlamaCppEngine] = None

        self._last_check_time = 0.0
        self._last_online_result = False

        # THE ACTUAL BUG THIS FIXES: __init__ used to do nothing but
        # store config -- it never tried to load anything, so
        # constructing this class always "succeeded" even if
        # llama-cpp-python wasn't installed or the GGUF file was
        # missing. cli.py would print "Neural Bridge Online" no
        # matter what, and the real failure only ever surfaced later,
        # buried inside a chat reply's text ("[Model Generation
        # Error: ...]") that looked like a bad answer rather than a
        # startup failure. self.last_error and self.is_ready below
        # let callers (cli.py, the web /api/organism/state endpoint)
        # show the REAL state instead of assuming success.
        self.last_error: Optional[str] = None
<<<<<<< HEAD
        self.is_ready: bool = False
=======
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
        # PROTECTED FLOOR for the final reply (2026-09-12, from UK's
        # live trace: turns showing "tokens_used=2700/2700 ...
        # status=failed"). Perception and the semantic fallback are
        # PREPARATORY calls -- they exist to help produce an answer,
        # and it is never correct for them to consume so much of the
        # turn budget that the ANSWER itself can't be generated. Yet
        # nothing stopped them: they reserved from the same flat pool,
        # first-come-first-served, so two unlucky preparatory calls
        # could leave zero for the reply and the whole turn failed
        # with no output at all. Preparatory levels now can't touch
        # the last RESPONSE_TOKEN_FLOOR tokens; response generation
        # itself still draws from the full remaining pool.
        if level and level not in ("response_generation", None):
            usable = remaining - self.RESPONSE_TOKEN_FLOOR
            if usable <= 0 or requested > usable:
                raise CognitiveBudgetExceeded(
                    f"LLM output-token budget exceeded: '{level}' requested {requested} tokens but only "
                    f"{max(0, usable)} are available to preparatory calls (the last "
                    f"{self.RESPONSE_TOKEN_FLOOR} tokens are reserved for the final reply)"
                )
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
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

    def verify_offline_ready(self) -> bool:
        """
        Eagerly loads the local llama.cpp engine right now instead of
        waiting for the first chat message to discover it's broken.
        Call this once right after construction (see cli.py). Sets
        self.last_error / self.is_ready either way, and also means the
        model is already warm in RAM before the first real message
        instead of paying that load cost on the user's first turn.
        """
        try:
            self._get_local()
            self.is_ready = True
            self.last_error = None
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
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.CONNECTIVITY_TEST_HOST, self.CONNECTIVITY_TEST_PORT))
            s.close()
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
            self._local_engine = LlamaCppEngine(
                model_filename=self._model_filename,
                n_ctx=self._n_ctx,
                n_threads=self._n_threads,
            )
        return self._local_engine

    def generate_response(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        online = self._is_online()
        have_groq_key = bool(os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY"))

        if online and have_groq_key:
            try:
                engine = self._get_groq()
                result = engine.generate(
                    system_prompt=system_prompt,
                    user_input=user_input,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self.last_error = None
                self.is_ready = True
                return result
            except Exception as exc:
                print(f"[JARVIS LLM] Groq API failed ({exc}), falling back to offline model.")

        try:
            engine = self._get_local()
            result = engine.generate(
                system_prompt=system_prompt,
                user_input=user_input,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            self.last_error = None
            self.is_ready = True
<<<<<<< HEAD
=======
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
                result = self._get_groq().generate(system_prompt=bounded_system, user_input=bounded_user, max_tokens=reserved_tokens, temperature=temperature, response_format=kwargs.get("response_format"), reasoning_effort=kwargs.get("reasoning_effort"))
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
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
            return result
        except Exception as exc:
            # This string used to be the ONLY place a broken model
            # setup ever became visible -- and it looked like a
            # (bad) chat reply rather than a system fault. It's kept
            # here as a last-resort safety net, but verify_offline_
            # ready() below is what should actually catch this at
            # startup now.
            self.last_error = str(exc)
            self.is_ready = False
            return f"[Model Generation Error: {exc}]"


# Backward compatibility alias for cli.py and brain.py
LlamaCppBridge = HybridLLMBridge