"""SEO advisor powered by the Claude CLI.

Calls the ``claude`` CLI binary via subprocess per request.
Authentication uses existing ``claude login`` OAuth (user's subscription) —
no API key needed in the app.

No dependency on ``claude-agent-sdk`` — uses asyncio subprocess directly,
avoiding the starlette version conflict between ``mcp`` and FastAPI.
"""

import asyncio
import logging
import shutil

from modules.seo.adapters.advisor_utils import (
    SYSTEM_PROMPT,
    build_prompt,
    parse_suggestions,
)
from modules.seo.interfaces.seo_advisor import (
    AdvisorResult,
    SEOAdvisorProvider,
)

logger = logging.getLogger(__name__)

_MAX_TURNS = 5
_ADVISOR_TIMEOUT = 90  # seconds

# Backward-compatible aliases for test imports
from modules.seo.adapters.advisor_utils import (  # noqa: E402, F401
    truncate_html as _truncate_html,
    build_prompt as _build_prompt,
    parse_suggestions as _parse_suggestions,
)

_SYSTEM_PROMPT = SYSTEM_PROMPT
_MAX_BODY_LINES = 150


class ClaudeSDKAdvisor(SEOAdvisorProvider):
    """SEO advisor using the Claude CLI (subprocess per request).

    Authentication uses existing ``claude login`` OAuth — no API key needed.
    Each analyze() call spawns a fresh ``claude -p`` process and reads stdout.
    """

    @staticmethod
    def _sdk_available() -> bool:
        """Check if the claude CLI is on PATH."""
        return shutil.which("claude") is not None

    @staticmethod
    async def _cli_healthy() -> tuple[bool, str]:
        """Quick check that the CLI can actually run with the restricted env.

        Returns (healthy, detail) where detail contains CLI output on failure.
        """
        cli_path = shutil.which("claude")
        if not cli_path:
            return False, "claude binary not found"
        try:
            proc = await asyncio.create_subprocess_exec(
                cli_path,
                "-p",
                "respond with ok",
                "--max-turns",
                "1",
                "--output-format",
                "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "HOME": "/home/appuser",
                    "CLAUDECODE": "",
                    "CLAUDE_CODE_ENTRYPOINT": "",
                },
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=10,
            )
            if proc.returncode == 0:
                return True, ""
            detail = (
                stdout.decode("utf-8", errors="replace").strip()
                or stderr.decode("utf-8", errors="replace").strip()
                or f"exit code {proc.returncode}"
            )
            return False, detail
        except asyncio.TimeoutError:
            proc.kill()
            return False, "health check timed out"
        except Exception as exc:
            return False, str(exc)

    async def _run_analysis(self, prompt: str) -> AdvisorResult:
        """Spawn ``claude -p`` with the prompt and parse the output."""
        cli_path = shutil.which("claude")

        full_prompt = f"<system>\n{SYSTEM_PROMPT}\n</system>\n\n{prompt}"

        proc = await asyncio.create_subprocess_exec(
            cli_path,
            "-p",
            full_prompt,
            "--max-turns",
            str(_MAX_TURNS),
            "--output-format",
            "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": "/home/appuser",
                "CLAUDECODE": "",
                "CLAUDE_CODE_ENTRYPOINT": "",
            },
        )

        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error("Claude CLI exited with code %d: %s", proc.returncode, err_msg)
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI error (exit {proc.returncode}): {err_msg[:200]}",
            )

        if not output:
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error="Claude CLI returned empty output.",
            )

        suggestions = parse_suggestions(output)

        if not suggestions:
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error="Could not parse suggestions from Claude response.",
            )

        return AdvisorResult(
            suggestions=suggestions,
            provider="claude_cli",
        )

    async def analyze(
        self,
        path: str,
        html: str,
        scores: dict,
        rule_results: list[dict],
        target_keywords: list[str] | None = None,
        business_context: str | None = None,
        intent: str | None = None,
    ) -> AdvisorResult:
        if not self._sdk_available():
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=(
                    "Claude CLI not available. Install @anthropic-ai/claude-code "
                    "and authenticate via 'claude login'."
                ),
            )

        healthy, detail = await self._cli_healthy()
        if not healthy:
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI not ready: {detail}",
            )

        prompt = build_prompt(
            path,
            html,
            scores,
            rule_results,
            target_keywords,
            business_context,
            intent,
        )

        try:
            result = await asyncio.wait_for(
                self._run_analysis(prompt),
                timeout=_ADVISOR_TIMEOUT,
            )
            return result

        except asyncio.TimeoutError:
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=(
                    f"Analysis timed out after {_ADVISOR_TIMEOUT} seconds. "
                    "Try again or simplify your request."
                ),
            )

        except Exception as e:
            error_type = type(e).__name__
            logger.error("Claude CLI advisor error: %s: %s", error_type, e)
            return AdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI error: {error_type}: {e}",
            )
