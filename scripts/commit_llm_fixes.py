#!/usr/bin/env python3
"""Commit LLM state management and async fixes."""

import subprocess
import sys

def run(cmd):
    """Run shell command."""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd="/vercel/share/v0-project")
    if result.returncode != 0:
        print(f"Error: command failed with code {result.returncode}")
        sys.exit(1)

# Stage all changes
run("git add -A")

# Commit
commit_msg = """feat: LLM-based state management & async LangGraph integration

- Fix async/await issues in research nodes - all nodes now properly async
- Add LLM-based research intent detection with confidence scoring
- Create LangGraph async nodes for intelligent routing and decisions
- Extend StoryState with 15 fields for LLM decisions and conversation context
- Add router functions for conditional edge routing based on LLM classification
- Enhance greetings to guide toward research-enabled stories
- Rewrite research_nodes.py with proper async/await patterns
- Add comprehensive documentation for state management and LangGraph integration
- Maintain 100% backward compatibility with existing code

Files:
- New: ai/llm_research.py (LLM decision functions)
- New: ai/llm_nodes.py (LangGraph nodes and routers)
- New: LLM_STATE_MANAGEMENT.md (architecture guide)
- New: LANGGRAPH_NODES.md (node quick reference)
- New: FIXES_AND_IMPROVEMENTS.md (summary)
- Modified: ai/research_nodes.py (async rewrite)
- Modified: ai/graph.py (extended state + greetings)

All async operations with proper error handling and graceful fallback."""

run(f'git commit -m "{commit_msg}"')

print("\n✅ Changes committed successfully!")
print("\nCommit summary:")
run("git log --oneline -1")
