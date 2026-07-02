# Publishing the post to Medium — step by step

Medium has **no markdown support and no native tables** (pasting raw markdown leaves literal
`##` and `**`; pasted tables flatten to text). Its API is closed to new integrations
(Jan 2025) and the Import tool is unreliable. The workflow that reliably works is
**paste rendered rich text, then add the tables as images**. Everything below is
research-verified against Medium's current help docs (2025–2026).

## 1. Paste the article (2 minutes)

1. Open [`medium-post-paste.html`](medium-post-paste.html) in your browser
   (double-click the file).
2. Select all (**Cmd+A**), copy (**Cmd+C**).
3. In a new Medium story, paste (**Cmd+V**). Headings, bold, italic, links,
   the blockquote and paragraphs all survive the paste.
4. Check the two top lines: the first line should render as the **Title**
   (big-T) and the second as the **Subtitle** (small-t, gray). If the subtitle
   pasted as ordinary text, select it → popup toolbar → small **t**.

## 2. Insert the two table images

Medium's own recommendation for dense tables: upload wide, use the *outset* size.
Both PNGs are 2200 px wide (Medium wants ≥1400 px) and designed on white so they
blend into the page.

1. At the first yellow marker line under **Head-to-head**: put the cursor on an
   empty line → **⊕** menu → image → upload
   [`images/post/table-1-head-to-head.png`](images/post/table-1-head-to-head.png).
2. Click the image → choose the **second size option (outset)** so the table gets
   extra width. Readers can also click the image to zoom to full resolution.
3. Optional caption (click the image and type):
   *"The supervisor and blackboard patterns compared attribute by attribute."*
4. Repeat under **Where each pattern fits** with
   [`images/post/table-2-industry-fit.png`](images/post/table-2-industry-fit.png).
   Optional caption: *"Same institution, different work shapes — the pattern follows the work."*
5. **Delete the yellow marker lines.**

## 3. Beautify (1 minute, in the editor)

- **Pull quote**: select the final quote ("Model choices change quarterly…") →
  click the quote icon **twice** (once = blockquote, twice = large pull quote).
- **Section separators**: press **Cmd+Enter** on an empty line before
  *Head-to-head* and before *What I advise in practice* — this inserts Medium's
  ••• divider between the major parts.
- **Cover image**: Medium uses the **first image** in the story for the feed
  card and social shares. Since the first image here is a table, either accept
  that, or add a title card at the top (I can generate one matching the title
  on request). You can also pick the featured image in the Story Preview
  settings behind the Publish button.

## 4. Publish settings

- **Tags** (up to 5): `AI Agents`, `Multi-Agent Systems`, `Enterprise AI`,
  `Software Architecture`, `Generative AI`.
- **Display title/subtitle** for the story card: the `…` menu →
  *Change display title/subtitle* if you want a shorter card title than the
  full SEO title.

## Alternatives (if you prefer)

| Approach | Verdict |
|---|---|
| Paste rendered HTML (this guide) | ✅ Most reliable; everything except tables survives |
| Tables as images | ✅ Medium's own "best for keeping formatting" option; not copyable/searchable text |
| [markdown-to-medium.surge.sh](https://markdown-to-medium.surge.sh/) | ✅ Works (paste `medium-post.md` into it) — but tables still need the image treatment |
| Google Sheets / Datawrapper link-embed for tables | ⚠️ Renders a live embed card; interactive only after publish; look depends on the external service |
| GitHub Gist embed (.csv renders as a table) | ⚠️ Works but undocumented behavior; may break if Medium changes gist embedding |
| Medium "Import a story" from a URL | ⚠️ Exists but error-prone (fails behind Cloudflare; mangles headings/code) |
| Medium API / CLI tools (mdium, Ulysses, Obsidian) | ❌ Closed to new integration tokens since Jan 2025 |

Canonical article source: [`medium-post.md`](medium-post.md) (markdown, renders on GitHub).
