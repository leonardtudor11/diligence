# Frontend asset credits

Third-party visual assets shipped under `frontend/public/`.

## Bull and Bear silhouettes — `public/{bull,bear}.svg`

- **Source**: [Game-icons.net](https://game-icons.net) — `charging-bull` and `bear-head` icons by [Lorc](https://lorcblog.blogspot.com/).
- **Retrieved via**: [Iconify](https://iconify.design) (`api.iconify.design/game-icons:charging-bull.svg`, `api.iconify.design/game-icons:bear-head.svg`).
- **License**: [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) — requires attribution.
- **Modifications**: served as-is from `public/`; recoloured at render time via CSS `mask-image` + `background-color` (see `app/components/BullBearSplit.js`).

## Company brand logos — `public/logos/<TICKER>.svg`

- **Source**: [Simple Icons](https://simpleicons.org) (`nvidia`, `tesla`, `palantir`, `apple`, `microsoft`, `meta`, `amd`, `amazon`, `google`).
- **Retrieved via**: Iconify (`api.iconify.design/simple-icons:<slug>.svg`).
- **License**: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). No attribution required for the icons themselves, but the trademarks remain owned by their respective companies and are used here only for editorial / informational identification of the public-equity tickers covered by the demo.

## Spline 3D robot scene

- **Source**: Spline community scene at `https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode`, the default published by 21st.dev as part of the SplineSceneBasic component pattern.
- **License**: as published on the Spline community page. We embed via the official runtime; no scene file is redistributed in this repo.

## Fonts

- **Orbitron** (display) and **JetBrains Mono** (body) — both OFL-licensed, served via `next/font/google`.
