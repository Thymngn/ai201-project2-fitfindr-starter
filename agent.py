"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Use the LLM to extract description, size, and max_price from a natural
    language query. Returns a dict with keys: description, size, max_price.
    """
    client = _get_groq_client()
    prompt = (
        "Extract search parameters from this clothing query. "
        "Return JSON with exactly these keys: "
        "description (str), size (str or null), max_price (float or null).\n\n"
        f"Query: {query}\n\n"
        "Examples:\n"
        "'vintage graphic tee under $30' → "
        "{\"description\": \"vintage graphic tee\", \"size\": null, \"max_price\": 30.0}\n"
        "'size M grunge jacket under $50' → "
        "{\"description\": \"grunge jacket\", \"size\": \"M\", \"max_price\": 50.0}\n\n"
        "Return only valid JSON, no explanation."
    )
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()

    # Strip markdown code fences if the LLM wraps the JSON
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query with the LLM
    try:
        session["parsed"] = _parse_query(query)
    except Exception as e:
        session["error"] = f"Couldn't parse your query: {e}"
        return session

    description = session["parsed"].get("description", query)
    size = session["parsed"].get("size")
    max_price = session["parsed"].get("max_price")

    # Step 3: Search listings
    results = search_listings(description, size=size, max_price=max_price)

    # Retry with looser params if no results — raise price 20%, drop size filter
    if not results:
        looser_price = round(max_price * 1.2, 2) if max_price else None
        results = search_listings(description, size=None, max_price=looser_price)

    if not results:
        price_note = f" under ${max_price}" if max_price else ""
        session["error"] = (
            f"No listings found for '{description}'{price_note}. "
            "Try different style keywords."
        )
        return session

    session["search_results"] = results

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 6: Create fit card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
