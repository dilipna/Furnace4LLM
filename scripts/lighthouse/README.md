# Locked existing audit tool

CI already used Lighthouse 13.0.1. Ad-hoc `pnpm dlx` resolution failed on November
25 when tldts-icann 7.5.6 required a tldts-core release unavailable in the registry.
This directory freezes the existing tool and published matching 7.5.5 pair.
Its separate dependency graph avoids changing Next's optional OpenTelemetry peers.
Nothing here is a product runtime dependency or a new browser download.

```powershell
pnpm --dir scripts/lighthouse install --frozen-lockfile --ignore-scripts
pnpm --dir scripts/lighthouse exec lighthouse --version
$env:CHROME_PATH = 'C:\path\to\chrome.exe'
pnpm --dir scripts/lighthouse exec lighthouse http://127.0.0.1:4011 --only-categories=performance,accessibility,seo '--chrome-flags=--headless=new --no-sandbox --disable-gpu' --output=json --output-path=../../dist/lighthouse.json --quiet
uv run python scripts/check_lighthouse.py dist/lighthouse.json
```

Use an existing local browser and the existing preview server. The relative output
path deliberately resolves from this tool directory to the repository's dist folder.
Version 13.0.1 and the >=90 acceptance rule for every category are unchanged.
Offline installation requires a populated pnpm cache; it is not clean-machine setup.

Original failed runs (no audit score was produced):

- [#19 Windows run45585393163](https://github.com/dilipna/Furnace4LLM/actions/runs/45585393163)
- [#20 Windows run45585523564](https://github.com/dilipna/Furnace4LLM/actions/runs/45585523564)

Both logs were inspected. Their installed-app/browser checks passed before tool
resolution failed. The failed workflows are retained; no check was disabled or
rerun unchanged until green.
