# -*- coding: utf-8 -*-
"""The single /ws realtime endpoint: chat messages, ping/pong, thinking sync."""
import asyncio
import json
import time
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import database, integration
from .ws_manager import (
    active_connections,
    debug_log,
    broadcast_to_clients,
    set_thinking,
    thinking_snapshot,
)
from .config import get_local_ist_timestamp

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    client_host = websocket.client.host if websocket.client else "Unknown"
    debug_log(f"WebSocket Connected: {client_host}", "green")

    # As soon as a client connects, push it a snapshot of every session
    # that is currently mid-query. This is what makes the "Thinking..."
    # bubble survive refresh / backgrounding / thread-switching.
    snapshot = thinking_snapshot()
    if snapshot:
        try:
            await websocket.send_json({"type": "thinking_sync", "sessions": snapshot})
        except Exception:
            pass

    try:
        while True:
            # Don't let a single receive_text() call block forever with no
            # signal to the outside world. A short timeout here just lets
            # the loop check in periodically -- it does NOT close the
            # connection on timeout, it just avoids the socket looking
            # "dead" from the server's perspective while genuinely idle.
            try:
                raw_data = await asyncio.wait_for(websocket.receive_text(), timeout=45)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    break
                continue

            # A malformed frame must never kill the socket -- it used to
            # bubble up and force a reconnect, which was a big part of why
            # the CLI showed rapid Connected/Disconnected flapping.
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                debug_log(f"Ignoring malformed WS frame: {raw_data[:120]}", "bold red")
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "user_message":
                await _handle_user_message(websocket, data)

    except WebSocketDisconnect:
        debug_log(f"WebSocket Disconnected: {client_host}", "yellow")
    except Exception as ws_err:
        debug_log(f"WebSocket Exception: {ws_err}", "bold red")
    finally:
        active_connections.discard(websocket)


async def _handle_user_message(websocket: WebSocket, data: dict):
    user_text = data.get("text", "")
    session_id = data.get("session_id", "main_session")
    debug_log(f"Processing Query [{session_id}]: '{user_text}'", "bold cyan")

    database.save_message_to_db(session_id=session_id, sender="user", text=user_text, source="web")

    broadcast_to_clients(
        {
            "type": "chat_sync",
            "sender": "user",
            "text": user_text,
            "session_id": session_id,
            "source": "web",
        },
        exclude_ws=websocket,
    )

    executor = integration.get_query_executor()
    if not executor:
        await websocket.send_json({
            "type": "chat_error",
            "text": "Query Executor Engine Not Bound.",
        })
        return

    set_thinking(session_id, True)
    start_time = time.time()
    try:
        reply = await asyncio.to_thread(executor, user_text, "web")
        latency = round(time.time() - start_time, 3)
        reply_str = str(reply)

        # Build the trace from what ACTUALLY happened this turn instead
        # of a static string that printed the same fake "0.001s FAISS
        # hit" and "Episode logged & validated" every single time no
        # matter what the pipeline really did. cli.py's
        # execute_cognitive_query() stashes the real numbers on
        # brain.last_turn_trace right after each turn — pull that.
        trace = getattr(integration.brain, "last_turn_trace", None) if integration.brain else None

        if trace:
            mem = trace.get("memory", {})
            timings = trace.get("timings", {})
            queue = trace.get("learning_queue", {})
            trace_log_str = (
                f"COGNITIVE EXECUTION TRACE (Source: WEB | Latency: {timings.get('total', latency):.3f}s)\n"
                f"Event Ingestion: USER_INPUT via 'web' interface\n"
                f"Memory Subsystem Search ({timings.get('memory', 0.0):.3f}s):\n"
                f"  FAISS Vector Index: {mem.get('recent_experiences', 0)} matching frames retrieved\n"
                f"  Knowledge Graph: {mem.get('relevant_knowledge', 0)} facts, {mem.get('graph_relations', 0)} relations\n"
                f"Learning Pipeline (async):\n"
                f"  Queued for background learning -- queue pending={queue.get('pending', '?')}, "
                f"processed so far={queue.get('processed', '?')}, failed={queue.get('failed', '?')}\n"
                f"Neural Inference (Qwen, single combined call): response + memory_signal in one call"
                f" ({timings.get('llm', latency):.3f}s)\n"
                f"Trace ID: TRC-LIVE"
            )
        else:
            # Fallback for when brain isn't wired yet / trace missing --
            # still real (latency, actual reply length), just less detailed.
            trace_log_str = (
                f"COGNITIVE EXECUTION TRACE (Source: WEB | Latency: {latency}s)\n"
                f"Event Ingestion: USER_INPUT via 'web' interface\n"
                f"Detailed pipeline trace unavailable (brain.last_turn_trace not set yet).\n"
                f"Reply length: {len(reply_str)} chars\n"
                f"Trace ID: TRC-LIVE"
            )

        database.save_message_to_db(
            session_id=session_id,
            sender="jarvis",
            text=reply_str,
            source="web",
            trace_log=trace_log_str,
        )

        broadcast_to_clients({
            "type": "chat_response",
            "sender": "jarvis",
            "text": reply_str,
            "session_id": session_id,
            "timestamp": get_local_ist_timestamp(),
            "trace_log": trace_log_str,
        })
    except Exception as exec_err:
        err_trace = traceback.format_exc()
        debug_log(f"Query Execution Error:\n{err_trace}", "bold red")
        broadcast_to_clients({
            "type": "system_error",
            "source": "Query Executor Engine",
            "error": str(exec_err),
            "traceback": err_trace,
        })
        try:
            await websocket.send_json({
                "type": "chat_error",
                "text": f"Query failed: {exec_err}",
            })
        except Exception:
            pass
    finally:
        # Always clear the thinking flag, success or failure, so a crashed
        # query can never leave the UI stuck on "Thinking...".
        set_thinking(session_id, False)
