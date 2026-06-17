# FitFindr

FitFindr is an AI-powered thrift shopping agent. You describe what you're looking for, it searches a secondhand listings dataset, suggests how to style the find with your existing wardrobe, and generates a shareable fit card. It also evaluates whether the price is fair, surfaces trending styles, and remembers your preferences across sessions.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run the agent directly from the terminal:

```bash
python agent.py
```

Run tests:

```bash
python -m pytest tests/test_tools.py -v
```

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   ├── wardrobe_schema.json   # Wardrobe format + example wardrobe
│   └── style_profile.json     # Saved user preferences (auto-created)
├── utils/
│   └── data_loader.py         # Helper functions for loading data
├── tests/
│   └── test_tools.py          # Unit tests for search_listings
├── tools.py                   # All tool implementations
├── agent.py                   # Planning loop
├── app.py                     # Gradio UI
└── planning.md                # Design spec
```

---

## Tool Inventory

### `search_listings`
**Purpose:** Searches the listings dataset for items matching the user's description, size, and price ceiling. Returns the top 3 results scored by keyword relevance.

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Keywords describing the item (e.g. "vintage graphic tee") |
| `size` | `str \| None` | Size to filter by — case-insensitive, partial match (e.g. "M" matches "S/M") |
| `max_price` | `float \| None` | Maximum price inclusive; `None` skips price filtering |

**Returns:** `list[dict]` — up to 3 listing dicts, each with `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never raises.

---

### `suggest_outfit`
**Purpose:** Uses the Groq LLM to suggest 1–2 outfit combinations pairing the new item with pieces from the user's wardrobe.

| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` |
| `wardrobe` | `dict` | Wardrobe dict with an `items` key (list of wardrobe item dicts) |

**Returns:** `str` — outfit suggestions from the LLM. If wardrobe is empty, returns general styling advice instead. If there's no style tag overlap between the item and wardrobe, returns a message directing the user back to search.

---

### `create_fit_card`
**Purpose:** Uses the Groq LLM to write a 2–4 sentence Instagram/TikTok-style caption for the outfit.

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Returns:** `str` — a casual OOTD caption mentioning item name, price, and platform. If `outfit` is empty, returns an error string without raising.

---

### `compare_price` *(stretch)*
**Purpose:** Evaluates whether an item's price is fair by comparing it to similar listings in the dataset (same category, at least one shared style tag).

| Parameter | Type | Description |
|---|---|---|
| `item` | `dict` | A listing dict to evaluate |

**Returns:** `dict` with keys:
- `verdict` — `"good deal"`, `"fair"`, `"overpriced"`, or `"unknown"`
- `avg_comparable_price` — `float | None`
- `comparable_count` — `int`
- `message` — human-readable summary string

---

### `get_trending_styles` *(stretch)*
**Purpose:** Uses the Groq LLM as a trend oracle to surface 5 currently trending thrift/secondhand styles. In production this would call a real fashion platform API.

| Parameter | Type | Description |
|---|---|---|
| `size` | `str \| None` | Optional size to filter trends by |
| `category` | `str \| None` | Optional category to focus on |

**Returns:** `list[dict]` — up to 5 trend dicts each with `name`, `description`, `style_tags`, `example_items`. Returns `[]` if the LLM response can't be parsed.

---

### `load_style_profile` *(stretch)*
**Purpose:** Loads the user's saved style preferences from `data/style_profile.json` so they carry over between sessions.

**Parameters:** none

**Returns:** `dict` with keys `style_tags` (list), `size` (str | None), `max_price` (float | None). Returns a default empty profile if no file exists yet.

---

### `save_style_profile` *(stretch)*
**Purpose:** Persists the user's style preferences to `data/style_profile.json` at the end of each successful session.

| Parameter | Type | Description |
|---|---|---|
| `profile` | `dict` | Profile dict with `style_tags`, `size`, `max_price` |

**Returns:** `str` — confirmation message.

---

## Planning Loop

The agent runs a fixed sequence of steps for each query, with two optional branches:

1. **Startup** — `load_style_profile` restores preferences from the last session.
2. **Trend branch** — if the query is empty, `get_trending_styles` runs and the results are shown in the listing panel instead of an error.
3. **Parse** — the LLM extracts `description`, `size`, and `max_price` from the natural language query.
4. **Search** — `search_listings` runs with the parsed parameters. If no results, it retries with price raised 20% and size filter dropped. If still empty, the session ends with an error message.
5. **Price check** — `compare_price` runs automatically on the top result.
6. **Style** — `suggest_outfit` pairs the selected item with the wardrobe.
7. **Save** — `create_fit_card` generates the caption.
8. **Shutdown** — `save_style_profile` merges the session's learned tags, size, and price range into the saved profile.

The loop never proceeds to `suggest_outfit` with an empty `selected_item`, and never calls `create_fit_card` with an empty outfit string.

---

## State Management

All state for a single session lives in one dict initialized by `_new_session()` in `agent.py`:

```python
{
    "query":             str,        # original user input
    "parsed":            dict,       # LLM-extracted description / size / max_price
    "search_results":    list[dict], # all matching listings from this run
    "selected_item":     dict,       # top result; input to suggest_outfit
    "wardrobe":          dict,       # loaded from wardrobe_schema.json, read-only
    "outfit_suggestion": str,        # output of suggest_outfit
    "fit_card":          str,        # output of create_fit_card
    "error":             str | None, # set on early termination
}
```

Cross-session state is handled separately by `load_style_profile` / `save_style_profile`, which read and write `data/style_profile.json`. The profile accumulates style tags, size, and price range across runs — it is never reset by the session dict.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No results on first try | Retry with `max_price * 1.2` and size filter dropped |
| `search_listings` | No results after retry | Set `session["error"]`; surface message in listing panel |
| `suggest_outfit` | Wardrobe is empty | LLM gives general styling advice instead of specific combos |
| `suggest_outfit` | No style tag overlap with wardrobe | Returns a message directing user back to `search_listings` |
| `create_fit_card` | `outfit` string is empty | Returns an error string; does not raise |
| `compare_price` | No comparable listings found | Returns `verdict: "unknown"` with explanation; flow continues |
| `get_trending_styles` | LLM returns invalid JSON | Returns `[]`; listing panel shows a fallback message |
| `load_style_profile` | File missing or corrupted | Returns default empty profile; never crashes |

**Concrete example — retry path:**
Query `"designer ballgown size XXS under $5"` returns no results on the first pass (nothing under $5). The retry raises the ceiling to $6 and drops the size filter — still no results. The agent sets `session["error"] = "No listings found for 'designer ballgown' under $5.0. Try different style keywords."` and the listing panel shows that message with the other two panels empty.

**Concrete example — no style overlap:**
Searching `"leather bomber jacket 90s"` returns lst_022 (style tags: `90s`, `vintage`, `leather`, `classic`, `grunge`). If the wardrobe contained only `cottagecore` and `linen` pieces, `suggest_outfit` would return: *"This item doesn't pair well with your current wardrobe — there's no style overlap. Try going back to search_listings to find a better match."*

---

## Spec Reflection

**What matched the spec:**
The three required tools (`search_listings`, `suggest_outfit`, `create_fit_card`) were implemented exactly as described in planning.md — same parameter names, same return shapes, same failure modes. The planning loop follows the 1→2→3→4 sequence from the architecture diagram. The retry logic (raise price 20%, drop size) matches the error handling spec.

**What changed during implementation:**
- `suggest_outfit` was originally specced to return a `list[dict]` of outfit combos, but the starter code defined it as returning a `str`. The LLM response is naturally a string, so we kept `str` and the spec was updated to match.
- The state dict in planning.md used `search_history` with a cap of 10. The starter code's `_new_session()` used `search_results` (single-run only). We followed the starter code's structure to keep agent.py compatible with the existing CLI test harness.
- `compare_price` was added as a stretch feature after the core tools were working. It runs automatically on every result rather than being a user-triggered step, which wasn't in the original spec but makes the UX cleaner.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

**Input to Claude:** The Tool 1 spec from planning.md (parameters: `description`, `size`, `max_price`; return value: list of listing dicts with all fields; failure mode: empty list, no exception), plus the `load_listings()` function signature from `utils/data_loader.py`, and the instruction to score by keyword overlap between the description and `style_tags`.

**What it produced:** A working implementation that filters by price and size, then scores each listing by counting keyword matches in `style_tags` (weighted 2×) and title words. Returns the top 3 by score.

**What I changed:** The initial version only checked `style_tags` for keyword overlap and missed title-word matches entirely (e.g. searching "tee" wouldn't match a listing titled "Graphic Tee" if "tee" wasn't in the style tags). I added the `title_words` match alongside `tag_matches` to fix this.

---

### Instance 2 — Implementing the planning loop in `agent.py`

**Input to Claude:** The Planning Loop section of planning.md (step order: parse → search → retry → select → suggest → save), the State Management section (session dict structure), and the Architecture ASCII diagram showing the retry branch and error paths.

**What it produced:** A complete `run_agent()` function with `_parse_query()` using the LLM to extract JSON parameters, the retry logic raising price 20% and dropping size, and sequential calls through all three tools.

**What I changed:** The initial draft used `json.loads()` directly on the LLM response and crashed when the model wrapped the JSON in markdown code fences (` ```json ... ``` `). I added a stripping step to remove the fences before parsing — a pattern I reused in `get_trending_styles` for the same reason. I also moved the Groq client initialization into a shared `_get_groq_client()` helper rather than duplicating it in every function.
