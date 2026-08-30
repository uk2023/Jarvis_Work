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

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
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
                print(f"[JARVIS LLM] Groq Key #{key_num}/{total_keys} | Model: {self.model}")
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

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

        raise RuntimeError(f"All {total_keys} Groq API keys failed. Last error: {last_error}")


class HybridLLMBridge:
    CONNECTIVITY_CHECK_INTERVAL_SECONDS = 15
    CONNECTIVITY_TEST_HOST = "8.8.8.8"
    CONNECTIVITY_TEST_PORT = 53
    CONNECTIVITY_TIMEOUT = 1.5

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
        self.is_ready: bool = False

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