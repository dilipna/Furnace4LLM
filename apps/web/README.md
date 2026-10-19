This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
# Homepage experiment data

The public overview uses a scoped light theme; the existing evidence and demonstration
pages retain their dark console theme. The prompt-layout inspector switches between
recorded conditions C and D. It does not run a model or predict performance.

`lib/prefix-study.json` is generated from independently verified raw observations:

```bash
# From the repository root:
python scripts/export_prefix_study.py
python scripts/export_prefix_study.py --check
```

The `evidence` workflow checks for drift. Preserve the distinction between medians of
run-level percentiles, token-counter cache reuse, and the separate gate-validation
statistics. All repeated-run timings, including the cache-off outlier, are available
under the homepage's expandable run table. The interactive control uses native buttons
with pressed state and a live result region; reduced-motion preferences disable its
bar transition. No backend or account secret is needed for the recorded-only export.
