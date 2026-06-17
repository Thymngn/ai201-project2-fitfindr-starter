"""
tools.py

FitFindr tools — three required + three stretch features.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str

Stretch:
    compare_price(item)                            → dict
    load_style_profile()                           → dict
    save_style_profile(profile)                    → str
    get_trending_styles(size, category)            → list[dict]
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of up to 3 matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Step 1: filter by price and size
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.lower() not in item["size"].lower():
            continue
        candidates.append(item)

    # Step 2: score by keyword overlap — style_tags weighted 2x over title words
    keywords = set(description.lower().split())
    scored = []
    for item in candidates:
        tag_matches = len(keywords & {tag.lower() for tag in item["style_tags"]})
        title_matches = len(keywords & set(item["title"].lower().split()))
        score = tag_matches * 2 + title_matches
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:3]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions or an error message.
        Never raises an exception.
    """
    client = _get_groq_client()
    wardrobe_items = wardrobe.get("items", [])

    # Empty wardrobe: give general styling advice
    if not wardrobe_items:
        prompt = (
            f"A user is considering buying this thrifted item:\n"
            f"- {new_item['title']} (${new_item['price']}, style: {', '.join(new_item['style_tags'])})\n\n"
            f"Their wardrobe is empty. Give general styling advice — what kinds of pieces "
            f"pair well with it, what aesthetic it suits, and how to build an outfit around it."
        )
    else:
        # Check for style tag overlap between new item and wardrobe
        new_tags = {tag.lower() for tag in new_item.get("style_tags", [])}
        wardrobe_tags = {
            tag.lower()
            for item in wardrobe_items
            for tag in item.get("style_tags", [])
        }

        if not new_tags & wardrobe_tags:
            return (
                f"'{new_item['title']}' doesn't pair well with your current wardrobe — "
                f"there's no style overlap. Try going back to search for something that "
                f"matches your existing pieces better."
            )

        wardrobe_text = "\n".join(
            f"- {item['name']} ({item['category']}, tags: {', '.join(item['style_tags'])})"
            for item in wardrobe_items
        )
        prompt = (
            f"A user is considering buying this thrifted item:\n"
            f"- {new_item['title']} (${new_item['price']}, style: {', '.join(new_item['style_tags'])})\n\n"
            f"Their current wardrobe:\n{wardrobe_text}\n\n"
            f"Suggest 1-2 specific outfit combinations using the new item and named pieces "
            f"from their wardrobe. Be specific about which wardrobe pieces to pair it with "
            f"and describe the overall look and vibe."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return (
            "Couldn't create a fit card — outfit suggestion is missing. "
            "Try running suggest_outfit first."
        )

    client = _get_groq_client()
    prompt = (
        f"Write a 2-4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Thrifted item: {new_item['title']} — ${new_item['price']} on {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        f"The caption should:\n"
        f"- Sound casual and authentic like a real OOTD post, not a product description\n"
        f"- Mention the item name, price, and platform naturally (once each)\n"
        f"- Capture the outfit vibe in specific terms\n"
        f"- Feel unique and personal"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
    )
    return response.choices[0].message.content


# ── Stretch Tool 4: compare_price ─────────────────────────────────────────────

def compare_price(item: dict) -> dict:
    """
    Estimate whether an item's price is fair by comparing it to similar listings.

    Args:
        item: A listing dict (e.g., from search_listings).

    Returns:
        A dict with:
            verdict (str):               "good deal", "fair", "overpriced", or "unknown"
            avg_comparable_price (float): average price of comparable items, or None
            comparable_count (int):       number of comparables found
            message (str):               human-readable summary
    """
    listings = load_listings()

    item_category = item.get("category")
    item_tags = {tag.lower() for tag in item.get("style_tags", [])}
    item_price = item.get("price", 0)

    comparables = [
        l for l in listings
        if l["id"] != item["id"]
        and l["category"] == item_category
        and {tag.lower() for tag in l.get("style_tags", [])} & item_tags
    ]

    if not comparables:
        return {
            "verdict": "unknown",
            "avg_comparable_price": None,
            "comparable_count": 0,
            "message": "Not enough comparable listings to evaluate this price.",
        }

    avg_price = sum(l["price"] for l in comparables) / len(comparables)

    if item_price <= avg_price * 0.8:
        verdict = "good deal"
    elif item_price <= avg_price * 1.1:
        verdict = "fair"
    else:
        verdict = "overpriced"

    return {
        "verdict": verdict,
        "avg_comparable_price": round(avg_price, 2),
        "comparable_count": len(comparables),
        "message": (
            f"${item_price:.2f} vs. avg ${avg_price:.2f} across "
            f"{len(comparables)} comparable listing(s) — {verdict}."
        ),
    }


# ── Stretch: Style profile memory ─────────────────────────────────────────────

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "data", "style_profile.json")

_DEFAULT_PROFILE = {
    "style_tags": [],
    "size": None,
    "max_price": None,
}


def load_style_profile() -> dict:
    """
    Load the user's saved style profile from disk.
    Returns the default empty profile if no file exists or the file is unreadable.
    """
    if not os.path.exists(_PROFILE_PATH):
        return _DEFAULT_PROFILE.copy()
    try:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_PROFILE.copy()


def save_style_profile(profile: dict) -> str:
    """
    Save the user's style profile to disk.

    Args:
        profile: dict with keys: style_tags (list), size (str|None), max_price (float|None)

    Returns:
        A confirmation string.
    """
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    return "Style profile saved."


# ── Stretch Tool 5: get_trending_styles ───────────────────────────────────────

def get_trending_styles(
    size: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Surface currently trending thrift/secondhand styles using the LLM.
    In production this would call a real fashion platform API.

    Args:
        size:     Optional size to filter trends by (e.g., "M", "L").
        category: Optional category to focus on (e.g., "tops", "outerwear").

    Returns:
        A list of up to 5 trend dicts, each with:
            name (str), description (str), style_tags (list), example_items (list)
        Returns an empty list if the LLM response cannot be parsed.
    """
    client = _get_groq_client()

    size_note = f" for size {size}" if size else ""
    category_note = f" in the {category} category" if category else ""

    prompt = (
        f"You are a fashion trend expert. List 5 currently trending secondhand/thrift styles"
        f"{size_note}{category_note}. "
        f"For each trend return a JSON object with: "
        f"name (str), description (str), style_tags (list of 3-5 tags), "
        f"example_items (list of 2 example clothing pieces).\n\n"
        f"Return a JSON array of 5 objects. No explanation, just valid JSON."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    text = response.choices[0].message.content.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return []
