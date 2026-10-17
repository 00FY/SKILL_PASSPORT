import uuid
from datetime import datetime, timezone
from typing import List
from ..schemas import AuditStep, RunAuditLog

class AuditTracer:
    """
    Records micro-trace audit events for every rule, AST check, blame match,
    and rubric calculation, serialized into run.json.
    """

    def __init__(self, candidate_name: str):
        self.candidate_name = candidate_name
        self.audit_id = f"audit_{uuid.uuid4().hex[:10]}"
        self.steps: List[AuditStep] = []

    def record(self, step: str, target: str, rule_applied: str, verdict_reached: str):
        self.steps.append(
            AuditStep(
                step=step,
                target=target,
                rule_applied=rule_applied,
                verdict_reached=verdict_reached,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )

    def finalize(self) -> RunAuditLog:
        return RunAuditLog(
            audit_id=self.audit_id,
            candidate_name=self.candidate_name,
            traces=self.steps,
            generated_at=datetime.now(timezone.utc).isoformat()
        )
