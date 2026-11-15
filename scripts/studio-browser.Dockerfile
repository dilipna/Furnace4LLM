# Disposable verification tooling; never used by the application or deployment image.
# Match the existing Playwright development dependency in uv.lock.
FROM ghcr.io/astral-sh/uv@sha256:85d4cb1afa769a7338e095b927bee941cf5ec92266c7424b3f6c0f2748567248
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN uv pip install --system playwright==1.63.0 && python -m playwright install --with-deps chromium && chmod -R a+rX /opt/playwright
