# -*- coding: utf-8 -*-
"""
Endpoints consumed by the V6 React/TypeScript frontend (web_frontend/,
built from JARVIS_v6-main). Every one of these used to be served by a
Node/Express mock (server.ts) that fabricated numbers with
Math.random(). None of that ships here -- every field below is read
from the live jarvis/brain/memory/goal_manager/evolution objects via
backend/integration.py, or from the same SQLite chat history used by
the CLI and the legacy dashboard.

Endpoint <-> frontend contract (see web_frontend/src/types.ts + App.tsx):
    GET    /api/organism/state        -> OrganismTelemetry (no wrapper)
    GET    /api/memory/engrams        -> { engrams: EngramFact[] }
    POST   /api/memory/engrams        -> { engram: EngramFact }
    DELETE /api/memory/engrams/{id}   -> { status }
    GET    /api/autonomy/state        -> { goals, proposals }
    POST   /api/autonomy/trigger-idle -> { goal: CuriosityGoal }
    POST   /api/chat                  -> { jarvisMessage: ChatMessage }
"""
import json
import resource
import time
import traceback
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import database
from . import integration
from .ws_manager import debug_log
from core.organism.organ_descriptions import describe_organ

router = APIRouter()


# =====================================================================
# HELPERS
# =====================================================================

def _resident_memory_mb() -> float:
    """
    Real resident-set-size of THIS process, in MB. Uses the stdlib
    `resource` module (ru_maxrss is KB on Linux/Android/Termux, which
    is the deployment target here) instead of pulling in psutil as a
    dependency just for one number.
    """
    try:
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(kb / 1024.0, 1)
    except Exception:
        return 0.0


def _knowledge_to_engram(item) -> dict:
    """Knowledge dataclass -> EngramFact shape (src/types.ts)."""
    d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
    return {
        "id": d.get("knowledge_id"),
        "subject": d.get("subject"),
        "predicate": d.get("predicate"),
        "value": d.get("value"),
        "confidence": d.get("confidence", 0.5),
        "importance": d.get("importance", 0.5),
        "evidenceCount": d.get("evidence_count", 1),
        "source": d.get("source") or "unknown",
        "tags": d.get("tags") or [],
        "createdAt": int((d.get("created_at") or time.time()) * 1000),
        "updatedAt": int((d.get("updated_at") or time.time()) * 1000),
        "faissId": d.get("faiss_id", 0) or 0,
        # SemanticMemory doesn't track a separate pending/accepted
        # state on Knowledge itself -- anything actually persisted
        # here already passed through KnowledgeBuilder/SelfEvaluator
        # (or was inserted directly via this API), so it's accurate
        # to report it as ACCEPTED rather than invent a fake pipeline
        # stage the object doesn't actually carry.
        "status": "ACCEPTED",
    }


def _goal_to_curiosity_goal(g: dict) -> dict:
    origin = g.get("origin", "user")
    if origin not in ("user", "curiosity", "self"):
        origin = "self"
    return {
        "id": g.get("id"),
        "text": g.get("text"),
        "priority": g.get("priority", 0.5),
        "status": g.get("status", "pending"),
        "origin": origin,
        "progress": g.get("progress") or [],
        "createdAt": int((g.get("created_at") or time.time()) * 1000),
    }


def _proposal_to_evolution_proposal(p: dict) -> dict:
    trigger = p.get("trigger") or {}
    return {
        "id": p.get("id"),
        "target": p.get("target"),
        "reason": p.get("reason"),
        "status": p.get("status", "PROPOSED"),
        "score": trigger.get("evaluation_score", 0.5),
        "createdAt": int((p.get("created_at") or time.time()) * 1000),
    }


# =====================================================================
# GET /api/organism/state
# =====================================================================

@router.get("/api/organism/state")
async def organism_state():
    jarvis = integration.jarvis
    if jarvis is None:
        return JSONResponse(
            {"status": "error", "message": "Organism not initialized in this process."},
            status_code=503,
        )

    try:
        hb = jarvis.heartbeat.status() if hasattr(jarvis, "heartbeat") and jarvis.heartbeat else {}
        beat_count = hb.get("beat_count", 0)
        is_idle = hb.get("is_idle", True)
        interval = hb.get("interval", 5.0) or 5.0
        uptime = hb.get("uptime", 0.0)

        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        brain_status = brain.status() if brain and hasattr(brain, "status") else {}

        organs_status = jarvis.get_organ_status() if hasattr(jarvis, "get_organ_status") else {}
        organs = []
        for name, info in organs_status.items():
            attached = info.get("attached", False)
            organs.append({
                "name": name,
                "classType": info.get("type", "Subsystem"),
                "isAttached": attached,
                "role": describe_organ(jarvis, name, info),
                "metrics": "online" if attached else "offline",
                "health": "green" if attached else "red",
            })

        # Async learning queue lives inside Brain, not jarvis.organs --
        # surface it as one more organ row so the web UI sees it too.
        queue_status = brain_status.get("async_learning_queue", {})
        organs.append({
            "name": "async_learning_queue",
            "classType": "Background Thread",
            "isAttached": bool(queue_status.get("alive", False)),
            "role": "Ordered background learning worker (response sync, learning async)",
            "metrics": (
                f"pending={queue_status.get('pending', 0)} "
                f"processed={queue_status.get('processed', 0)} "
                f"failed={queue_status.get('failed', 0)}"
            ),
            "health": "green" if queue_status.get("alive") else "yellow",
        })

        # "llm" is likewise never a registered jarvis organ -- it's
        # just brain.llm assigned post-hoc, so it never appeared in
        # this list at all before. Sourced from the real
        # is_ready/last_error state (see llm_bridge.py's
        # verify_offline_ready()), not just "attribute exists".
        llm_bridge_for_organ = getattr(brain, "llm", None) if brain else None
        if llm_bridge_for_organ is not None:
            llm_ready = getattr(llm_bridge_for_organ, "is_ready", False)
            llm_error = getattr(llm_bridge_for_organ, "last_error", None)
            organs.append({
                "name": "llm",
                "classType": "HybridLLMBridge",
                "isAttached": True,
                "role": "Local LLM Neural Bridge (Qwen 2.5 LlamaCpp Interface)",
                "metrics": "verified loaded" if llm_ready else (f"error: {llm_error}" if llm_error else "not yet verified"),
                "health": "green" if llm_ready else ("red" if llm_error else "yellow"),
            })
        else:
            organs.append({
                "name": "llm",
                "classType": "HybridLLMBridge",
                "isAttached": False,
                "role": "Local LLM Neural Bridge (Qwen 2.5 LlamaCpp Interface)",
                "metrics": "brain.llm is None -- never connected",
                "health": "red",
            })

        llm_bridge = getattr(brain, "llm", None) if brain else None
        # THE ACTUAL BUG: this used to read llm_bridge.model_path,
        # an attribute that has never existed on HybridLLMBridge (the
        # real attribute is the private _model_filename) -- so this
        # ALWAYS fell through to the hardcoded fallback string below,
        # regardless of whether the model was actually loaded, failed
        # to import, or was never connected at all. That's the "dummy
        # data" the UI kept showing no matter what was really going
        # on. Now it reports genuine state via is_ready/last_error
        # (see llm_bridge.py's verify_offline_ready()).
        if llm_bridge is None:
            active_model = "disconnected"
        elif getattr(llm_bridge, "is_ready", False):
            active_model = f"{getattr(llm_bridge, '_model_filename', 'unknown.gguf')} (offline, verified)"
        elif getattr(llm_bridge, "last_error", None):
            active_model = f"MODEL LOAD FAILED: {llm_bridge.last_error}"
        else:
            active_model = f"{getattr(llm_bridge, '_model_filename', 'unknown.gguf')} (not yet verified)"

        telemetry = {
            "pulseState": "idle" if is_idle else "active",
            "beatCount": beat_count,
            # Real bpm derived from the heartbeat's actual interval,
            # not a random number -- 60s / interval-seconds.
            "bpm": round(60.0 / interval, 1),
            "pulseWave": "SYS_UPTIME",
            "runtimeSeconds": round(uptime, 1),
            "isIdle": is_idle,
            "activeModel": str(active_model),
            "ramUsageMB": _resident_memory_mb(),
            "totalTokensProcessed": brain_status.get("total_tokens_estimate", 0),
            "avgLatencyMs": brain_status.get("avg_latency_ms", 0.0),
            "organs": organs,
        }
        return JSONResponse(telemetry)
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"organism_state Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# =====================================================================
# MEMORY ENGRAMS
# =====================================================================

@router.get("/api/memory/engrams")
async def list_engrams():
    brain = integration.brain
    if brain is None or brain.memory is None:
        return JSONResponse({"status": "success", "engrams": []})

    try:
        items = brain.memory.list_all_knowledge(limit=500)
        engrams = [_knowledge_to_engram(item) for item in items]
        return JSONResponse({"status": "success", "engrams": engrams})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"list_engrams Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/api/memory/engrams")
async def add_engram(payload: dict):
    brain = integration.brain
    if brain is None or brain.memory is None:
        return JSONResponse({"status": "error", "message": "Memory organ not connected."}, status_code=503)

    subject = (payload or {}).get("subject")
    predicate = (payload or {}).get("predicate")
    value = (payload or {}).get("value")
    tags = (payload or {}).get("tags") or []

    if not subject or not predicate or value in (None, ""):
        return JSONResponse(
            {"status": "error", "message": "subject, predicate and value are required."},
            status_code=400,
        )

    try:
        knowledge = brain.memory.remember_knowledge(
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=0.9,   # manually entered via UI -> high confidence
            importance=0.6,
            source="web_ui_manual_entry",
            tags=tags,
        )
        return JSONResponse({"status": "success", "engram": _knowledge_to_engram(knowledge)})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"add_engram Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.delete("/api/memory/engrams/{knowledge_id}")
async def delete_engram(knowledge_id: str):
    brain = integration.brain
    if brain is None or brain.memory is None:
        return JSONResponse({"status": "error", "message": "Memory organ not connected."}, status_code=503)

    try:
        deleted = brain.memory.forget_knowledge(knowledge_id)
        return JSONResponse({"status": "success" if deleted else "not_found", "id": knowledge_id})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"delete_engram Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# =====================================================================
# AUTONOMY
# =====================================================================

@router.get("/api/autonomy/state")
async def autonomy_state():
    jarvis = integration.jarvis
    if jarvis is None:
        return JSONResponse({"status": "success", "goals": [], "proposals": []})

    try:
        goal_manager = jarvis.get_organ("goal_manager") if hasattr(jarvis, "get_organ") else None
        goals = [_goal_to_curiosity_goal(g) for g in (goal_manager.goals if goal_manager else [])]

        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        evolution = getattr(brain, "evolution", None) if brain else None
        proposals = []
        if evolution is not None and hasattr(evolution, "list_proposals"):
            proposals = [_proposal_to_evolution_proposal(p) for p in evolution.list_proposals(limit=50)]

        return JSONResponse({"status": "success", "goals": goals, "proposals": proposals})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"autonomy_state Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/api/autonomy/trigger-idle")
async def trigger_idle():
    """
    Runs one REAL idle cycle right now (core/autonomy/idle_loop.py),
    instead of waiting for the next heartbeat pulse -- this is the
    "Trigger Idle Curiosity Cycle" button. It's the exact same
    idle_loop.step() the heartbeat calls automatically when idle; this
    just calls it on demand and reports back whichever goal actually
    changed as a result.
    """
    jarvis = integration.jarvis
    if jarvis is None:
        return JSONResponse({"status": "error", "message": "Organism not initialized."}, status_code=503)

    idle_loop = jarvis.get_organ("idle_loop") if hasattr(jarvis, "get_organ") else None
    goal_manager = jarvis.get_organ("goal_manager") if hasattr(jarvis, "get_organ") else None

    if idle_loop is None or goal_manager is None:
        return JSONResponse({"status": "error", "message": "Autonomy organs not attached."}, status_code=503)

    try:
        before_ids = {g["id"] for g in goal_manager.goals}
        result = idle_loop.step()

        # Prefer a goal that's genuinely new/changed this cycle so the
        # UI reflects what actually happened, not just "the newest
        # goal in the list" (which might be unrelated/older).
        new_goals = [g for g in goal_manager.goals if g["id"] not in before_ids]
        if new_goals:
            chosen = new_goals[-1]
        else:
            target_text = result.get("goal")
            chosen = next((g for g in reversed(goal_manager.goals) if g.get("text") == target_text), None)

        if chosen is None:
            # Genuinely nothing changed this cycle -- report that
            # honestly instead of fabricating a goal.
            chosen = {
                "id": f"idle-noop-{int(time.time())}",
                "text": f"Idle cycle ran, no change ({result.get('action', 'noop')}: {result.get('reason', 'no pending work')})",
                "priority": 0.1,
                "status": "completed",
                "origin": "self",
                "progress": [],
                "created_at": time.time(),
            }

        return JSONResponse({"status": "success", "goal": _goal_to_curiosity_goal(chosen), "cycle_result": result})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"trigger_idle Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# =====================================================================
# CHAT (REST alternative to the /ws socket, same real pipeline)
# =====================================================================

@router.post("/api/chat")
async def chat_v6(payload: dict):
    """
    Same underlying executor as the websocket path (routes_ws.py) --
    cli.py's execute_cognitive_query(), which calls the real
    brain.think_and_respond(). Both surfaces persist to the same
    SQLite chat history and build their trace from the same
    brain.last_turn_trace, so nothing here is simulated or duplicated
    logic that could drift from the CLI/websocket behaviour.
    """
    executor = integration.get_query_executor()
    if executor is None:
        return JSONResponse({"status": "error", "message": "Cognitive engine not bound yet."}, status_code=503)

    message = (payload or {}).get("message", "")
    session_id = (payload or {}).get("sessionId") or "main_session"
    if not message.strip():
        return JSONResponse({"status": "error", "message": "message is required."}, status_code=400)

    try:
        database.save_message_to_db(session_id=session_id, sender="user", text=message, source="web")

        reply = await asyncio.to_thread(executor, message, "web")
        reply_str = str(reply)

        trace = getattr(integration.brain, "last_turn_trace", None) if integration.brain else None
        trace_log_payload = None
        extracted_fact = None

        if trace:
            timings = trace.get("timings", {})
            queue = trace.get("learning_queue", {})
            pipeline_status = "queued"
            if queue.get("pending", 0) == 0 and queue.get("processed", 0) > 0:
                pipeline_status = "consolidated"

            trace_log_payload = {
                "traceId": f"trc-{int(trace.get('timestamp', time.time()) * 1000)}",
                "latencySeconds": timings.get("total", 0.0),
                "memoryLookupSeconds": timings.get("memory", 0.0),
                "llmInferenceSeconds": timings.get("llm", 0.0),
                "vectorMatches": trace.get("vector_matches", []),
                "graphRelations": trace.get("graph_edges", []),
                "learningPipelineStatus": pipeline_status,
                "typosCorrected": trace.get("typos_corrected", []),
            }

            signal = trace.get("memory_signal")
            if signal:
                extracted_fact = {
                    "subject": signal.get("subject"),
                    "predicate": signal.get("predicate"),
                    "value": signal.get("value"),
                    "confidence": 0.7,
                }

        message_id = database.save_message_to_db(
            session_id=session_id,
            sender="jarvis",
            text=reply_str,
            source="web",
            trace_log=json.dumps(trace_log_payload) if trace_log_payload else None,
            extracted_fact=json.dumps(extracted_fact) if extracted_fact else None,
        )

        jarvis_message = {
            "id": str(message_id) if message_id else f"msg-{int(time.time() * 1000)}-j",
            "sessionId": session_id,
            "sender": "jarvis",
            "text": reply_str,
            "timestamp": time.strftime("%H:%M:%S"),
            "source": "web",
            "traceLog": trace_log_payload,
            "extractedFact": extracted_fact,
        }

        return JSONResponse({"status": "success", "jarvisMessage": jarvis_message})
    except Exception as e:
        err_str = traceback.format_exc()
        debug_log(f"chat_v6 Error:\n{err_str}", "bold red")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
