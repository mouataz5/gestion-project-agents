"""
Agent 6 (Documentation Writer) — File browsing tools for ReAct (OF6.1–OF6.8).

All paths are relative to a project root; resolution is restricted to that root.
Includes project_stats for OF6.8 (documentation coverage) and file_mtime for OF6.7 (obsolete detection).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool


def _safe_resolve(root: Path, relative_path: str) -> Path | None:
    """Resolve relative_path under root. Return None if path escapes root."""
    root = root.resolve()
    try:
        full = (root / relative_path.lstrip("/")).resolve()
        full.relative_to(root)
        return full
    except (ValueError, Exception):
        return None


def make_list_dir_tool(root_path: Path):
    """Build a list_directory tool restricted to root_path."""

    @tool
    def list_directory(
        relative_path: Annotated[str, "Relative path from project root, e.g. 'src' or 'src/agents'"],
    ) -> str:
        """List files and directories at the given path (relative to project root). Use this to explore the codebase."""
        path = _safe_resolve(root_path, relative_path)
        if path is None:
            return "Error: path is outside project root."
        if not path.exists():
            return f"Error: path does not exist: {relative_path}"
        if not path.is_dir():
            return f"Error: not a directory: {relative_path}"
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            lines = [f"{'[dir]  ' if p.is_dir() else '[file] '} {p.name}" for p in entries]
            return "\n".join(lines) if lines else "(empty)"
        except OSError as e:
            return f"Error: {e}"

    return list_directory


def make_read_file_tool(root_path: Path):
    """Build a read_file tool restricted to root_path."""

    @tool
    def read_file(
        relative_path: Annotated[str, "Relative path to file from project root, e.g. 'src/agents/agent1/models.py'"],
        max_lines: Annotated[int | None, "Optional: max lines to read (default all)"] = None,
    ) -> str:
        """Read the contents of a file. Use this to inspect source code for documentation."""
        path = _safe_resolve(root_path, relative_path)
        if path is None:
            return "Error: path is outside project root."
        if not path.exists():
            return f"Error: file not found: {relative_path}"
        if not path.is_file():
            return f"Error: not a file: {relative_path}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if max_lines is not None and max_lines > 0:
                lines = text.splitlines()
                text = "\n".join(lines[: max_lines])
                if len(lines) > max_lines:
                    text += f"\n... ({len(lines) - max_lines} more lines)"
            return text
        except OSError as e:
            return f"Error: {e}"

    return read_file


def make_project_stats_tool(root_path: Path):
    """OF6.8: Count code files for coverage. OF6.7: optional mtime for obsolete detection."""

    @tool
    def project_stats(
        relative_path: Annotated[str, "Directory to scan (e.g. '' or 'src')"] = "",
    ) -> str:
        """Count Python, JS, TS files under the path for documentation coverage. Call this to compute coverage_pct."""
        path = _safe_resolve(root_path, relative_path or ".")
        if path is None:
            return "Error: path is outside project root."
        if not path.exists() or not path.is_dir():
            return f"Error: not a directory: {relative_path or '.'}"
        counts = {"py": 0, "js": 0, "ts": 0, "tsx": 0}
        for ext in counts:
            counts[ext] = len(list(path.rglob(f"*.{ext}")))
        total = sum(counts.values())
        return (
            f"Code files under {relative_path or '.'}: "
            f"Python={counts['py']}, JS={counts['js']}, TS={counts['ts']}, TSX={counts['tsx']}; total={total}"
        )

    return project_stats


def make_file_mtime_tool(root_path: Path):
    """OF6.7: Return file last modified time (for obsolete doc detection)."""

    @tool
    def file_modified_time(
        relative_path: Annotated[str, "Relative path to file from project root"],
    ) -> str:
        """Get last modified time of a file. Use to detect if documentation is older than code (obsolete)."""
        path = _safe_resolve(root_path, relative_path)
        if path is None:
            return "Error: path is outside project root."
        if not path.exists() or not path.is_file():
            return f"Error: not a file: {relative_path}"
        try:
            mtime = path.stat().st_mtime
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime)
            return f"{relative_path}: last modified {dt.isoformat()}"
        except OSError as e:
            return f"Error: {e}"

    return file_modified_time


def get_doc_tools(root_path: Path):
    """Return list of tools for documentation writer: list_directory, read_file, project_stats, file_modified_time."""
    return [
        make_list_dir_tool(root_path),
        make_read_file_tool(root_path),
        make_project_stats_tool(root_path),
        make_file_mtime_tool(root_path),
    ]
