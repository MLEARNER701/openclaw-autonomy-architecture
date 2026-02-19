from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Optional

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

class GoalRuntime:
    def __init__(self, goal: Goal, policy: Policy):
        self.goal=goal
        self.policy=policy
        self.log=[]

    def tick(self):
        for t in self.goal.tasks:
            if t.state in {State.DONE, State.BLOCKED, State.ABORTED}:
                continue
            if t.state==State.PLANNED:
                t.state=State.READY
            if t.state==State.READY:
                if not self.policy.allowed(t.requires):
                    t.state=State.NEEDS_APPROVAL
                    t.note=f"Missing permissions: {', '.join(sorted(set(t.requires)-self.policy.grants))}"
                    self.log.append((t.id,t.state,t.note))
                    continue
                t.state=State.RUNNING
                self.log.append((t.id,t.state,"started"))
                t.state=State.VERIFYING
                self.log.append((t.id,t.state,"verifying outputs"))
                t.state=State.DONE
                t.note="completed"
                self.log.append((t.id,t.state,t.note))
            elif t.state==State.NEEDS_APPROVAL:
                self.log.append((t.id,t.state,t.note))
            return  # one task per tick for deterministic progression

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
        id="goal-001",
        objective="Analyze OpenClaw runtime and deliver architecture + prototype",
        deadline=datetime.now()+timedelta(hours=6),
        success_criteria=["analysis report","prototype code","next actions"],
        tasks=[
            Task("T1","collect docs and behavior model",requires=[]),
            Task("T2","draft architecture proposal",requires=[]),
            Task("T3","push to GitHub repo",requires=["github:push"]),
        ],
    )
    runtime=GoalRuntime(g,Policy(grants=[]))
    for _ in range(6):
        runtime.tick()
    print(runtime.summary())
