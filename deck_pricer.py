import csv
import io
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote
import requests

API = 'https://api.scryfall.com'
HEADERS = {'User-Agent': 'PersonalMTGDeckPricer/1.0 (personal deck valuation)', 'Accept': 'application/json'}
PATTERN = re.compile(r'^\s*(\d+)\s+(.+?)(?:\s+\(([A-Za-z0-9]+)\)\s+([A-Za-z0-9★]+))?\s*$')
SECTIONS = {'Commander', 'Deck', 'Sideboard', 'Companion', 'Maybeboard'}

def parse_deck(content):
    cards, section = [], 'Deck'
    for line in content.splitlines():
        line = line.strip().lstrip('\ufeff')
        if not line or line.startswith(('#', '//')):
            continue
        if line in SECTIONS:
            section = line
            continue
        match = PATTERN.match(line)
        if match:
            qty, name, set_code, collector = match.groups()
            cards.append({'section': section, 'qty': int(qty), 'name': name.strip(), 'set': set_code or '', 'collector': collector or ''})
    return cards

def fetch_price(session, card):
    params = None
    if card['set'] and card['collector']:
        url = f"{API}/cards/{quote(card['set'].lower())}/{quote(card['collector'])}"
    else:
        url = f'{API}/cards/named'
        params = {'exact': card['name']}
    try:
        response = session.get(url, params=params, headers=HEADERS, timeout=20)
        if response.status_code == 404 and card['set']:
            response = session.get(f'{API}/cards/named', params={'exact': card['name']}, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
        prices = data.get('prices') or {}
        price = prices.get('usd')
        if price is None:
            return None, 'No nonfoil USD price (digital-only or unavailable)', data.get('scryfall_uri', '')
        return float(price), 'Matched', data.get('scryfall_uri', '')
    except requests.RequestException as exc:
        return None, f'Lookup failed: {exc}', ''

class DeckPricer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MTG Deck Pricer — TCGplayer USD via Scryfall')
        self.geometry('1050x650')
        self.rows = []
        self.path = ''
        self.build_ui()

    def build_ui(self):
        bar = ttk.Frame(self, padding=12)
        bar.pack(fill='x')
        ttk.Button(bar, text='Open deck TXT', command=self.open_file).pack(side='left')
        self.price_btn = ttk.Button(bar, text='Price deck', command=self.start_pricing)
        self.price_btn.pack(side='left', padx=8)
        ttk.Button(bar, text='Export CSV', command=self.export_csv).pack(side='left')
        self.file_label = ttk.Label(bar, text='No deck loaded')
        self.file_label.pack(side='left', padx=15)
        self.summary = ttk.Label(self, text='Load an MTGA deck export to begin.', padding=(12, 5), font=('Arial', 12, 'bold'))
        self.summary.pack(anchor='w')
        cols = ('section', 'qty', 'name', 'set', 'collector', 'unit', 'total', 'status')
        frame = ttk.Frame(self, padding=(12, 6))
        frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(frame, columns=cols, show='headings')
        for col, title, width in zip(cols, ['Section', 'Qty', 'Card', 'Set', 'No.', 'Unit USD', 'Total USD', 'Status'], [90, 45, 250, 65, 55, 90, 100, 280]):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, anchor='w' if col in ('name', 'status', 'section') else 'center')
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.status = ttk.Label(self, text='Prices reflect Scryfall’s latest available TCGplayer USD price; not guaranteed live.', padding=12)
        self.status.pack(anchor='w')

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('Text decks', '*.txt'), ('All files', '*.*')])
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                cards = parse_deck(f.read())
        except Exception as exc:
            messagebox.showerror('Cannot open file', str(exc))
            return
        if not cards:
            messagebox.showwarning('No cards found', 'Expected lines such as: 1 Sheoldred, the Apocalypse (DMU) 107')
            return
        self.path = path
        self.rows = [{**card, 'unit': None, 'total': None, 'status': 'Not priced', 'url': ''} for card in cards]
        self.file_label.config(text=path.split('/')[-1].split('\\')[-1])
        self.render()

    def render(self):
        self.table.delete(*self.table.get_children())
        for card in self.rows:
            self.table.insert('', 'end', values=(card['section'], card['qty'], card['name'], card['set'], card['collector'],
                f"${card['unit']:.2f}" if card['unit'] is not None else '—',
                f"${card['total']:.2f}" if card['total'] is not None else '—', card['status']))
        total = sum(r['total'] or 0 for r in self.rows)
        missing = sum(r['unit'] is None for r in self.rows)
        self.summary.config(text=f"Known value: ${total:,.2f}   |   {sum(r['qty'] for r in self.rows)} cards   |   {missing} lines unpriced")

    def start_pricing(self):
        if not self.rows:
            messagebox.showinfo('Load a deck', 'Open a deck text file first.')
            return
        self.price_btn.config(state='disabled')
        self.status.config(text='Looking up prices…')
        threading.Thread(target=self.price_worker, daemon=True).start()

    def price_worker(self):
        with requests.Session() as session:
            cache = {}
            for idx, card in enumerate(self.rows):
                key = (card['name'], card['set'].lower(), card['collector'])
                if key not in cache:
                    cache[key] = fetch_price(session, card)
                    time.sleep(0.12)
                unit, status, url = cache[key]
                card.update(unit=unit, total=round(unit * card['qty'], 2) if unit is not None else None, status=status, url=url)
                self.after(0, self.render)
                self.after(0, lambda i=idx: self.status.config(text=f'Priced {i+1} of {len(self.rows)} deck entries…'))
        self.after(0, lambda: (self.price_btn.config(state='normal'), self.status.config(text='Finished. Unpriced entries are excluded from the known-value total.')))

    def export_csv(self):
        if not self.rows:
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')], initialfile='deck_prices.csv')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Section', 'Quantity', 'Card', 'Set', 'Collector Number', 'Unit USD', 'Total USD', 'Status', 'Scryfall URL'])
            for r in self.rows:
                writer.writerow([r['section'], r['qty'], r['name'], r['set'], r['collector'], r['unit'] if r['unit'] is not None else '', r['total'] if r['total'] is not None else '', r['status'], r['url']])
        messagebox.showinfo('Saved', f'CSV saved to:\n{path}')

if __name__ == '__main__':
    DeckPricer().mainloop()
