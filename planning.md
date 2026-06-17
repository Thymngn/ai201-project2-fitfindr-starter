# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
It looks into listing.json and determine top 3 matches based on relevance using description and style_tag.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): It describes the outfit style and outfit.
- `size` (str): It describes the sizing of the piece the yser is looking for 
- `max_price` (float): How much user willing to spend for that one item

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
return a list of ldictionary where it shows id, title, description, category, style_tags (list), size, condition, price (float), colors (list), brand, platform for each item.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
It asks the user to do an alternative search and a message of no finding.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Use the return list of dictionary from search_listings. It combine the top relevance and return a description on how to style this.
**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): it represent the item that is return from the search function. 
- `wardrobe` (dict): display the current outfit in the wardrobe

**What it returns:**
<!-- Describe the return value -->
"Show a list of outfit" — the spec should say what shape comes back (e.g., a list of dicts, each with items, styling_tip, etc.)

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
Give a message to user that the new item and wardrobe doesn't looks good. Suggest to find a different item or add more to the wardrobe.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
It save fit outfit so user can comeback when they need an idea what to wear.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (dict): the outfit in the wardrobe
- `newitem` (dict): return from search.

**What it returns:**
<!-- Describe the return value -->
a list of dictionary of all the outfit together.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
tell the user the card couldn't be saved and ask them to confirm the outfit

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
It will follow in order, first search_listing. Before using suggest_outfit, there must be a return value from search_listing. Next up, is create_fit_card where the user save their newly found outfit idea to the card.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

state = {
    "wardrobe": load_wardrobe(),   # loaded once from file at startup, never mutated
    "search_results": [],           # appended to on each new search, never overwritten
    "selected_item": None,          # set when user picks an item from search_results
    "suggested_outfits": [],        # set by suggest_outfit, replaced each call
    "fit_cards": []                 # grows as user saves looks via create_fit_card
}

- wardrobe is read-only after startup — suggest_outfit reads it but never modifies it.
- search_results accumulates across searches so the user can reference earlier finds.
- selected_item is updated whenever the user picks a listing to style.
- suggest_outfit overwrites suggested_outfits on each new call since it's always based on the current selected_item.
- create_fit_card appends to fit_cards — saves persist for the whole session.
---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.


┌─────────────────┬─────────────────┬───────────────────────────────────────────────────┐
│      Tool       │  Failure mode   │                  Agent response                   │
├─────────────────┼─────────────────┼───────────────────────────────────────────────────┤
│                 │                 │ Tell the user no matches were found and echo back │
│ search_listings │ No results      │  what was searched. Suggest broadening the search │
│                 │ match the query │  — raise max_price, try different style keywords, │
│                 │                 │  or remove the size filter.                       │
├─────────────────┼─────────────────┼───────────────────────────────────────────────────┤
│                 │ Wardrobe is     │ Tell the user outfit suggestions need wardrobe    │
│ suggest_outfit  │ empty           │ items to work with. Prompt them to add at least   │
│                 │                 │ one item to their wardrobe and try again.         │
├─────────────────┼─────────────────┼───────────────────────────────────────────────────┤
│                 │ No matching     │ Tell the user the item doesn't pair well with     │
│ suggest_outfit  │ style tags with │ their current wardrobe. Suggest going back to     │
│                 │ wardrobe        │ search_listings to find a better match.           │
├─────────────────┼─────────────────┼───────────────────────────────────────────────────┤
│                 │ Outfit input is │ Tell the user the fit card couldn't be saved.     │
│ create_fit_card │  missing or     │ Identify which field is missing (selected_item or │
│                 │ incomplete      │  suggested_outfits) and ask them to confirm the   │
│                 │                 │ outfit before retrying.                           │
└─────────────────┴─────────────────┴───────────────────────────────────────────────────┘

---

## Architecture

```
  ┌─────────────────┐
  │   User Input    │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Planning Loop  │
  └────────┬────────┘
           │
           │ 1. search request
           ▼
  ┌─────────────────┐   no match   ┌──────────────────┐
  │ search_listings │─────────────►│  retry looser    │
  └────────┬────────┘              └────────┬─────────┘
           │ match found                    │ still fails
           ▼                               ▼
  ┌─────────────────┐            ┌──────────────────────┐
  │  search_history │            │ tell user: try new   │
  │  (state, cap 10)│            │ keywords             │
  └────────┬────────┘            └──────────────────────┘
           │ user picks item
           ▼
  ┌─────────────────┐
  │  selected_item  │
  │    (state)      │
  └────────┬────────┘
           │
           │ 2. style request
           ▼
  ┌─────────────────┐◄──────────────────────────────────────┐
  │  suggest_outfit │          ┌───────────────────────────┐ │
  └────────┬────────┘          │ wardrobe (read-only)      │─┘
           │ success           └───────────────────────────┘
           │              wardrobe empty ──► tell user: add items
           │              no style match ──► tell user: go back to search
           ▼
  ┌─────────────────┐
  │suggested_outfits│
  │    (state)      │
  └────────┬────────┘
           │
           │ 3. save request
           ▼
  ┌─────────────────┐  missing data  ┌───────────────────────┐
  │ create_fit_card │───────────────►│ tell user: confirm    │
  └────────┬────────┘                │ outfit before retrying│
           │ saved                   └───────────────────────┘
           ▼
  ┌─────────────────┐
  │    fit_cards    │
  │    (state)      │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ show fit card   │
  │   to user       │
  └─────────────────┘
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
search_listings: Give Claude the Tool 1 spec (inputs, return value, failure mode) and the listings.json structure. Ask it to implement search_listings() that scores items by matching style_tags against description keywords, filters by size and max_price, and returns the top 3. Verify by running 3 test queries — "vintage graphic tee under $30", "grunge boots size 8", and a query with no matches — and confirm the results and retry behavior match the spec.

suggest_outfit: Give Claude the Tool 2 spec and the wardrobe_schema.json structure. Ask it to implement suggest_outfit() that matches style_tags between new_item and wardrobe items and returns outfit combos with a styling tip. Verify with lst_006 + the example wardrobe (should return at least one combo), then test with an empty wardrobe to confirm the error message triggers.

create_fit_card: Give Claude the Tool 3 spec. Ask it to implement create_fit_card() that builds a fit card dict from outfit + new_item and appends it to state["fit_cards"]. Verify by calling it with a valid outfit and checking fit_cards grows, then call it with a missing field to confirm the error response.

**Milestone 4 — Planning loop and state management:**
Give Claude the Planning Loop section, State Management section, and the Architecture diagram. Ask it to implement the main agent loop that initializes state from wardrobe_schema.json at startup, routes user input to the correct tool, and passes state between calls. Verify by running the full example interaction from the Complete Interaction section end-to-end and checking that search_history, selected_item, suggested_outfits, and fit_cards each update correctly at the right step.

---
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
Agent parses the query and calls search_listings:
- description: "vintage graphic tee"
- size: not specified (omitted)
- max_price: 30.0

Returns top 3 matches under $30 with matching style tags:
1. lst_006 — Graphic Tee, 2003 Tour Bootleg Style ($24, black, size L)
2. lst_033 — Vintage Band Tee, Faded Grey ($19, grey, size L)
3. lst_002 — Y2K Baby Tee, Butterfly Print ($18, white/pink, size S/M)

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Agent presents the 3 results. User picks lst_006. selected_item is updated. Agent calls suggest_outfit:

- new_item: lst_006 (black graphic tee, style_tags: graphic tee, vintage, grunge, streetwear)
- wardrobe: loaded from wardrobe_schema.json

Matches style_tags with wardrobe — returns outfit combo:
- Baggy straight-leg dark wash jeans (w_001) + chunky white sneakers (w_007) + graphic tee → classic streetwear look
- Optional layer: vintage black denim jacket (w_006)

Result stored in suggested_outfits.

**Step 3:**
<!-- Continue until the full interaction is complete -->
User wants to save the look. Agent calls create_fit_card:
- outfit: baggy jeans + chunky sneakers + optional denim jacket
- new_item: lst_006

Fit card appended to fit_cards.

**Final output to user:**
<!-- What does the user actually see at the end? -->
Here's your fit card:
"2003 Bootleg Tee Look"
- Graphic Tee — 2003 Tour Bootleg Style ($24, Depop)
- Baggy straight-leg dark wash jeans
- Chunky white sneakers
- Layer option: Vintage black denim jacket
▎
Saved to your fit cards.
