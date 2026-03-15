r"""MCP prompt templates for memory operations.

Provides pre-built prompts that agents can use to get
structured guidance on how to interact with the memory
system.
"""

from __future__ import annotations

from seeking_context.server import mcp


@mcp.prompt()
def memory_store_prompt(content: str) -> str:
    """Prompt template for storing a new memory.

    Args:
        content: The content to store.

    Returns:
        Formatted instruction for the agent.
    """
    return (
        "You are a memory management assistant. "
        "Analyse the following content and store it "
        "as a memory with appropriate category, "
        "abstract (one-line summary), and overview "
        "(structured summary).\n\n"
        f"Content:\n{content}\n\n"
        "Choose the best category from: profile, "
        "preferences, entities, events, cases, patterns."
    )


@mcp.prompt()
def memory_search_prompt(query: str) -> str:
    """Prompt template for searching memories.

    Args:
        query: The user's search intent.

    Returns:
        Formatted instruction for the agent.
    """
    return (
        "You are a memory retrieval assistant. "
        "Search for memories relevant to the following "
        "query and present the most useful results.\n\n"
        f"Query: {query}\n\n"
        "Return results at the appropriate detail level "
        "(L0 abstract for quick scanning, L1 overview "
        "for context, L2 detail for full content)."
    )


@mcp.prompt()
def session_summary_prompt(session_id: str) -> str:
    """Prompt template for summarising a session.

    Args:
        session_id: The session to summarise.

    Returns:
        Formatted instruction for the agent.
    """
    return (
        "You are a session summariser. Review the "
        f"memories from session {session_id} and "
        "produce:\n"
        "1. A one-line abstract (L0)\n"
        "2. A structured overview (L1) with key topics, "
        "decisions, and action items\n"
        "3. A list of important memories to flag"
    )
