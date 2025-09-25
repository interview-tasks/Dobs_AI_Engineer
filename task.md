# Option 1: **Search Price from Large PDF**

**Goal**

Build a search tool that takes one **free-form line** and returns the **base list rate (USD)** from the official FedEx 2025 PDF. 

> **One input → one price.**
> 

**Data Source (single source of truth)**

**FedEx Standard List Rates 2025 (PDF):** https://www.fedex.com/content/dam/fedex/us-united-states/services/FedEx_Standard_List_Rates_2025.pdf

---

## **What you build (in 3-6 hours)**

- A function: get_price(line: str) -> Decimal|float
- A minimal way to demo it: CLI, HTTP endpoint (POST /price with { line }), or a one-field web UI.

---

## **Input (free text, one line)**

Examples we’ll send (order/synonyms vary):

- FedEx 2Day, Zone 5, 3 lb
- Standard Overnight, z2, 10 lbs, other packaging
- Express Saver Z8 1 lb
- Ground Z6 12 lb
- Home Delivery zone 3 5 lb

**Assumptions**

- **Zone is given** (no ZIP→zone lookup).
- **Weight is in pounds**; always **round up** to next whole lb.
- Handle common service synonyms: First Overnight, Priority Overnight, Standard Overnight, 2Day, 2Day AM, Express Saver, Ground, Home Delivery.
- Accept Zone 5 / Z5 / 5, lb / lbs, any case.

---

## **Requirements**

- **Prices must come from the PDF tables.** You may parse/copy to CSV/SQLite for speed.
- **No external tariff APIs.**
- **Deterministic**: same input ⇒ same output.
- **No hardcoding per sample strings.**
- Return **base list rate only** (no surcharges, minimums, discounts).

---

---

## **Deliverables**

1. **Repo link** with one-step run (make run, docker run, or similar).
2. **README** (short): solution architecture, how you parsed the PDF, stored the data and find the answear.
3. **Demo**: show 5–7 lines (incl. ours).

## **(use or completely ignore…)**

- Fast path: extract tables → CSV/SQLite → LLM (service, zone, ceil(weight)).
- Use an LLM only to normalize the input line; never to “guess” prices.