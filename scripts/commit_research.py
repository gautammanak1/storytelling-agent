#!/usr/bin/env python3
"""Commit research integration changes to git."""

import subprocess
import sys
import os

os.chdir("/vercel/share/v0-project")

# Stage all research-related files
files_to_stage = [
    "ai/research/websearch.py",
    "ai/research/scraper.py",
    "ai/research/detector.py",
    "ai/research/__init__.py",
    "ai/research_nodes.py",
    "ai/graph.py",
    "ai/handlers.py",
    "ai/story_generator.py",
    ".env.example",
    "README.md",
    "RESEARCH_REQUIREMENTS.md",
    "RESEARCH_INTEGRATION.md",
]

print("[v0] Staging research integration files...")
for file in files_to_stage:
    try:
        subprocess.run(["git", "add", file], check=True, capture_output=True)
        print(f"[v0] Staged: {file}")
    except subprocess.CalledProcessError as e:
        print(f"[v0] Warning: Could not stage {file}: {e}")

print("\n[v0] Committing changes...")
commit_message = """feat: integrate web search and content extraction into storytelling agent

- Added ai/research/ module with websearch, scraper, and detector components
- Integrated DuckDuckGo web search and Trafilatura content extraction
- Extended StoryState with research_query, search_results, scraped_content, research_context fields
- Created research_nodes.py with LangGraph-compatible async nodes for research pipeline
- Added smart detection heuristics to identify research-worthy briefs (companies, products, recent events)
- Injected research context into story generation prompts to ground narratives in facts
- Updated handlers.py to trigger research during brief processing with graceful fallback
- Updated story_generator.py to accept optional research_context parameter
- Added RESEARCH_ENABLED, SEARCH_MAX_RESULTS, SCRAPE_MAX_URLS env var configuration
- Documented research integration in README.md and RESEARCH_INTEGRATION.md
- Maintains full backward compatibility: non-research briefs skip research nodes

Co-authored-by: v0[bot] <v0[bot]@users.noreply.github.com>"""

try:
    result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        check=True,
        capture_output=True,
        text=True
    )
    print("[v0] Commit successful!")
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"[v0] Commit failed: {e.stderr}")
    sys.exit(1)

print("[v0] Research integration committed to git!")
