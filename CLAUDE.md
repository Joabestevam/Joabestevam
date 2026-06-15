# CLAUDE.md

Guidance for AI assistants (Claude Code and similar tools) working in this repository.

## What this repository is

This is **Joabestevam's GitHub profile repository** (`joabestevam/joabestevam`). A repository
named exactly the same as the GitHub username is special-cased by GitHub: its root `README.md`
is rendered on the user's profile page (https://github.com/Joabestevam).

In addition to the profile README, the repo also hosts a standalone Python project,
`mercado-livre-pricing/` (see below), unrelated to the profile page itself.

## Repository structure

```
.
├── README.md                 # Rendered as the profile page on github.com/Joabestevam
├── CLAUDE.md                  # This file
└── mercado-livre-pricing/     # Standalone Python project (pricing + product research)
    ├── README.md               # Setup and usage instructions for this subproject
    ├── requirements.txt
    ├── .env.example
    ├── config/
    │   └── products.example.json
    ├── data/                    # Generated CSV reports (gitignored content aside, kept via .gitkeep)
    ├── src/
    │   ├── ml_client.py         # Mercado Livre API client (public endpoints + OAuth)
    │   ├── models.py             # Dataclasses: ProductConfig, PriceSuggestion, etc.
    │   ├── pricing_engine.py     # Margin/price math and champion scoring
    │   ├── product_finder.py     # "Produto campeão" discovery logic
    │   └── cli.py                # CLI: price-report, find-champions, apply-prices
    └── tests/
        └── test_pricing_engine.py
```

## mercado-livre-pricing/ subproject

A CLI tool for sellers on Mercado Livre (Brazilian/LatAm marketplace):

- **Price management**: for each configured product, fetches competitor listings via the
  public Mercado Livre search API, computes a minimum-viable price (based on cost + ML fees +
  minimum margin) and a target price (desired margin), and suggests a price per a configurable
  strategy (`match_median`, `beat_lowest`, `premium`). Suggested prices never go below the
  minimum-viable price.
- **Champion product finder**: uses Mercado Livre trending searches (or user-supplied
  keywords) and scores results by `sold_quantity / (1 + competitor_count)` (with a free-shipping
  bonus) to surface high-demand, low-competition products.
- **Optional OAuth**: read-only features (price reports, champion search) work without
  credentials. Updating your own listing prices (`apply-prices --confirm`) requires Mercado
  Livre developer OAuth credentials (`ML_CLIENT_ID`/`ML_CLIENT_SECRET`/tokens in `.env`).

Run from `mercado-livre-pricing/`:
```bash
pip install -r requirements.txt
cp config/products.example.json config/products.json   # edit with real products
python -m src.cli price-report --config config/products.json
python -m src.cli find-champions --top 15
pytest   # unit tests for pricing_engine
```

See `mercado-livre-pricing/README.md` for full setup, OAuth flow, and cron scheduling.

### README.md contents

The README is an HTML-in-Markdown profile page containing:
- A short bio/intro (currently in Portuguese — the owner is a Brazilian student of
  "Análise e Desenvolvimento de Sistemas" / Systems Analysis and Development, interested in
  security analysis and "Técnicas de Invasão" / penetration testing techniques).
- A WakaTime coding-activity badge.
- GitHub stats and top-languages cards via `github-readme-stats.vercel.app`.
- A "Habilidades" (Skills) section using `devicon` icon badges, grouped into:
  - "Estudando e praticando" (Studying/practicing): Python, Linux
  - "Leve contato com" (Familiar with): MySQL, HTML5, CSS3
  - "Interesse em" (Interested in): JavaScript
- A GitHub contribution activity graph via `activity-graph.herokuapp.com`.
- Contact badges (Gmail, LinkedIn, Instagram) at the bottom.

## Development workflow

There is no build, lint, or test process. Changes are simple edits to `README.md`:

1. Edit `README.md` directly — it's a hand-written HTML/Markdown mix, not generated.
2. Preview by checking that Markdown/HTML renders sensibly on GitHub (badges/images are
   external URLs and won't resolve locally).
3. Commit and push.

## Conventions and notes

- **Language**: bio text is in Portuguese (Brazilian). Preserve this unless the user asks for
  translation.
- **External services**: most visual elements (stats cards, language charts, activity graph,
  skill icons, contact badges) are dynamically generated images from third-party services
  (`github-readme-stats.vercel.app`, `activity-graph.herokuapp.com`, `devicon`, `shields.io`,
  `wakatime.com`). When editing these, keep the existing `username=Joabestevam` query
  parameters and badge styles consistent with the rest of the file unless asked to change them.
- **HTML in Markdown**: the file mixes raw HTML (`<div>`, `<kbd>`, `<img>`, `<a>`, `<li>`,
  `<summary>`) with Markdown headings. Some tags are unbalanced/leftover from template editing
  (e.g. stray `</div>` and `##` separators) — be cautious about "fixing" these unless asked, as
  GitHub's renderer is lenient and the visual result is what matters.
- **Adding skills/badges**: follow the existing pattern — a `devicon` SVG `<img>` with
  `align="center" title="..." alt="..." height="30" width="40"` inside the relevant `<kbd>`
  skill group.
- **Links**: the LinkedIn URL in the contact section has a malformed `href`
  (`linkedin.com/inhttps://...`) — fix opportunistically if asked to update contact links, but
  don't change it unprompted as part of unrelated edits.

## When making changes

- Keep edits minimal and scoped to what's requested — this is a personal profile page, not a
  software project, so avoid adding tooling, CI, linters, or scaffolding unless explicitly asked.
- Don't introduce new files (e.g. LICENSE, CI configs, package.json) unless the user requests
  them — the repo is intentionally just a profile README.
