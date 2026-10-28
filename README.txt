MTG DECK PRICER

1. Install Python 3.10+ from python.org (enable Add Python to PATH on Windows).
2. In this folder run: python -m pip install -r requirements.txt
3. Start with: python deck_pricer.py
4. Open a .txt file exported from MTG Arena, click Price deck, then Export CSV.

This tool uses Scryfall's free API to obtain the latest available TCGplayer-linked USD nonfoil price. It does NOT use TCGplayer's live market-price API, which is not open to new developers. Prices may be delayed, and are not firm buy/sell quotes.

When a set/collector-number lookup fails, the tool falls back to the card name. In that case the price may be for a different printing. Digital-only cards, cards without USD nonfoil prices, and failed lookups remain unpriced and are excluded from the known-value total. Foils and conditions are not supported.

An internet connection is required. No credentials or account login are needed.
