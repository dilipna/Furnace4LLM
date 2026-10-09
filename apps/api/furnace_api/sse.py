"""Server-sent events responses that survive proxies."""

from collections.abc import AsyncIterator

from sse_starlette.sse import EventSourceResponse


def sse(stream: AsyncIterator[dict[str, str]]) -> EventSourceResponse:
    # no-transform: the Next.js rewrite proxy (and CDNs) would otherwise gzip the stream
    # and buffer it, so the browser sees nothing until the stream ends.
    return EventSourceResponse(stream, headers={"Cache-Control": "no-cache, no-transform"})
