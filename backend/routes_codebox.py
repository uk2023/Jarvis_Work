from __future__ import annotations

"""HTTP surface for the codebox, uploads and extended thinking.

Every route here takes the speaker from the auth dependency rather than
from the request body. A body-supplied username would let any caller
claim to be UK and land in his sandbox, which is the whole point of
having per-role sandboxes in the first place.
"""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .routes_auth import get_speaker


def _live_brain():
    """The running organism's brain. integration.py holds it as a
    module-level global that is set at startup, so it must be read
    through the module rather than imported by value -- importing the
    name once would capture None from before startup."""
    from . import integration
    return getattr(integration, "brain", None)

router = APIRouter(prefix="/api", tags=["codebox"])


def _principal(speaker: Any) -> Dict[str, Any]:
    """Normalise whatever get_speaker() returned into a plain dict.

    THE CRASH (fixed 2026-09-14). get_speaker() returns a Speaker
    DATACLASS, not a dict. This called .get() on it, so every request to
    /api/think/stream, /api/codebox/* and /api/upload raised
    `AttributeError: 'Speaker' object has no attribute 'get'` --
    a 500 and a full traceback in the CLI on EVERY turn.

    routes_frontend_v6.py had it right (speaker.as_dict()); this file
    did not, and the two were written a round apart. Accepting both
    shapes here means a future change to either side cannot re-break it
    the same way.
    """
    if speaker is None:
        data: Dict[str, Any] = {}
    elif isinstance(speaker, dict):
        data = speaker
    elif hasattr(speaker, "as_dict"):
        try:
            data = speaker.as_dict() or {}
        except Exception:
            data = {}
    else:
        data = {
            "role": getattr(speaker, "role", None),
            "username": getattr(speaker, "username", None),
            "is_verified": getattr(speaker, "is_verified", None),
        }

    # Speaker has NO 'username' field -- it carries display_name. Reading
    # "username" off it returned None for everybody, which silently sent
    # every authenticated user into the shared guest sandbox.
    username = data.get("username") or data.get("display_name")

    role = data.get("role") or "guest"
    role = role.value if hasattr(role, "value") else str(role)
    return {
        "role": role.lower(),
        "username": username,
        "is_verified": bool(data.get("is_verified")),
    }


def _sandbox_identity(p: Dict[str, Any], request: Any = None) -> Dict[str, Any]:
    """Who owns the sandbox for this call.

    WHY GUESTS ARE ALLOWED HERE (fixed 2026-09-14). Every codebox route
    used to require is_verified, so an unauthenticated caller got 401 on
    run, task, files AND upload -- which is why the CodeBox page showed
    "error fetching" for everything and the build button appeared dead.
    UK had no account at the time and no way to make one from the web.

    Running code in your OWN isolated sandbox is not a privileged
    operation -- it touches nothing outside that directory (see
    sandbox_policy.py). What IS privileged is system-level work, and
    that check lives separately and still requires owner/co-owner.

    A guest gets a sandbox keyed to their connection, so two guests do
    not share a directory.
    """
    if p["is_verified"] and p["username"]:
        return {"role": p["role"], "username": p["username"]}
    ip = "anon"
    try:
        if request is not None and request.client:
            ip = (request.client.host or "anon").replace(":", "_").replace(".", "_")
    except Exception:
        pass
    return {"role": "user", "username": f"guest_{ip}"}


# ------------------------------------------------------------------ uploads
@router.post("/upload")
async def upload_file(file: UploadFile = File(...), request: Request = None, speaker: Dict = Depends(get_speaker)):
    """Accept a file or archive into the CALLER'S OWN sandbox.

    Nothing is executed here. Archives are extracted with path-escape
    and symlink protection, then scanned; the response tells the user
    what was found so they can decide before running anything.
    """
    from core.skills.upload_guard import accept_upload

    p = _principal(speaker)
    who = _sandbox_identity(p, request)

    try:
        data = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File padhi nahi gayi: {exc}")

    result = accept_upload(data, file.filename or "upload",
                           role=who["role"], username=who["username"])
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error"), "note": result.get("note")}
    return result


@router.get("/uploads")
async def list_my_uploads(request: Request = None, speaker: Dict = Depends(get_speaker)):
    from core.skills.upload_guard import list_uploads
    p = _principal(speaker)
    who = _sandbox_identity(p, request)
    return {"uploads": list_uploads(role=who["role"], username=who["username"])}


# ------------------------------------------------------------------ codebox
class CodeRunRequest(BaseModel):
    code: str
    filename: Optional[str] = "main.py"


class CodeTaskRequest(BaseModel):
    task: str
    max_steps: int = 4


@router.post("/codebox/run")
async def codebox_run(req: CodeRunRequest, request: Request = None, speaker: Dict = Depends(get_speaker)):
    """Run code the user wrote, in their own sandbox. No LLM involved."""
    from core.skills.codebox import CodeBox

    p = _principal(speaker)
    who = _sandbox_identity(p, request)
    if not (req.code or "").strip():
        raise HTTPException(status_code=400, detail="Code khali hai.")

    box = CodeBox(role=who["role"], username=who["username"])
    step = box.run_python(req.code, filename=req.filename or "main.py")
    payload = step.as_dict() if hasattr(step, "as_dict") else dict(step)
    payload["workdir"] = str(box.session.workdir)
    payload["files"] = box.list_files()
    return payload


@router.post("/codebox/task")
async def codebox_task(req: CodeTaskRequest, request: Request = None, speaker: Dict = Depends(get_speaker)):
    """Ask JARVIS to write and iterate on code -- the multi-step path."""
    p = _principal(speaker)
    who = _sandbox_identity(p, request)

    brain = _live_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="Organism abhi ready nahi hai.")

    from core.skills.codebox import run_coding_session
    result = run_coding_session(
        brain.llm.generate_response,
        task=req.task,
        system_prompt="You are JARVIS, writing code for the user.",
        max_steps=max(1, min(int(req.max_steps), 12)),
        role=who["role"], username=who["username"],
    )
    return result


@router.get("/codebox/files")
async def codebox_files(request: Request = None, speaker: Dict = Depends(get_speaker)):
    from core.skills.codebox import CodeBox
    p = _principal(speaker)
    who = _sandbox_identity(p, request)
    box = CodeBox(role=who["role"], username=who["username"])
    return {"workdir": str(box.session.workdir), "files": box.list_files()}


# --------------------------------------------------------- extended thinking
class ThinkRequest(BaseModel):
    message: str
    mode: str = "auto"          # off | on | auto
    context: str = ""
    effort: str = "medium"      # low | medium | high | aggressive | deep


@router.post("/think/stream")
async def think_stream_route(req: ThinkRequest, speaker: Dict = Depends(get_speaker)):
    """Server-sent events so the UI renders each reasoning stage as it
    arrives, rather than waiting for the whole run."""
    from core.cognition.thinking import think_stream
    from core.identity.persona import persona_prompt
    from core.identity.user_memory import context_block

    p = _principal(speaker)
    brain = _live_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="Organism abhi ready nahi hai.")

    persona = persona_prompt(role=p["role"], speaker_name=p["username"],
                             is_verified=p["is_verified"])
    user_ctx = context_block(p["username"], role=p["role"])
    combined_ctx = "\n\n".join(x for x in (req.context, user_ctx) if x)

    def event_source():
        try:
            # MULTI-TURN STEP COMPLETION, UNIFIED WITH THINKING
            # (2026-09-14, UK: "multi-turn/step-turn sab extended
            # thinking se hi hoga on karne pe"). If the mode is not
            # 'off' AND the message reads as a task ("X bana do", "fix
            # karo", etc. -- see task_loop.wants_task_loop), this runs
            # the full plan/act/verify loop instead of the staged
            # reasoner. thinking.py's understand/explore/critique stages
            # answer a QUESTION; task_loop actually CARRIES OUT a task
            # to a verified conclusion. Turning extended thinking on is
            # now the single switch that engages whichever of the two
            # the turn actually needs, rather than a person having to
            # separately remember "and also use the task feature".
            from core.orchestration.task_loop import wants_task_loop, TaskLoop

            if req.mode != "off" and wants_task_loop(req.message):
                loop = TaskLoop(
                    brain.llm.generate_response, brain=brain,
                    role=p["role"], is_verified=p["is_verified"],
                    effort=req.effort,
                )
                for event in loop.stream(req.message):
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                return

            for event in think_stream(
                brain.llm.generate_response,
                user_input=req.message, mode=req.mode,
                context=combined_ctx, persona_prompt=persona,
                effort=req.effort,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/think/decide")
async def think_decide(req: ThinkRequest, speaker: Dict = Depends(get_speaker)):
    """What JARVIS would choose in AUTO mode for this message -- lets the
    UI show the toggle lighting up on its own, honestly."""
    from core.cognition.thinking import resolve_mode
    return resolve_mode(req.mode, req.message)


# ------------------------------------------------------------- step goals
class GoalRequest(BaseModel):
    goal: str
    max_steps: int = 6


@router.post("/goal/stepwise")
async def goal_stepwise(req: GoalRequest, speaker: Dict = Depends(get_speaker)):
    """Owner/co-owner only -- enforced inside run_goal_stepwise too."""
    p = _principal(speaker)
    brain = _live_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="Organism abhi ready nahi hai.")
    result = brain.run_goal_stepwise(
        goal=req.goal, role=p["role"], is_verified=p["is_verified"],
        max_steps=req.max_steps,
    )
    if not result.get("allowed", True):
        raise HTTPException(status_code=403, detail=result.get("reason"))
    return result


@router.get("/sandbox/overview")
async def sandbox_overview_route(speaker: Dict = Depends(get_speaker)):
    from core.skills.sandbox_policy import sandbox_overview
    p = _principal(speaker)
    if p["role"] not in {"owner", "co_owner"} or not p["is_verified"]:
        raise HTTPException(status_code=403, detail="Sandbox overview sirf owner/co-owner ke liye.")
    return sandbox_overview()


@router.get("/diagnose")
async def diagnose_route(speaker: Dict = Depends(get_speaker)):
    """Read-only diagnostic report -- anyone signed in can see what
    JARVIS thinks is wrong with itself; applying a fix is restricted
    below."""
    from core.runtime.diagnostics import run_diagnostics
    return run_diagnostics(auto_fix=False)


class DiagnoseFixRequest(BaseModel):
    name: str = ""   # empty = apply every safe AUTO remedy


@router.post("/diagnose/fix")
async def diagnose_fix_route(req: DiagnoseFixRequest, speaker: Dict = Depends(get_speaker)):
    """Applying a remedy -- even an AUTO one -- is owner/co-owner only.
    A read-only report is fine for anyone; actually changing runtime
    state is not."""
    from core.runtime.diagnostics import run_diagnostics, apply_remedy
    p = _principal(speaker)
    if p["role"] not in {"owner", "co_owner"} or not p["is_verified"]:
        raise HTTPException(status_code=403, detail="Fix apply karna sirf owner/co-owner ke liye.")
    if req.name:
        return apply_remedy(req.name)
    return run_diagnostics(auto_fix=True)
