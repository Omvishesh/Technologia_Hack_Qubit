"""
Incident Response Agents

Each agent is a specialized LLM-powered component in the pipeline:
- LogAnalyzer: Summarizes logs and extracts error signals
- HypothesisGenerator: Generates top-3 ranked root cause hypotheses
- VerificationExecutor: Calls verification tools for each hypothesis
- RCAAgent: Confirms root cause from evidence
- RemediationAgent: Proposes safe remediation actions
- SafetyAgent: Validates actions against the allowlist
"""

