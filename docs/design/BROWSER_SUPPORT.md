# Browser Support

## Targets

- **Chromium** (Chrome, Edge): last 2 versions.
- **Firefox:** last 2 versions.
- **Safari:** last 2 versions.
- **No** IE11, **no** Edge Legacy.

The report is one self-contained `file://`-openable HTML document; "support" means
it renders and reads correctly when double-clicked from disk, opened from an email
attachment, or served statically — with **no build step** in Component 17.

## CSS features we use, and why each is safe

| Feature | Decision | Rationale |
|---------|----------|-----------|
| Custom properties | Use freely | Universally supported across all target versions; the theming backbone. |
| Grid & Flexbox | Use freely | Stable everywhere in scope; the whole layout rests on them. |
| `:is()` / `:has()` | Use, with fallback | `:has()` shipped in all targets' last 2 versions, but a plain-selector fallback must keep layout intact if a stale build lacks it. |
| CSS nesting | Use, with flat fallback authorable | Supported in current targets; since there is no build step, nesting must be hand-flattened anywhere a last-2 edge case slips. |
| Container queries | Use **only** with a media-query fallback | Newest of the set; layout must not depend on it alone. |

## JS features we use

- **ES2022** language features and standard DOM APIs only.
- **No build step** — Component 17 ships JS that runs directly in the browser.
- All JS is enhancement; the report reads with JS fully disabled
  (`FIRST_PAINT.md`).

## Banned — with the reason for each

| Banned | One-sentence why |
|--------|------------------|
| Web Components / custom elements | A single static report needs no component runtime; they add lifecycle complexity and a no-JS blank-element failure mode for zero benefit. |
| `localStorage` / `IndexedDB` | One document holds its own state in the DOM; persistence would also break under `file://` sandboxing and leak state between unrelated reports. |
| Web fonts from a CDN | Any remote fetch breaks the self-contained, offline guarantee and leaks a request when the report is opened. |
| **Any** external HTTP request | A report opened from email or disk must never phone home — for privacy, for offline use, and so a proxy can't make it render differently. |
| Service workers | Pointless and disallowed for a `file://` document; implies caching/lifecycle a single file must not have. |

## Fallback policy

Where a feature is "use with fallback," the fallback is the **default authored
path** and the modern feature is the progressive layer — never the reverse. A
browser at the older edge of "last 2 versions" must get a fully readable,
correctly-laid-out report, only without the newest visual refinement.
