import logging
import uuid
from typing import Dict

logger = logging.getLogger(__name__)

# Allowed imports for sandboxed execution
ALLOWED_IMPORTS = {
    "math", "random", "statistics", "datetime", "json", "re",
    "urllib.parse", "base64", "hashlib", "collections", "itertools",
    "string", "decimal", "fractions", "functools", "operator",
    "textwrap", "csv", "io","pandas",
}

DANGEROUS_KEYWORDS = [
    "__import__", "exec(", "eval(", "compile(", "open(",
    "os.", "sys.", "subprocess", "shutil.", "pathlib.",
    "socket.", "ctypes.", "signal.", "multiprocessing.",
    "importlib.", "builtins.", "globals(", "locals(",
]

DOCKER_IMAGE = "python:3.11-alpine"
CONTAINER_TIMEOUT = 30  # seconds
MAX_OUTPUT = 2000  # chars


def _check_code_safety(code: str):
    """Returns error message if code is unsafe, None if OK."""
    code_lower = code.lower()
    for kw in DANGEROUS_KEYWORDS:
        if kw.lower() in code_lower:
            return f"Security error: '{kw}' is not allowed"

    # Split on both newlines and semicolons to handle one-liner code
    statements = []
    for line in code.split("\n"):
        for part in line.split(";"):
            statements.append(part.strip())

    for stripped in statements:
        if stripped.startswith("import ") or stripped.startswith("from "):
            parts = stripped.split()
            if len(parts) >= 2:
                module = parts[1].split(".")[0].strip(",")
                if module not in ALLOWED_IMPORTS:
                    return f"Security error: module '{module}' not allowed"
    return None


async def run_python(code: str, **kwargs) -> Dict[str, str]:
    """Execute Python code in a sandboxed Docker container.
    
    Security: no network, read-only FS, memory/CPU/PID limits,
    all capabilities dropped, no-new-privileges.
    """

    logger.info(f"python_exec called with code ({len(code)} chars): {code[:200]}")

    # Pre-check before spinning up a container
    safety_err = _check_code_safety(code)
    if safety_err:
        logger.warning(f"python_exec safety check FAILED: {safety_err}")
        return {"stdout": "", "stderr": safety_err, "returncode": -1}
    logger.info("python_exec safety check passed")

    container_name = f"aether_sandbox_{uuid.uuid4().hex[:12]}"

    try:
        import docker
        client = docker.from_env()
        logger.info(f"Docker client connected, creating container '{container_name}'")
    except Exception as e:
        logger.error(f"Docker not available: {e}")
        return {
            "stdout": "",
            "stderr": f"Docker not available: {str(e)[:100]}",
            "returncode": -1,
        }

    try:
        # Run code in an isolated container with strict limits
        container = client.containers.run(
            image=DOCKER_IMAGE,
            command=["python", "-c", code],
            name=container_name,
            detach=True,
            network_mode="none",
            read_only=True,
            tmpfs={"/tmp": "size=10m,noexec"},
            mem_limit="64m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% of one CPU
            pids_limit=32,
            security_opt=["no-new-privileges"],
            cap_drop=["ALL"],
        )

        # Wait for container to finish (with timeout)
        try:
            result = container.wait(timeout=CONTAINER_TIMEOUT)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            try:
                container.kill()
            except Exception:
                pass
            return {
                "stdout": "",
                "stderr": f"Execution timeout ({CONTAINER_TIMEOUT}s limit)",
                "returncode": -1,
            }

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        logger.info(f"python_exec completed: exit={exit_code}, stdout={len(stdout)} chars, stderr={len(stderr)} chars")
        if stdout:
            logger.info(f"python_exec stdout: {stdout[:300]}")
        if stderr:
            logger.warning(f"python_exec stderr: {stderr[:300]}")

        return {
            "stdout": stdout[:MAX_OUTPUT],
            "stderr": stderr[:MAX_OUTPUT],
            "returncode": exit_code,
        }

    except docker.errors.ImageNotFound:
        # Auto-pull the image on first use
        try:
            client.images.pull(DOCKER_IMAGE)
            return await run_python(code)  # retry once after pull
        except Exception as e2:
            return {
                "stdout": "",
                "stderr": f"Failed to pull sandbox image: {str(e2)[:200]}",
                "returncode": -1,
            }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Sandbox error: {str(e)[:200]}",
            "returncode": -1,
        }
    finally:
        # Always clean up the container
        try:
            c = client.containers.get(container_name)
            c.remove(force=True)
        except Exception:
            pass
