"""Multi-agent film concierge.

A deterministic 4-agent pipeline (preference -> retrieval -> critic -> explainer)
composed from the existing Phase-3 tools (semantic search, recommenders, RAG).
The orchestrator threads one explicit ConciergeState through the agents, records a
per-agent trace, and falls back to the Phase-3 recommender if any agent fails.
"""
