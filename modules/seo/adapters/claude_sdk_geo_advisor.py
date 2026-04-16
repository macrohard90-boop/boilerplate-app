"""GEO advisor powered by the Claude CLI.

Calls the ``claude`` CLI binary via subprocess per request.
Authentication uses existing ``claude login`` OAuth (user's subscription) —
no API key needed in the app.

Follows the same pattern as ``claude_sdk_advisor.py`` but uses GEO-specific
system prompts and response parsing.
"""

import asyncio
import logging
import shutil

from modules.seo.adapters.geo_advisor_utils import (
    GEO_SYSTEM_PROMPT,
    build_geo_prompt,
    parse_geo_suggestions,
)
from modules.seo.interfaces.geo_advisor import (
    GEOAdvisorProvider,
    GEOAdvisorResult,
)

logger = logging.getLogger(__name__)

_MAX_TURNS = 5
_ADVISOR_TIMEOUT = 90  # seconds


class ClaudeSDKGEOAdvisor(GEOAdvisorProvider):
    """GEO advisor using the Claude CLI (subprocess per request).

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
                cli_path, "-p", "respond with ok", "--max-turns", "1",
                "--output-format", "text",
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
                proc.communicate(), timeout=10,
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

    async def _run_analysis(self, prompt: str) -> GEOAdvisorResult:
        """Spawn ``claude -p`` with the prompt and parse the output."""
        cli_path = shutil.which("claude")

        full_prompt = (
            f"<system>\n{GEO_SYSTEM_PROMPT}\n</system>\n\n{prompt}"
        )

        proc = await asyncio.create_subprocess_exec(
            cli_path,
            "-p", full_prompt,
            "--max-turns", str(_MAX_TURNS),
            "--output-format", "text",
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
            logger.error(
                "Claude CLI (GEO) exited with code %d: %s",
                proc.returncode, err_msg,
            )
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI error (exit {proc.returncode}): {err_msg[:200]}",
            )

        if not output:
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error="Claude CLI returned empty output.",
            )

        suggestions = parse_geo_suggestions(output)

        if not suggestions:
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error="Could not parse GEO suggestions from Claude response.",
            )

        return GEOAdvisorResult(
            suggestions=suggestions,
            provider="claude_cli",
        )

    async def analyze(
        self,
        path: str,
        html: str,
        scores: dict,
        dimension_scores: dict[str, int],
        rule_results: list[dict],
        business_context: str | None = None,
        intent: str | None = None,
    ) -> GEOAdvisorResult:
        if not self._sdk_available():
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=(
                    "Claude CLI not available. Install @anthropic-ai/claude-code "
                    "and authenticate via 'claude login'."
                ),
            )

        healthy, detail = await self._cli_healthy()
        if not healthy:
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI not ready: {detail}",
            )

        prompt = build_geo_prompt(
            path, html, scores, dimension_scores, rule_results,
            business_context, intent,
        )

        try:
            result = await asyncio.wait_for(
                self._run_analysis(prompt),
                timeout=_ADVISOR_TIMEOUT,
            )
            return result

        except asyncio.TimeoutError:
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=(
                    f"Analysis timed out after {_ADVISOR_TIMEOUT} seconds. "
                    "Try again or simplify your request."
                ),
            )

        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                "Claude CLI GEO advisor error: %s: %s", error_type, e,
            )
            return GEOAdvisorResult(
                suggestions=[],
                provider="claude_cli",
                error=f"Claude CLI error: {error_type}: {e}",
            )
