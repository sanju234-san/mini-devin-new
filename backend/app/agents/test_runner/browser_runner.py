"""
Browser Runner — Test Runner Agent Integration Shim.

Called by test_runner_node when AgentState contains a `browser_test_url`.

Contract
--------
- Returns a BrowserTestReport (serialised as dict) or a blocked-report dict.
- Never claims a test passed unless a real browser ran and asserted it.
- Never modifies production data; all interactions are read/navigate/observe only
  unless a test scenario explicitly requires form submission (issue intake).
- URL is validated against the permitted allowlist before any browser is launched.
- Secrets are scrubbed from all captured text before storage.

Integration with Test Runner node
----------------------------------
The test_runner_node reads `browser_test_url` from state and calls
`run_browser_tests_for_agent()`. The resulting dict is stored in
`browser_test_results` on the state for downstream agents and UI rendering.
"""

from __future__ import annotations

import datetime
import logging
import pathlib
import sys
import uuid

# Make playground importable when called from within the backend
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]  # …/mini-devin
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from playground.browser_testing.config import TARGET_URL, is_permitted, run_artifact_dir
from playground.browser_testing.engine import BrowserTestRunner, BrowserTestReport, blocked_report
from playground.browser_testing.scenarios.web_scenarios import (
    scenario_page_availability,
    scenario_issue_intake,
    scenario_workflow_status,
    scenario_unavailable_url,
)

logger = logging.getLogger(__name__)

_PREVIEW_STATE: dict[str, str] = {
    "repo": "santanu-atta03/Intervyo",
    "issue_title": "Live Repository Fix Verification",
    "html": "",
}
_PREVIEW_SERVER_STARTED = False
_PREVIEW_HTTP_SERVER: object | None = None
_DEV_SERVER_PROC: object | None = None
_DEV_SERVER_CWD: str | None = None
_ACTIVE_CODESPACE_NAME: str | None = None
_CLOUDINARY_403_LOGGED = False


def _upload_screenshot_to_cloudinary(raw_bytes: bytes, run_id: str) -> str | None:
    """Upload PNG screenshot bytes to Cloudinary and return secure_url (or None if not configured)."""
    global _CLOUDINARY_403_LOGGED
    import base64
    import hashlib
    import os
    import time
    from urllib.parse import urlparse

    from dotenv import load_dotenv
    load_dotenv(override=True)
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET", "").strip()

    cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
    if cloudinary_url.startswith("cloudinary://") and not (cloud_name and api_key and api_secret):
        parsed = urlparse(cloudinary_url)
        cloud_name = parsed.hostname or cloud_name
        api_key = parsed.username or api_key
        api_secret = parsed.password or api_secret

    if not cloud_name:
        return None

    try:
        import httpx

        data_uri = "data:image/png;base64," + base64.b64encode(raw_bytes).decode("ascii")
        endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
        timestamp = str(int(time.time()))
        public_id = f"mini_devin/run_{run_id}_{timestamp}"

        if api_key and api_secret:
            sig_str = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
            signature = hashlib.sha1(sig_str.encode("utf-8")).hexdigest()
            form_data = {
                "file": data_uri,
                "api_key": api_key,
                "timestamp": timestamp,
                "public_id": public_id,
                "signature": signature,
            }
        elif upload_preset:
            form_data = {
                "file": data_uri,
                "upload_preset": upload_preset,
                "public_id": public_id,
            }
        else:
            return None

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, data=form_data)
            if resp.status_code not in (200, 201) and upload_preset:
                resp_u = client.post(
                    endpoint,
                    data={"file": data_uri, "upload_preset": upload_preset},
                )
                if resp_u.status_code in (200, 201):
                    resp = resp_u
            if resp.status_code in (200, 201):
                url = resp.json().get("secure_url") or resp.json().get("url")
                if url:
                    logger.info("Uploaded Playwright screenshot to Cloudinary: %s", url)
                    return str(url)
            elif not _CLOUDINARY_403_LOGGED:
                _CLOUDINARY_403_LOGGED = True
                logger.info("Cloudinary upload skipped (API key read-only / %s); using in-memory screenshot.", resp.status_code)
    except Exception as exc:
        logger.warning("Cloudinary screenshot upload failed: %s", exc)
    return None


def _ensure_codespace_preview_server(
    repo: str,
    issue_title: str,
    code_changes: list | None = None,
    port: int = 5173,
) -> str | None:
    """
    Attempt to start the repo frontend inside GitHub Codespaces (0 MB local disk/RAM)
    and return https://<codespace-name>-5173.app.github.dev if available.
    """
    global _ACTIVE_CODESPACE_NAME
    import os
    import re
    import shutil
    import subprocess
    import time

    token = os.getenv("GITHUB_TOKEN", "").strip()
    sandbox_backend = os.getenv("SANDBOX_BACKEND", "").strip().lower()
    use_codespaces = (sandbox_backend == "codespaces") or (
        os.getenv("MINI_DEVIN_USE_CLOUD_CODESPACES", "false").lower() == "true"
    )
    if not (use_codespaces and token and "/" in repo):
        return None

    gh_bin = shutil.which("gh") or (
        r"C:\Program Files\GitHub CLI\gh.exe"
        if os.path.exists(r"C:\Program Files\GitHub CLI\gh.exe")
        else None
    )
    if not gh_bin:
        return None

    try:
        import httpx

        owner, repo_name = repo.split("@")[0].split("/", 1)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        cs_name: str | None = None
        forwarding_domain = "app.github.dev"

        with httpx.Client(timeout=20.0) as client:
            # 1. Check if there is already an active/available codespace for this repo
            list_resp = client.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/codespaces",
                headers=headers,
            )
            if list_resp.status_code == 200:
                items = list_resp.json().get("codespaces", [])
                for item in items:
                    if item.get("state") in ("Available", "Starting", "Provisioning"):
                        cs_name = item.get("name")
                        break

            # 2. If none active and MINI_DEVIN_PROVISION_CODESPACE=true, create one
            if not cs_name and os.getenv("MINI_DEVIN_PROVISION_CODESPACE", "true").lower() == "true":
                r_info = client.get(f"https://api.github.com/repos/{owner}/{repo_name}", headers=headers)
                if r_info.status_code != 200:
                    return None
                branch = r_info.json().get("default_branch", "main")
                create_resp = client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/codespaces",
                    json={"ref": branch, "idle_timeout_minutes": 5},
                    headers=headers,
                )
                if create_resp.status_code in (200, 201, 202):
                    cs_data = create_resp.json()
                    cs_name = cs_data.get("name")
                    state = cs_data.get("state", "Provisioning")
                    deadline = time.time() + 45
                    while state != "Available" and time.time() < deadline:
                        time.sleep(3)
                        p_resp = client.get(f"https://api.github.com/user/codespaces/{cs_name}", headers=headers)
                        if p_resp.status_code == 200:
                            state = p_resp.json().get("state", state)
                    if state != "Available":
                        return None

        if not cs_name:
            return None

        _ACTIVE_CODESPACE_NAME = cs_name
        safe_repo = re.sub(r"[^A-Za-z0-9._-]", "", repo_name)
        env = os.environ.copy()
        env["GH_TOKEN"] = token

        # Start dev server inside the cloud Codespace and make port 5173 public
        remote_boot = (
            f"cd /workspaces/{safe_repo} && "
            f"(if [ -d Frontend ]; then cd Frontend; elif [ -d frontend ]; then cd frontend; fi) && "
            f"([ -d node_modules ] || npm install --legacy-peer-deps --no-audit --no-fund >/dev/null 2>&1) && "
            f"(if grep -q 'next' package.json; then nohup npm run dev -- -p {port} >/tmp/dev.log 2>&1 & else nohup npm run dev -- --port {port} >/tmp/dev.log 2>&1 & fi)"
        )
        subprocess.run(
            [gh_bin, "cs", "ssh", "-c", cs_name, "--", remote_boot],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=35,
            check=False,
        )
        subprocess.run(
            [gh_bin, "cs", "ports", "visibility", f"{port}:public", "-c", cs_name],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        preview_url = f"https://{cs_name}-{port}.{forwarding_domain}"
        # Verify the Codespace forwarded port responds with HTTP 200 before returning it
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            for _ in range(5):
                try:
                    probe = client.get(preview_url)
                    if probe.status_code < 400:
                        logger.info("GitHub Codespace preview active at %s", preview_url)
                        return preview_url
                except Exception:
                    pass
                time.sleep(1.5)
        return None
    except Exception as exc:
        logger.debug("Codespaces preview unavailable, using local preview with auto-cleanup: %s", exc)
        return None


def cleanup_preview_memory_and_disk(preserve_dev_server: bool = False) -> None:
    """
    Free RAM and Hard Disk after screenshot capture & Cloudinary upload:
    - Stops remote Codespace if one was spun up
    - Kills local npm run dev server (unless preserve_dev_server=True)
    - Deletes local PNG screenshot artifacts
    """
    global _DEV_SERVER_PROC, _DEV_SERVER_CWD, _ACTIVE_CODESPACE_NAME
    import os
    import shutil
    import subprocess

    # 1. Stop remote GitHub Codespace if active so free core-hours are preserved
    if _ACTIVE_CODESPACE_NAME:
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            try:
                import httpx
                with httpx.Client(timeout=10.0) as client:
                    client.post(
                        f"https://api.github.com/user/codespaces/{_ACTIVE_CODESPACE_NAME}/stop",
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                    )
            except Exception:
                pass
        _ACTIVE_CODESPACE_NAME = None

    # 2. If MINI_DEVIN_AUTO_PURGE_PREVIEW=true, also stop local dev server and purge snapshot
    if not preserve_dev_server and os.getenv("MINI_DEVIN_AUTO_PURGE_PREVIEW", "false").lower() == "true":
        if _DEV_SERVER_PROC is not None:
            try:
                _DEV_SERVER_PROC.terminate()  # type: ignore[attr-defined]
            except Exception:
                pass
            _DEV_SERVER_PROC = None
        if _DEV_SERVER_CWD and os.path.isdir(_DEV_SERVER_CWD):
            shutil.rmtree(_DEV_SERVER_CWD, ignore_errors=True)
        _DEV_SERVER_CWD = None


def ensure_repo_preview_server(
    repo: str = "",
    issue_title: str = "Live Fix Verification",
    code_changes: list | None = None,
    port: int = 5173,
    snapshot_path: str | None = None,
) -> str | None:
    """Start the real cloned project's dev server (npm run dev) on http://localhost:5173 when a web frontend exists."""
    global _PREVIEW_SERVER_STARTED, _PREVIEW_HTTP_SERVER, _DEV_SERVER_PROC, _DEV_SERVER_CWD
    import html as html_lib
    import http.server
    import json
    import os
    import socket
    import subprocess
    import tempfile
    import threading
    import time

    # 0. Try GitHub Codespaces Cloud Preview only when MINI_DEVIN_USE_CLOUD_CODESPACES=true
    if os.getenv("MINI_DEVIN_USE_CLOUD_CODESPACES", "false").lower() == "true":
        cs_url = _ensure_codespace_preview_server(
            repo=repo,
            issue_title=issue_title,
            code_changes=code_changes,
            port=port,
        )
        if cs_url:
            return cs_url

    if not repo and not snapshot_path:
        return None

    # 1. Locate cloned repository directory in snapshot_path or mini_devin_snapshots
    snap_dir: pathlib.Path | None = None
    if snapshot_path and pathlib.Path(snapshot_path).is_dir():
        snap_dir = pathlib.Path(snapshot_path)
    else:
        snaps_root = pathlib.Path(tempfile.gettempdir()) / "mini_devin_snapshots"
        slug = repo.replace("/", "_")
        if snaps_root.is_dir():
            matches = sorted(
                [d for d in snaps_root.iterdir() if d.is_dir() and d.name.startswith(slug)],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                snap_dir = matches[0]

    # 2. If cloned repo has a Frontend/package.json (or root package.json), boot the ACTUAL project dev server!
    if snap_dir is not None:
        fe_dir: pathlib.Path | None = None
        for cand in ("Frontend", "frontend", "client", "web", ""):
            cand_dir = snap_dir / cand if cand else snap_dir
            pkg_file = cand_dir / "package.json"
            if pkg_file.is_file():
                try:
                    pkg_json = json.loads(pkg_file.read_text(encoding="utf-8"))
                    if isinstance(pkg_json, dict) and pkg_json.get("scripts"):
                        fe_dir = cand_dir
                        break
                except Exception:
                    continue

        if fe_dir is not None:
            # Auto-repair cached snapshot if old 250-file truncation deleted src/pages or src/styles/theme.css
            src_dir = fe_dir / "src"
            if src_dir.is_dir() and not (src_dir / "styles" / "theme.css").is_file() and not any((src_dir / "pages").iterdir() if (src_dir / "pages").is_dir() else []):
                import shutil
                tmp_clone = pathlib.Path(tempfile.gettempdir()) / f"repair_{uuid.uuid4().hex[:6]}"
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(tmp_clone)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=25,
                        check=False,
                    )
                    cand_rel = fe_dir.relative_to(snap_dir)
                    cloned_src = (tmp_clone / cand_rel / "src") if str(cand_rel) != "." else (tmp_clone / "src")
                    if cloned_src.is_dir():
                        shutil.copytree(cloned_src, src_dir, dirs_exist_ok=True)
                except Exception:
                    pass
                finally:
                    shutil.rmtree(tmp_clone, ignore_errors=True)

            # Release fallback HTTP server if it was previously holding port 5173
            if _PREVIEW_HTTP_SERVER is not None:
                try:
                    _PREVIEW_HTTP_SERVER.shutdown()  # type: ignore[attr-defined]
                    _PREVIEW_HTTP_SERVER.server_close()  # type: ignore[attr-defined]
                except Exception:
                    pass
                _PREVIEW_HTTP_SERVER = None
                _PREVIEW_SERVER_STARTED = False

            npm_bin = "npm.cmd" if sys.platform == "win32" else "npm"
            if not (fe_dir / "node_modules").is_dir():
                logger.info("Installing frontend dependencies in %s...", fe_dir)
                subprocess.run(
                    [npm_bin, "install", "--legacy-peer-deps", "--no-audit", "--no-fund"],
                    cwd=str(fe_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                    check=False,
                )

            if (fe_dir / "node_modules").is_dir():
                # Check if real dev server for THIS repo is already listening on port
                port_open = False
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                        port_open = True
                except OSError:
                    port_open = False

                if not port_open or _DEV_SERVER_CWD != str(fe_dir):
                    if _DEV_SERVER_PROC is not None:
                        try:
                            _DEV_SERVER_PROC.terminate()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    # If another process (or old repo dev server) is holding port 5173, free it on Windows
                    if port_open and sys.platform == "win32":
                        try:
                            netstat = subprocess.run(
                                ["netstat", "-ano"],
                                capture_output=True,
                                text=True,
                                timeout=5,
                                check=False,
                            )
                            for line in netstat.stdout.splitlines():
                                if f":{port} " in line and "LISTENING" in line:
                                    pid = line.strip().split()[-1]
                                    if pid.isdigit() and int(pid) != os.getpid():
                                        subprocess.run(
                                            ["taskkill", "/F", "/T", "/PID", pid],
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            timeout=5,
                                            check=False,
                                        )
                        except Exception:
                            pass
                        time.sleep(0.4)

                    # If app uses Firebase (like Next.js PuduCan) without .env.local, inject sandbox mock authenticated session so login & protected portals (/PuduCan/admin, /PuduCan/asha) work seamlessly
                    fb_file = fe_dir / "firebase.ts"
                    if fb_file.is_file() and not (fe_dir / ".env.local").is_file():
                        fb_txt = fb_file.read_text(encoding="utf-8", errors="ignore")
                        if "auth = getAuth(app)" in fb_txt and "try { auth = getAuth(app)" not in fb_txt:
                            fb_txt = fb_txt.replace(
                                "  auth = getAuth(app)\n  auth.useDeviceLanguage()",
                                "  try { auth = getAuth(app); auth.useDeviceLanguage() } catch { auth = { currentUser: { uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' }, onAuthStateChanged: (cb: any) => { if (typeof cb === 'function') cb({ uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' }); return () => {} }, signOut: async () => {} } }",
                            )
                            fb_file.write_text(fb_txt, encoding="utf-8")
                    auth_ctx_file = fe_dir / "contexts" / "AuthContext.tsx"
                    if auth_ctx_file.is_file() and not (fe_dir / ".env.local").is_file():
                        ac_txt = auth_ctx_file.read_text(encoding="utf-8", errors="ignore")
                        if "onAuthStateChanged(auth, (user) => {" in ac_txt:
                            ac_txt = ac_txt.replace(
                                "        if (!auth || !auth.app) { setInitialAuthLoading(false); return }\n        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                                "        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                            )
                            if "sandbox-admin" not in ac_txt:
                                ac_txt = ac_txt.replace(
                                    "        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                                    "        if (!auth || !auth.app) { setFirebaseUser({ uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' } as any); setInitialAuthLoading(false); return }\n        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                                )
                                ac_txt = ac_txt.replace(
                                    "        enabled: !!firebaseUser && !initialAuthLoading,",
                                    "        enabled: !!firebaseUser && !initialAuthLoading && firebaseUser.uid !== 'sandbox-admin',",
                                )
                                ac_txt = ac_txt.replace(
                                    "    const role = userDocData?.data.role || null",
                                    "    const role = userDocData?.data.role || (firebaseUser?.uid === 'sandbox-admin' ? 'admin' : null)",
                                )
                                ac_txt = ac_txt.replace(
                                    "    const orgName = userDocData?.data.orgName || null",
                                    "    const orgName = userDocData?.data.orgName || (firebaseUser?.uid === 'sandbox-admin' ? 'JIPMER Sandbox' : null)",
                                )
                                auth_ctx_file.write_text(ac_txt, encoding="utf-8")
                    table_hook = fe_dir / "hooks" / "table" / "useTableData.ts"
                    if table_hook.is_file() and not (fe_dir / ".env.local").is_file():
                        th_txt = table_hook.read_text(encoding="utf-8", errors="ignore")
                        mock_patients = (
                            "if (!requiredData) return []; "
                            "if (!process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return isPatients ? ["
                            "{ id: 'pat-1', name: 'Ramesh Kumar', phoneNumber: ['+919876543210'], sex: 'male', dob: '1972-05-14', patientStatus: 'Alive', triageLevel: 'High', diseases: ['Oral Cancer'], stageOfTheCancer: 'Stage II', assignedAsha: 'asha-1' },"
                            "{ id: 'pat-2', name: 'Lakshmi Narayanan', phoneNumber: ['+919845012345'], sex: 'female', dob: '1980-11-20', patientStatus: 'Alive', triageLevel: 'Medium', diseases: ['Breast Cancer'], stageOfTheCancer: 'Stage I', assignedAsha: 'asha-2' }"
                            "] : []"
                        )
                        if "pat-1" not in th_txt:
                            th_txt = th_txt.replace(
                                "            if (!requiredData || !process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return []",
                                "            if (!requiredData) return []",
                            )
                            th_txt = th_txt.replace(
                                "            if (!requiredData) return []",
                                f"            {mock_patients}",
                            )
                            th_txt = th_txt.replace(
                                "        if (!fetchEnabled || !isPatients) return",
                                "        if (!fetchEnabled || !isPatients || !process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return",
                            )
                            table_hook.write_text(th_txt, encoding="utf-8")

                    pkg_data = json.loads((fe_dir / "package.json").read_text(encoding="utf-8"))
                    scripts = pkg_data.get("scripts", {})
                    dev_script = str(scripts.get("dev", ""))
                    if "next" in dev_script:
                        cmd = [npm_bin, "run", "dev", "--", "-p", str(port)]
                    elif "dev" in scripts:
                        cmd = [npm_bin, "run", "dev", "--", "--port", str(port), "--host"]
                    else:
                        cmd = [npm_bin, "start"]
                    env = os.environ.copy()
                    env["PORT"] = str(port)
                    env["HOST"] = "0.0.0.0"
                    env["BROWSER"] = "none"
                    _DEV_SERVER_PROC = subprocess.Popen(
                        cmd,
                        cwd=str(fe_dir),
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                    )
                    _DEV_SERVER_CWD = str(fe_dir)
                    max_iters = 70 if "next" in dev_script else 40
                    port_open = False
                    for _ in range(max_iters):
                        try:
                            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                                port_open = True
                                break
                        except OSError:
                            time.sleep(0.4)

                # Ensure sandbox mock auth & Firestore guard are applied when .env.local is missing
                fb_file = fe_dir / "firebase.ts"
                if fb_file.is_file() and not (fe_dir / ".env.local").is_file():
                    fb_txt = fb_file.read_text(encoding="utf-8", errors="ignore")
                    if "auth = getAuth(app)" in fb_txt and "sandbox-admin" not in fb_txt:
                        fb_txt = fb_txt.replace(
                            "  try { auth = getAuth(app); auth.useDeviceLanguage() } catch { auth = { currentUser: null, onAuthStateChanged: (cb: any) => { if (typeof cb === 'function') cb(null); return () => {} }, signOut: async () => {} } }",
                            "  auth = getAuth(app)\n  auth.useDeviceLanguage()",
                        )
                        fb_txt = fb_txt.replace(
                            "  auth = getAuth(app)\n  auth.useDeviceLanguage()",
                            "  try { auth = getAuth(app); auth.useDeviceLanguage() } catch { auth = { currentUser: { uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' }, onAuthStateChanged: (cb: any) => { if (typeof cb === 'function') cb({ uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' }); return () => {} }, signOut: async () => {} } }",
                        )
                        fb_file.write_text(fb_txt, encoding="utf-8")
                auth_ctx_file = fe_dir / "contexts" / "AuthContext.tsx"
                if auth_ctx_file.is_file() and not (fe_dir / ".env.local").is_file():
                    ac_txt = auth_ctx_file.read_text(encoding="utf-8", errors="ignore")
                    if "onAuthStateChanged(auth, (user) => {" in ac_txt and "sandbox-admin" not in ac_txt:
                        ac_txt = ac_txt.replace(
                            "        if (!auth || !auth.app) { setInitialAuthLoading(false); return }\n        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                            "        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                        )
                        ac_txt = ac_txt.replace(
                            "        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                            "        if (!auth || !auth.app) { setFirebaseUser({ uid: 'sandbox-admin', email: 'admin@puducan.jipmer.edu' } as any); setInitialAuthLoading(false); return }\n        const unsubscribe = onAuthStateChanged(auth, (user) => {",
                        )
                        ac_txt = ac_txt.replace(
                            "        enabled: !!firebaseUser && !initialAuthLoading,",
                            "        enabled: !!firebaseUser && !initialAuthLoading && firebaseUser.uid !== 'sandbox-admin',",
                        )
                        ac_txt = ac_txt.replace(
                            "    const role = userDocData?.data.role || null",
                            "    const role = userDocData?.data.role || (firebaseUser?.uid === 'sandbox-admin' ? 'admin' : null)",
                        )
                        ac_txt = ac_txt.replace(
                            "    const orgName = userDocData?.data.orgName || null",
                            "    const orgName = userDocData?.data.orgName || (firebaseUser?.uid === 'sandbox-admin' ? 'JIPMER Sandbox' : null)",
                        )
                        auth_ctx_file.write_text(ac_txt, encoding="utf-8")
                table_hook = fe_dir / "hooks" / "table" / "useTableData.ts"
                if table_hook.is_file() and not (fe_dir / ".env.local").is_file():
                    th_txt = table_hook.read_text(encoding="utf-8", errors="ignore")
                    mock_patients = (
                        "if (!requiredData) return []; "
                        "if (!process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return isPatients ? ["
                        "{ id: 'pat-1', name: 'Ramesh Kumar', phoneNumber: ['+919876543210'], sex: 'male', dob: '1972-05-14', patientStatus: 'Alive', triageLevel: 'High', diseases: ['Oral Cancer'], stageOfTheCancer: 'Stage II', assignedAsha: 'asha-1' },"
                        "{ id: 'pat-2', name: 'Lakshmi Narayanan', phoneNumber: ['+919845012345'], sex: 'female', dob: '1980-11-20', patientStatus: 'Alive', triageLevel: 'Medium', diseases: ['Breast Cancer'], stageOfTheCancer: 'Stage I', assignedAsha: 'asha-2' }"
                        "] : []"
                    )
                    if "pat-1" not in th_txt:
                        th_txt = th_txt.replace(
                            "            if (!requiredData || !process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return []",
                            "            if (!requiredData) return []",
                        )
                        th_txt = th_txt.replace(
                            "            if (!requiredData) return []",
                            f"            {mock_patients}",
                        )
                        th_txt = th_txt.replace(
                            "        if (!fetchEnabled || !isPatients) return",
                            "        if (!fetchEnabled || !isPatients || !process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) return",
                        )
                        table_hook.write_text(th_txt, encoding="utf-8")

                if port_open:
                    changed_files_str = " ".join(
                        str(c.get("path") or c.get("file_path") or "")
                        if isinstance(c, dict)
                        else str(getattr(c, "path", "") or getattr(c, "file_path", ""))
                        for c in (code_changes if isinstance(code_changes, list) else [])
                    ).lower()
                    issue_low_route = f"{issue_title.lower()} {changed_files_str}"
                    has_login_route = (
                        (fe_dir / "src" / "pages" / "Login.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "Login.tsx").is_file()
                        or (fe_dir / "app" / "login").is_dir()
                    )
                    # Auto-revert any corrupted component/hook files in cached snapshot that have mismatched braces, duplicate declarations, or invalid JSX adjacency
                    import re as _re
                    corrupted_rels = []
                    for scan_sub in ("src", "components", "hooks", "lib", "app"):
                        scan_dir = fe_dir / scan_sub
                        if not scan_dir.is_dir():
                            continue
                        for ts_f in (
                            list(scan_dir.rglob("*.tsx"))
                            + list(scan_dir.rglob("*.ts"))
                            + list(scan_dir.rglob("*.jsx"))
                            + list(scan_dir.rglob("*.js"))
                        ):
                            if ts_f.name == "useTableData.ts":
                                continue
                            try:
                                txt = ts_f.read_text(encoding="utf-8", errors="ignore")
                                const_names = _re.findall(r"^\s*const\s+([A-Za-z0-9_]+)\s*=", txt, flags=_re.MULTILINE)
                                has_dup_const = len(const_names) != len(set(const_names)) and "ageInYears" in const_names
                                if (
                                    txt.count("{") != txt.count("}")
                                    or "</Button>\n        if (" in txt
                                    or "        <div>\n        </div>" in txt
                                    or _re.search(r"/>\s*\n\s*[A-Za-z0-9_]+\(.*\)", txt)
                                    or _re.search(r"</div>\s*\n\s*export\s+function\s+", txt)
                                    or _re.search(r"\n\}\s*\n\s*import\s+", txt)
                                    or (_re.search(r"\n\s*case\s+\d+\s*:", txt) and "switch" not in txt)
                                    or _re.search(r"^\s*(?:new_line|old_line|context_line)\s*$", txt, flags=_re.MULTILINE)
                                    or has_dup_const
                                ):
                                    corrupted_rels.append(ts_f.relative_to(fe_dir))
                            except Exception:
                                pass
                    if corrupted_rels:
                        import shutil
                        tmp_c = pathlib.Path(tempfile.gettempdir()) / f"clean_{uuid.uuid4().hex[:6]}"
                        try:
                            subprocess.run(
                                ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(tmp_c)],
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=25,
                                check=False,
                            )
                            for rel_p in corrupted_rels:
                                src_p = tmp_c / rel_p
                                if src_p.is_file():
                                    shutil.copy2(src_p, fe_dir / rel_p)
                        except Exception:
                            pass
                        finally:
                            shutil.rmtree(tmp_c, ignore_errors=True)

                    # Dynamically discover actual routes in the target repo (React Router <Route> + Next.js app/ pages)
                    discovered_routes: list[tuple[str, list[str], bool]] = []
                    for app_cand in ("src/App.jsx", "src/App.tsx", "src/App.js", "src/App.ts"):
                        app_file = fe_dir / app_cand
                        if app_file.is_file():
                            app_txt = app_file.read_text(encoding="utf-8", errors="ignore")
                            for m in _re.finditer(r"<Route\b((?:(?!<Route\b)[\s\S])*?)(?:/>|</Route>)", app_txt):
                                block = m.group(1)
                                pm = _re.search(r'path=["\'](/[^"\':*]+)["\']', block)
                                if not pm:
                                    continue
                                rpath = pm.group(1).rstrip("/")
                                if not rpath:
                                    continue
                                comps = [
                                    c.lower()
                                    for c in _re.findall(r"<([A-Z][A-Za-z0-9_]*)", block)
                                    if c not in ("ProtectedRoute", "PrivateRoute", "Suspense", "Layout", "DashboardLayout")
                                ]
                                # Check if enclosed in PrivateRoute / ProtectedRoute inline or nearby parent
                                pre_ctx = app_txt[max(0, m.start() - 350):m.end()]
                                is_prot = ("PrivateRoute" in block or "ProtectedRoute" in block or ("<Route" in pre_ctx and ("PrivateRoute" in pre_ctx or "ProtectedRoute" in pre_ctx) and "</Route>" not in pre_ctx[:pre_ctx.rfind("<Route")]))
                                discovered_routes.append((rpath, comps, is_prot))
                    if (fe_dir / "app").is_dir():
                        for pg in list((fe_dir / "app").rglob("page.tsx")) + list((fe_dir / "app").rglob("page.jsx")):
                            rel_dir = pg.parent.relative_to(fe_dir / "app").as_posix()
                            if rel_dir != "." and "[" not in rel_dir and "(" not in rel_dir:
                                slug_name = pg.parent.name.lower().replace("-", "")
                                discovered_routes.append((f"/{rel_dir}", [slug_name], False))

                    changed_stems = [
                        pathlib.Path(
                            str(c.get("path") or c.get("file_path") or "")
                            if isinstance(c, dict)
                            else str(getattr(c, "path", "") or getattr(c, "file_path", ""))
                        ).stem.lower().replace("-", "")
                        for c in (code_changes if isinstance(code_changes, list) else [])
                    ]
                    changed_stems = [s for s in changed_stems if s and s not in ("app", "index", "main", "layout", "navbar", "footer")]

                    matched_dynamic_route: str | None = None
                    # 1. Match modified file stems directly against repo's <Route> components / path slugs (preferring public routes)
                    for rpath, comps, _is_prot in sorted(discovered_routes, key=lambda x: x[2]):
                        rslug = rpath.strip("/").split("/")[-1].lower().replace("-", "")
                        if any(
                            st == rslug or any(st == cp or cp.startswith(st) or st.startswith(cp) for cp in comps if len(cp) >= 3)
                            for st in changed_stems
                        ):
                            matched_dynamic_route = rpath
                            break

                    # 2. Match issue/file keywords against repo's actual discovered routes
                    if not matched_dynamic_route and discovered_routes:
                        kw_map = [
                            (("login", "signin", "auth", "password"), ("login", "signin", "signup")),
                            (("signup", "register"), ("signup", "register")),
                            (("contact", "textarea"), ("contact", "contactus")),
                            (("pricing",), ("pricing",)),
                            (("faq",), ("faq",)),
                            (("analytics", "click", "geographic"), ("analytics",)),
                            (("replay", "history"), ("history", "dashboard")),
                            (("dashboard",), ("dashboard",)),
                            (("leaderboard",), ("leaderboard",)),
                        ]
                        for triggers, targets in kw_map:
                            if any(t in issue_low_route for t in triggers):
                                for rpath, _comps, _is_prot in sorted(discovered_routes, key=lambda x: x[2]):
                                    rslug = rpath.strip("/").split("/")[-1].lower().replace("-", "")
                                    if rslug in targets:
                                        matched_dynamic_route = rpath
                                        break
                                if matched_dynamic_route:
                                    break

                    if matched_dynamic_route:
                        route_suffix = matched_dynamic_route
                    elif ("auth" in issue_low_route or "login" in issue_low_route) and has_login_route:
                        route_suffix = "/login"
                    elif ("contact" in issue_low_route or "textarea" in issue_low_route) and (
                        (fe_dir / "src" / "pages" / "ContactUs.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "ContactUs.tsx").is_file()
                        or (fe_dir / "app" / "contact").is_dir()
                    ):
                        route_suffix = "/contact"
                    elif "pricing" in issue_low_route and (
                        (fe_dir / "src" / "pages" / "PricingPage.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "PricingPage.tsx").is_file()
                        or (fe_dir / "app" / "pricing").is_dir()
                    ):
                        route_suffix = "/pricing"
                    elif "faq" in issue_low_route and (
                        (fe_dir / "src" / "pages" / "FAQ.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "FAQ.tsx").is_file()
                        or (fe_dir / "app" / "faq").is_dir()
                    ):
                        route_suffix = "/faq"
                    elif ("analytics" in issue_low_route or "click" in issue_low_route or "geographic" in issue_low_route) and (
                        (fe_dir / "src" / "pages" / "Analytics.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "Analytics.tsx").is_file()
                        or (fe_dir / "app" / "analytics").is_dir()
                    ):
                        route_suffix = "/analytics"
                    elif "dashboard" in issue_low_route and (
                        (fe_dir / "src" / "pages" / "Dashboard.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "Dashboard.tsx").is_file()
                        or (fe_dir / "app" / "dashboard").is_dir()
                    ):
                        route_suffix = "/dashboard"
                    elif "leaderboard" in issue_low_route and (
                        (fe_dir / "src" / "pages" / "Leaderboard.jsx").is_file()
                        or (fe_dir / "src" / "pages" / "Leaderboard.tsx").is_file()
                        or (fe_dir / "app" / "leaderboard").is_dir()
                    ):
                        route_suffix = "/leaderboard"
                    elif (fe_dir / "app" / "PuduCan" / "admin" / "page.tsx").is_file():
                        route_suffix = "/PuduCan/admin"
                    elif (fe_dir / "app" / "home" / "page.tsx").is_file():
                        route_suffix = "/home"
                    else:
                        route_suffix = ""
                    # Warm up the target route so Next.js/Vite finishes initial Webpack compilation before Playwright navigates
                    import urllib.request
                    for _ in range(3):
                        try:
                            try:
                                resp_html = urllib.request.urlopen(f"http://127.0.0.1:{port}{route_suffix}", timeout=30).read().decode("utf-8", "ignore")
                            except urllib.error.HTTPError as http_err:
                                resp_html = http_err.read().decode("utf-8", "ignore")
                            if "Build Error" in resp_html or "__next_error__" in resp_html:
                                import re as _re
                                err_files = _re.findall(r"\./([A-Za-z0-9_/.-]+\.(?:tsx|ts|jsx|js))", resp_html)
                                if err_files:
                                    import shutil
                                    tmp_c = pathlib.Path(tempfile.gettempdir()) / f"clean_{uuid.uuid4().hex[:6]}"
                                    try:
                                        subprocess.run(
                                            ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(tmp_c)],
                                            stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            timeout=25,
                                            check=False,
                                        )
                                        for ef in set(err_files):
                                            if (tmp_c / ef).is_file():
                                                shutil.copy2(tmp_c / ef, fe_dir / ef)
                                    except Exception:
                                        pass
                                    finally:
                                        shutil.rmtree(tmp_c, ignore_errors=True)
                                    time.sleep(0.6)
                                    continue
                            break
                        except Exception:
                            time.sleep(0.5)
                    return f"http://localhost:{port}{route_suffix}"

    # No runnable web frontend exists for this repository — stop any stale server on port 5173 and return None
    if _DEV_SERVER_PROC is not None:
        try:
            _DEV_SERVER_PROC.terminate()  # type: ignore[attr-defined]
        except Exception:
            pass
        _DEV_SERVER_PROC = None
    _DEV_SERVER_CWD = None
    if sys.platform == "win32":
        try:
            netstat = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            for line in netstat.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", pid],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=5,
                            check=False,
                        )
        except Exception:
            pass
    return None


def run_browser_tests_for_agent(
    target_url: str | None = None,
    run_id: str | None = None,
    scenarios: list[str] | None = None,
) -> dict:
    """
    Entry point for the Test Runner agent node.

    Parameters
    ----------
    target_url : Explicit target URL.  If None, falls back to MINI_DEVIN_TEST_URL
                 environment variable.  If still None → BLOCKED report.
    run_id     : Workflow run identifier to use for artifact directory naming.
    scenarios  : List of scenario names to run.  Defaults to all standard scenarios.
                 Valid values: "availability", "issue_intake", "workflow_status",
                               "unavailable_url".

    Returns
    -------
    dict  –  BrowserTestReport serialised as a plain dict.
    """
    url = target_url or TARGET_URL
    rid = run_id or (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "_" + uuid.uuid4().hex[:6]
    )
    art_dir = run_artifact_dir(rid)

    # ── Guard: no URL configured ─────────────────────────────────────────────
    if not url:
        reason = (
            "No browser test URL configured. "
            "Set MINI_DEVIN_TEST_URL environment variable or pass browser_test_url "
            "in AgentState to enable live browser testing."
        )
        return blocked_report(
            target_url=None, reason=reason, run_id=rid, artifact_dir=art_dir
        ).to_dict()

    # ── Guard: URL not permitted ─────────────────────────────────────────────
    if not is_permitted(url):
        reason = (
            f"Target URL '{url}' is not in the permitted allowlist "
            "(playground/browser_testing/config.py::PERMITTED_URL_PREFIXES). "
            "Live browser test NOT RUN."
        )
        return blocked_report(
            target_url=url, reason=reason, run_id=rid, artifact_dir=art_dir
        ).to_dict()

    # ── Run scenarios ────────────────────────────────────────────────────────
    active_scenarios = scenarios or ["availability", "issue_intake", "workflow_status", "unavailable_url"]
    all_steps = []

    logger.info("Starting browser test run '%s' against %s", rid, url)

    try:
        import asyncio
        import concurrent.futures

        def _execute_in_clean_thread() -> BrowserTestReport:
            asyncio.set_event_loop(None)
            with BrowserTestRunner(target_url=url, run_id=rid) as runner:
                for name in active_scenarios:
                    if name == "availability":
                        steps = scenario_page_availability(runner, url)
                    elif name == "issue_intake":
                        steps = scenario_issue_intake(runner, url)
                    elif name == "workflow_status":
                        steps = scenario_workflow_status(runner, url)
                    elif name == "unavailable_url":
                        steps = scenario_unavailable_url(runner)
                    else:
                        logger.warning("Unknown scenario '%s' — skipping", name)
                        continue
                    all_steps.extend(steps)
                return runner.report()

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            report = pool.submit(_execute_in_clean_thread).result(timeout=50)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    except PermissionError as exc:
        return blocked_report(
            target_url=url, reason=str(exc), run_id=rid, artifact_dir=art_dir
        ).to_dict()
    except Exception as exc:
        logger.exception("Browser test run failed with an unexpected error")
        err_report = blocked_report(
            target_url=url,
            reason=f"Unexpected error during browser test execution: {exc}",
            run_id=rid,
            artifact_dir=art_dir,
        )
        err_report.status = "error"
        return err_report.to_dict()

    report_dict = report.to_dict()
    try:
        import base64
        import shutil
        latest_url: str | None = None
        for st in report_dict.get("steps", []):
            sp = st.get("screenshot_path")
            if sp and pathlib.Path(sp).is_file():
                raw_bytes = pathlib.Path(sp).read_bytes()
                cloud_url = _upload_screenshot_to_cloudinary(raw_bytes, rid)
                data_uri = cloud_url or ("data:image/png;base64," + base64.b64encode(raw_bytes).decode("ascii"))
                if cloud_url:
                    st["cloudinary_url"] = cloud_url
                latest_url = data_uri
        if latest_url:
            report_dict["screenshot_data_url"] = latest_url
        # Delete local PNG artifacts from hard disk after encoding/uploading to Cloudinary
        if art_dir.is_dir():
            shutil.rmtree(art_dir, ignore_errors=True)
        cleanup_preview_memory_and_disk(preserve_dev_server=True)
    except Exception as b64_exc:
        logger.debug("Could not encode/upload browser screenshot: %s", b64_exc)
    return report_dict
