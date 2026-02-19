from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from typing import List
import json
from pathlib import Path

class State(str, Enum):
    PLANNED="PLANNED"
    READY="READY"
    NEEDS_APPROVAL="NEEDS_APPROVAL"
    RUNNING="RUNNING"
    VERIFYING="VERIFYING"
    DONE="DONE"
    BLOCKED="BLOCKED"
    ABORTED="ABORTED"

@dataclass
class Task:
    id: str
    title: str
    requires: List[str] = field(default_factory=list)
    state: State = State.PLANNED
    note: str = ""
    attempts: int = 0

@dataclass
class Goal:
    id: str
    objective: str
    deadline: datetime
    success_criteria: List[str]
    tasks: List[Task]

class Policy:
    def __init__(self, grants: List[str]):
        self.grants = set(grants)
    def allowed(self, reqs: List[str]) -> bool:
        return set(reqs).issubset(self.grants)
    def grant(self, perm: str):
        self.grants.add(perm)

class GoalRuntime:
    def __init__(self, goal: Goal, policy: Policy, artifact_dir: str = "artifacts"):
        self.goal=goal
        self.policy=policy
        self.log=[]
        self.artifact_dir=Path(artifact_dir)/goal.id
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def checkpoints(self):
        d=self.goal.deadline
        return {
            "T-120": d - timedelta(minutes=120),
            "T-60": d - timedelta(minutes=60),
            "T-15": d - timedelta(minutes=15),
            "T": d,
        }

    def _record(self, task: Task, state: State, note: str):
        task.state=state
        task.note=note
        self.log.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "task": task.id,
            "state": state.value,
            "note": note,
            "attempts": task.attempts,
        })

    def tick(self):
        for t in self.goal.tasks:
            if t.state in {State.DONE, State.BLOCKED, State.ABORTED}:
                continue
            if t.state==State.PLANNED:
                self._record(t, State.READY, "ready")

            if t.state in {State.READY, State.NEEDS_APPROVAL}:
                missing=sorted(set(t.requires)-self.policy.grants)
                if missing:
                    t.attempts += 1
                    self._record(t, State.NEEDS_APPROVAL, f"Missing permissions: {', '.join(missing)}")
                    # backoff -> block after 3 failed checks
                    if t.attempts >= 3:
                        self._record(t, State.BLOCKED, "approval not resolved after 3 retries")
                    return

                t.attempts += 1
                self._record(t, State.RUNNING, "started")
                self._record(t, State.VERIFYING, "verifying outputs")
                self._record(t, State.DONE, "completed")
                return

    def save_artifacts(self):
        status = {
            "goal": {
                "id": self.goal.id,
                "objective": self.goal.objective,
                "deadline": self.goal.deadline.isoformat(timespec="minutes"),
                "success_criteria": self.goal.success_criteria,
            },
            "tasks": [
                {
                    **asdict(t),
                    "state": t.state.value,
                }
                for t in self.goal.tasks
            ],
            "checkpoints": {k:v.isoformat(timespec="minutes") for k,v in self.checkpoints().items()},
        }
        (self.artifact_dir/"status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2))
        (self.artifact_dir/"runs.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in self.log)+"\n")
        (self.artifact_dir/"status.md").write_text(self.summary()+"\n")

    def summary(self) -> str:
        done=[t for t in self.goal.tasks if t.state==State.DONE]
        pending=[t for t in self.goal.tasks if t.state in {State.PLANNED,State.READY,State.RUNNING,State.VERIFYING}]
        blocked=[t for t in self.goal.tasks if t.state in {State.NEEDS_APPROVAL,State.BLOCKED,State.ABORTED}]
        lines=[
            f"Goal: {self.goal.objective}",
            f"Deadline: {self.goal.deadline.isoformat(timespec='minutes')}",
            f"✅ done: {len(done)}",
            f"⏳ pending: {len(pending)}",
            f"🚫 blocked: {len(blocked)}",
        ]
        if blocked:
            lines.append("Blocked details:")
            for t in blocked:
                lines.append(f"- {t.id} {t.title}: {t.note}")
        return "\n".join(lines)

if __name__ == "__main__":
    g=Goal(
        id="goal-002",
        objective="Deliver persistent autonomous goal runtime with checkpoints",
        deadline=datetime.now()+timedelta(hours=6),
        success_criteria=["state machine","artifact persistence","checkpoint schedule"],
        tasks=[
            Task("T1","collect docs and behavior model",requires=[]),
            Task("T2","draft architecture proposal",requires=[]),
            Task("T3","publish GitHub release notes",requires=["github:push"]),
        ],
    )
    runtime=GoalRuntime(g,Policy(grants=[]),artifact_dir="artifacts")
    for _ in range(8):
        runtime.tick()
    runtime.save_artifacts()
    print(runtime.summary())
