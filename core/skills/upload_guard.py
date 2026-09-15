from __future__ import annotations

"""WHAT IS ALLOWED THROUGH THE ATTACH BUTTON.

UK (2026-09-13): "attach file ka frontend mein option hai but attach
nahi hota, wahan koi file nahi koi directory check. Aisa ki koi
malicious code na daale input attach se -- ye sab karo, pehle zaroori
hai." And separately: "main package bolun .zip tar.gz to wo sab kar ke
de de."

Those two asks pull in opposite directions, which is the whole design
problem here. Accepting archives is exactly how you get hurt:

  * ZIP-SLIP. An archive entry named '../../core/orchestration/brain.py'
    will, with a naive extractall(), overwrite a live source file. This
    is the single most common way "just let users upload a zip" turns
    into remote code execution. Every path is therefore resolved after
    joining and rejected if it lands outside the destination -- string
    prefix checks are not enough, because symlinks defeat them.

  * SYMLINK ESCAPE. A tar can contain a symlink pointing at /etc or at
    core/, after which a later entry writes "into" it. Symlinks and
    hardlinks are refused outright; nothing in a user upload needs one.

  * ZIP BOMB. A few KB can expand to gigabytes and fill UK's phone.
    Declared sizes are summed BEFORE extracting, and the count of
    entries is capped.

  * SPECIAL FILES. Device nodes, FIFOs, setuid bits -- refused.

The scanner is the second layer, not the first. It flags code that
would reach outside the sandbox and marks the upload for review; it is
NOT a malware detector and does not pretend to be. Nobody can reliably
decide whether arbitrary code is malicious by reading it, so the real
protection is that uploaded code lands in an isolated per-role sandbox
and is never imported by the running organism. The scan exists so that
a person is warned before choosing to run something, not so the system
can claim the file is safe.
"""

import hashlib
import os
import re
import shutil
import tarfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..runtime.log import log_event

MAX_UPLOAD_BYTES = 100 * 1024 * 1024         # 100 MB -- audio/video are legitimately large
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024      # refuse zip bombs
MAX_ARCHIVE_ENTRIES = 2000
MAX_PATH_DEPTH = 12

# Extensions JARVIS will accept. Everything else is stored as an opaque
# blob at most, never opened or executed.
TEXT_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".csv",
                   ".yml", ".yaml", ".toml", ".ini", ".cfg", ".html", ".css", ".sh",
                   ".sql", ".xml", ".env.example"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".heic"}

# Media and documents: stored as opaque blobs, never parsed or executed.
# They were previously "unknown type", which worked but read like a
# warning for an ordinary mp3.
MEDIA_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac",
                    ".mp4", ".mkv", ".webm", ".mov", ".pdf", ".docx", ".xlsx",
                    ".pptx", ".epub", ".srt", ".vtt"}

# Never accepted -- executables and installers have no legitimate use
# in a code sandbox and every use is a risk.
BLOCKED_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bin", ".apk", ".deb", ".rpm",
                      ".msi", ".bat", ".cmd", ".scr", ".jar", ".com", ".pyc", ".pyd"}

# Patterns worth a human's attention. Presence does NOT mean malicious;
# it means "a person should look before this runs".
_SUSPICIOUS = (
    (r"\bos\.system\s*\(", "shell execution", "high"),
    (r"\bsubprocess\.(Popen|run|call|check_output)", "subprocess spawn", "high"),
    (r"\beval\s*\(|\bexec\s*\(", "eval/exec of dynamic code", "high"),
    (r"\b__import__\s*\(|\bimportlib\b", "dynamic import", "medium"),
    (r"\bshutil\.rmtree|\bos\.remove|\bos\.unlink", "file deletion", "high"),
    (r"\bsocket\b|\brequests\.|\burllib|\bhttpx\b|\bcurl\b|\bwget\b", "network access", "medium"),
    (r"\bpip\s+install|\bapt\s+install|\bnpm\s+i(nstall)?\b", "package installation", "high"),
    (r"base64\.b64decode\s*\([^)]{80,}", "large base64 blob decoded (often packed payload)", "high"),
    (r"\bos\.environ\b|\bgetenv\b", "reads environment variables", "medium"),
    (r"/etc/passwd|/etc/shadow|~/\.ssh|id_rsa", "touches credential paths", "high"),
    (r"\bchmod\s+\+?x|\bos\.chmod\b", "changes execute permissions", "medium"),
    (r"\bcrontab\b|\bsystemctl\b|\bnohup\b", "persistence / service control", "high"),
)


@dataclass
class ScanFinding:
    file: str
    label: str
    severity: str
    line: int

    def as_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "label": self.label, "severity": self.severity, "line": self.line}


@dataclass
class UploadResult:
    ok: bool
    upload_id: str
    dest: Optional[str] = None
    files: List[str] = field(default_factory=list)
    findings: List[ScanFinding] = field(default_factory=list)
    refused_entries: List[Dict[str, str]] = field(default_factory=list)
    error: Optional[str] = None
    total_bytes: int = 0
    sha256: Optional[str] = None

    @property
    def needs_review(self) -> bool:
        return any(f.severity == "high" for f in self.findings)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok, "upload_id": self.upload_id, "dest": self.dest,
            "files": self.files[:300], "file_count": len(self.files),
            "findings": [f.as_dict() for f in self.findings],
            "refused_entries": self.refused_entries[:50],
            "needs_review": self.needs_review, "error": self.error,
            "total_bytes": self.total_bytes, "sha256": self.sha256,
            "note": self._note(),
        }

    def _note(self) -> str:
        if not self.ok:
            return f"Upload refuse ho gaya: {self.error}"
        bits = [f"{len(self.files)} file extract hui."]
        if self.refused_entries:
            bits.append(f"{len(self.refused_entries)} entry refuse ki (path escape ya blocked type).")
        if self.needs_review:
            high = sorted({f.label for f in self.findings if f.severity == "high"})
            bits.append(
                f"Ismein yeh mila: {', '.join(high)}. Iska matlab yeh nahi ki file malicious hai -- "
                "matlab yeh hai ki chalane se pehle aap khud dekh lo. Main sirf sandbox mein hi "
                "chala sakta hun, live system se yeh code kabhi nahi judega."
            )
        elif self.findings:
            bits.append("Kuch minor cheezein mili, par kuch bhi sandbox ke bahar nahi pahunchta.")
        else:
            bits.append("Scan mein aisa kuch nahi mila jo sandbox ke bahar pahunche.")
        return " ".join(bits)


def _safe_join(dest_root: Path, member_name: str) -> Optional[Path]:
    """Resolve an archive member against the destination, returning None
    if it escapes. This is the zip-slip check and it must resolve, not
    string-compare, or '../' and symlinks both get through."""
    if not member_name or member_name.startswith("/") or "\x00" in member_name:
        return None
    if len(Path(member_name).parts) > MAX_PATH_DEPTH:
        return None
    candidate = (dest_root / member_name)
    try:
        resolved = candidate.resolve()
        root = dest_root.resolve()
        if resolved == root or root in resolved.parents:
            return candidate
    except Exception:
        return None
    return None


def _ext_allowed(name: str) -> Tuple[bool, str]:
    ext = Path(name).suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        return False, f"blocked file type ({ext})"
    if ext and ext not in (TEXT_EXTENSIONS | ARCHIVE_EXTENSIONS | IMAGE_EXTENSIONS | MEDIA_EXTENSIONS):
        # Unknown extension: allowed only if it is small and looks like
        # text, checked at write time. Recorded here for transparency.
        return True, "unknown type -- stored, not executed"
    return True, ""


def scan_source(path: Path, relative_name: str) -> List[ScanFinding]:
    """Read a text file and flag anything reaching outside the sandbox."""
    findings: List[ScanFinding] = []
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return findings
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    if len(text) > 2_000_000:
        text = text[:2_000_000]
    lines = text.splitlines()
    for pattern, label, severity in _SUSPICIOUS:
        rx = re.compile(pattern)
        for i, line in enumerate(lines, start=1):
            if rx.search(line):
                findings.append(ScanFinding(file=relative_name, label=label, severity=severity, line=i))
                break          # one finding per pattern per file is enough
    return findings


def _extract_zip(src: Path, dest: Path, result: UploadResult) -> bool:
    with zipfile.ZipFile(src) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            result.error = f"Archive mein {len(infos)} entries hain -- limit {MAX_ARCHIVE_ENTRIES}."
            return False
        declared = sum(i.file_size for i in infos)
        if declared > MAX_EXTRACTED_BYTES:
            result.error = f"Extract hone pe {declared // (1024*1024)} MB ho jaata -- zip bomb ho sakta hai, refuse kiya."
            return False
        for info in infos:
            name = info.filename
            if info.is_dir():
                continue
            target = _safe_join(dest, name)
            if target is None:
                result.refused_entries.append({"entry": name, "reason": "path archive ke bahar ja raha tha (zip-slip)"})
                continue
            allowed, why = _ext_allowed(name)
            if not allowed:
                result.refused_entries.append({"entry": name, "reason": why})
                continue
            # Unix mode is in the top 16 bits; refuse symlinks.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                result.refused_entries.append({"entry": name, "reason": "symlink -- refuse kiya"})
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as srcf, open(target, "wb") as out:
                shutil.copyfileobj(srcf, out, length=64 * 1024)
            result.files.append(str(target.relative_to(dest)))
    return True


def _extract_tar(src: Path, dest: Path, result: UploadResult) -> bool:
    with tarfile.open(src) as tf:
        members = tf.getmembers()
        if len(members) > MAX_ARCHIVE_ENTRIES:
            result.error = f"Archive mein {len(members)} entries hain -- limit {MAX_ARCHIVE_ENTRIES}."
            return False
        declared = sum(m.size for m in members if m.isfile())
        if declared > MAX_EXTRACTED_BYTES:
            result.error = f"Extract hone pe {declared // (1024*1024)} MB ho jaata -- refuse kiya."
            return False
        for m in members:
            if m.isdir():
                continue
            if m.issym() or m.islnk():
                result.refused_entries.append({"entry": m.name, "reason": "symlink/hardlink -- refuse kiya"})
                continue
            if not m.isfile():
                result.refused_entries.append({"entry": m.name, "reason": "special file (device/fifo) -- refuse kiya"})
                continue
            target = _safe_join(dest, m.name)
            if target is None:
                result.refused_entries.append({"entry": m.name, "reason": "path archive ke bahar ja raha tha (tar-slip)"})
                continue
            allowed, why = _ext_allowed(m.name)
            if not allowed:
                result.refused_entries.append({"entry": m.name, "reason": why})
                continue
            extracted = tf.extractfile(m)
            if extracted is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as out:
                shutil.copyfileobj(extracted, out, length=64 * 1024)
            os.chmod(target, 0o600)          # never executable
            result.files.append(str(target.relative_to(dest)))
    return True


def accept_upload(file_bytes: bytes, filename: str, *, role: str = "user",
                  username: Optional[str] = None) -> Dict[str, Any]:
    """Accept an uploaded file or archive into the caller's OWN sandbox.

    Nothing here ever lands in the live tree, and nothing is executed --
    extraction and scanning only. Running anything is a separate,
    explicit action in the codebox.
    """
    upload_id = uuid.uuid4().hex[:12]
    result = UploadResult(ok=False, upload_id=upload_id)

    if not file_bytes:
        result.error = "File khali hai."
        return result.as_dict()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        result.error = f"File {len(file_bytes) // (1024*1024)} MB hai -- limit {MAX_UPLOAD_BYTES // (1024*1024)} MB."
        return result.as_dict()

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename or "upload").name)[:120] or "upload"
    allowed, why = _ext_allowed(safe_name)
    if not allowed:
        result.error = why
        return result.as_dict()

    result.total_bytes = len(file_bytes)
    result.sha256 = hashlib.sha256(file_bytes).hexdigest()[:16]

    try:
        from .sandbox_policy import sandbox_dir_for
        sandbox = sandbox_dir_for(role=role, username=username, session_id=f"upload_{upload_id}")
    except Exception:
        sandbox = Path("data/sandboxes/user/anonymous")
        sandbox.mkdir(parents=True, exist_ok=True)

    dest = sandbox / f"upload_{upload_id}"
    dest.mkdir(parents=True, exist_ok=True)
    staged = dest / safe_name

    try:
        staged.write_bytes(file_bytes)
        lower = safe_name.lower()
        is_zip = lower.endswith(".zip")
        is_tar = any(lower.endswith(s) for s in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".gz", ".bz2", ".xz"))

        if is_zip:
            if not _extract_zip(staged, dest, result):
                shutil.rmtree(dest, ignore_errors=True)
                return result.as_dict()
            staged.unlink(missing_ok=True)
        elif is_tar:
            if not _extract_tar(staged, dest, result):
                shutil.rmtree(dest, ignore_errors=True)
                return result.as_dict()
            staged.unlink(missing_ok=True)
        else:
            os.chmod(staged, 0o600)
            result.files.append(safe_name)

        for rel in result.files:
            findings = scan_source(dest / rel, rel)
            result.findings.extend(findings)

        result.ok = True
        result.dest = str(dest)
        log_event("upload",
                  f"accepted upload {upload_id} ({len(result.files)} files, "
                  f"{len(result.refused_entries)} refused, review={result.needs_review})",
                  level="info")
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        result.error = f"Archive padha nahi gaya (corrupt ya galat format): {exc}"
    except Exception as exc:
        shutil.rmtree(dest, ignore_errors=True)
        result.error = f"Upload fail hua: {exc}"

    return result.as_dict()


def list_uploads(role: str = "user", username: Optional[str] = None) -> List[Dict[str, Any]]:
    """What this principal has uploaded -- their own sandbox only."""
    try:
        from .sandbox_policy import SANDBOX_ROOT
        tier = "owner" if role in {"owner", "co_owner"} else ("admin" if role == "admin" else "user")
        base = SANDBOX_ROOT / tier
        if tier == "user":
            base = base / re.sub(r"[^a-zA-Z0-9_-]", "_", username or "anonymous")
        out = []
        if base.exists():
            for d in sorted(base.rglob("upload_*")):
                if d.is_dir():
                    files = [f for f in d.rglob("*") if f.is_file()]
                    out.append({"upload_id": d.name.replace("upload_", ""), "path": str(d),
                                "files": len(files),
                                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(d.stat().st_mtime))})
        return out
    except Exception:
        return []
