"""
Agent 3 — Verification Executor

Executes the verification tool calls for each hypothesis and collects results.
The LLM decides which tools to call based on the hypotheses.
"""

from __future__ import annotations

import logging

from ..models import Incident, Hypothesis, ToolResult
from ..tools.verification_tools import call_verification_tool

logger = logging.getLogger("incident-response.agents.verification_executor")


async def execute_verifications(incident: Incident) -> list[ToolResult]:
    """
    Run the verification tool for each hypothesis and return the results.

    Each hypothesis specifies which tool to call. We call each one
    and collect the ToolResult objects.

    Args:
        incident: The Incident with hypotheses populated.

    Returns:
        List of ToolResult objects (one per hypothesis).
    """
    results: list[ToolResult] = []
    seen_tools: set[str] = set()

    for hypothesis in incident.hypotheses:
        tool_name = hypothesis.verification_tool

        # Avoid calling the same tool twice
        if tool_name in seen_tools:
            logger.info(
                "Skipping duplicate tool call '%s' for hypothesis #%d",
                tool_name,
                hypothesis.rank,
            )
            continue

        seen_tools.add(tool_name)

        logger.info(
            "Calling verification tool '%s' for hypothesis #%d: %s",
            tool_name,
            hypothesis.rank,
            hypothesis.title,
        )

        try:
            result = await call_verification_tool(tool_name)
            results.append(result)

            logger.info(
                "Tool '%s' returned: success=%s, result=%s",
                tool_name,
                result.success,
                result.result if result.success else result.error,
            )

        except Exception as exc:
            logger.error("Tool '%s' execution failed: %s", tool_name, exc)
            results.append(ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Execution error: {type(exc).__name__}: {exc}",
            ))

    logger.info(
        "Verification complete: %d/%d tools succeeded",
        sum(1 for r in results if r.success),
        len(results),
    )

    return results

