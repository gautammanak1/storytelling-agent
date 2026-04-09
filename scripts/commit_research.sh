#!/bin/bash
cd /vercel/share/v0-project
git add -A
git commit -m "feat: integrate web search and content extraction with LangGraph

- Add ai/research/ module with websearch.py, scraper.py, detector.py
- Extend StoryState with research_query, search_results, scraped_content, research_context
- Create ai/research_nodes.py with LangGraph nodes for research pipeline
- Integrate research into handlers.py iter_generate_full_story()
- Update story_generator.py to accept and inject research_context into prompts
- Add RESEARCH_ENABLED, SEARCH_MAX_RESULTS, SCRAPE_MAX_URLS env vars
- Update README.md with research feature documentation
- Add RESEARCH_INTEGRATION.md and RESEARCH_REQUIREMENTS.md docs
- Maintain backward compatibility: non-research briefs skip research nodes"
echo "Commit completed successfully"
