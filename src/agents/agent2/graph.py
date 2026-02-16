"""
Agent 2 (Task Allocator) — Optimization-based assignment.

Uses Python logic (skill match + complexity) to assign tasks to developers.
No LLM required for the core algorithm; can be extended with LLM for reasoning.
"""

from __future__ import annotations

from typing import TypedDict

from .models import (
    Assignment,
    Developer,
    Task,
    TaskAllocationResult,
)


def user_stories_to_tasks(user_stories: list) -> list[Task]:
    """Convert Agent 1 UserStory list to Agent 2 Task list (for pipeline use)."""
    tasks: list[Task] = []
    for us in user_stories:
        # Handle both Pydantic model and dict (e.g. from JSON)
        if hasattr(us, "model_dump"):
            us = us.model_dump()
        task_id = us.get("id", "?")
        action = us.get("action", us.get("title", ""))
        priority = us.get("priority", "Medium")
        tasks.append(
            Task(
                id=task_id,
                title=action,
                complexity=priority,
                required_skills=[],  # Could be enriched by LLM later
            )
        )
    return tasks

# Complexity weight: higher = prefer assigning complex tasks to skilled devs
COMPLEXITY_WEIGHT = {"Low": 1, "Medium": 2, "High": 3}


def _skill_match_score(task: Task, developer: Developer) -> float:
    """Score 0..1: how well developer skills match task requirements."""
    if not task.required_skills:
        return 1.0
    dev_skills = {s.lower().strip() for s in developer.skills}
    required = {s.lower().strip() for s in task.required_skills}
    if not required:
        return 1.0
    return len(required & dev_skills) / len(required)


def _assignment_score(task: Task, developer: Developer) -> float:
    """Combined score for assigning this task to this developer."""
    skill = _skill_match_score(task, developer)
    complexity = COMPLEXITY_WEIGHT.get(task.complexity, 2)
    return skill * (1 + 0.2 * complexity)


def allocate_tasks(
    tasks: list[Task],
    developers: list[Developer],
) -> TaskAllocationResult:
    """
    Assign each task to the best available developer (skill match + capacity).

    Greedy: sort tasks by complexity (high first), then assign each to the
    developer with highest score who still has capacity.
    """
    assignments: list[Assignment] = []
    unassigned: list[str] = []
    capacity_left = {d.id: d.capacity for d in developers}
    dev_by_id = {d.id: d for d in developers}

    # Sort by complexity (high first) so we assign hard tasks first
    sorted_tasks = sorted(
        tasks,
        key=lambda t: COMPLEXITY_WEIGHT.get(t.complexity, 2),
        reverse=True,
    )

    for task in sorted_tasks:
        best_dev_id: str | None = None
        best_score = -1.0
        for dev in developers:
            if capacity_left.get(dev.id, 0) <= 0:
                continue
            score = _assignment_score(task, dev)
            if score > best_score:
                best_score = score
                best_dev_id = dev.id
        if best_dev_id is not None and best_score > 0:
            assignments.append(
                Assignment(
                    task_id=task.id,
                    developer_id=best_dev_id,
                    reason=f"Skill match + capacity ({dev_by_id[best_dev_id].name})",
                )
            )
            capacity_left[best_dev_id] -= 1
        else:
            unassigned.append(task.id)

    return TaskAllocationResult(
        assignments=assignments,
        unassigned_task_ids=unassigned,
    )


class Agent2State(TypedDict, total=False):
    """State for Agent 2 (optional LangGraph wrapper)."""

    tasks: list[Task]
    developers: list[Developer]
    result: TaskAllocationResult | None


def build_allocation_graph():
    """
    Optional: LangGraph wrapper for Agent 2. Currently allocation is
    a single deterministic step, so we expose allocate_tasks() directly.
    """
    # For future: add nodes (e.g. validate input -> allocate -> format output)
    return None
