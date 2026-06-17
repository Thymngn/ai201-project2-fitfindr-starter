"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from tools import compare_price, load_style_profile, save_style_profile, get_trending_styles
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:      The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.
    """
    # Guard: empty query → show trending styles instead
    if not user_query or not user_query.strip():
        trends = get_trending_styles()
        if trends:
            lines = ["No query entered. Here are trending styles right now:\n"]
            for t in trends:
                lines.append(f"• {t['name']}: {t['description']}")
                lines.append(f"  Tags: {', '.join(t['style_tags'])}\n")
            return "\n".join(lines), "", ""
        return "Please enter a search query.", "", ""

    # Load saved style profile from previous sessions
    profile = load_style_profile()

    # Select wardrobe
    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    # Run the main agent loop
    session = run_agent(user_query, wardrobe)

    # Surface error in the listing panel
    if session["error"]:
        return session["error"], "", ""

    # Format listing panel — include price comparison verdict
    item = session["selected_item"]
    price_info = compare_price(item)

    listing_text = (
        f"{item['title']}\n"
        f"Price: ${item['price']:.2f}  •  {price_info['verdict'].upper()}\n"
        f"{price_info['message']}\n\n"
        f"Size:      {item['size']}\n"
        f"Condition: {item['condition']}\n"
        f"Colors:    {', '.join(item['colors'])}\n"
        f"Style:     {', '.join(item['style_tags'])}\n"
        f"Platform:  {item['platform']}\n"
    )
    if item.get("brand"):
        listing_text += f"Brand:     {item['brand']}\n"

    # Update and persist style profile with what we learned this session
    profile["style_tags"] = list(
        set(profile.get("style_tags", [])) | set(item.get("style_tags", []))
    )
    if session["parsed"].get("size"):
        profile["size"] = session["parsed"]["size"]
    if session["parsed"].get("max_price"):
        profile["max_price"] = session["parsed"]["max_price"]
    save_style_profile(profile)

    return listing_text, session["outfit_suggestion"], session["fit_card"]


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
