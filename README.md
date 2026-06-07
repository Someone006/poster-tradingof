# SiteForge AI Website Builder

This folder contains **SiteForge**, a local browser tool that creates responsive website drafts from a prompt.

Open `index.html` in a browser, or run the local server:

```powershell
node dev-server.mjs
```

Then visit `http://localhost:8000`.

SiteForge includes:

- Prompt-driven website generation
- Brand inference and optional brand override
- Multiple site types, styles, goals, and section combinations
- Safe HTML escaping for prompt text
- Live preview plus HTML, CSS, and full-site output
- Download buttons for generated files
- A built-in 100 hard quote stress test panel

The generator runs locally with a deterministic AI-style engine. It does not call an external AI API yet, but the core is isolated in `siteforge-core.js` so a real model endpoint can be connected later.

## Legal pages for TikTok review

This folder also includes simple legal pages for the poster tradingof app:

- `terms.html`
- `privacy.html`
- `legal.css`

The public contact email used in both legal pages is `tradingof.tiktok@gmail.com`.

Free 24/7 hosting options:

1. GitHub Pages: create a public GitHub repository, upload these files, then enable Pages from the repository settings. Use the published URLs for TikTok, for example `https://your-user.github.io/your-repo/terms.html` and `https://your-user.github.io/your-repo/privacy.html`.
2. Cloudflare Pages: connect a GitHub repository or upload the folder directly, then use the generated `pages.dev` URLs for TikTok.
3. Netlify: drag and drop the folder into Netlify Drop, then use the generated Netlify URLs.
