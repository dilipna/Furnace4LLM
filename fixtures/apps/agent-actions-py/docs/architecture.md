# Architecture

    client -> FastAPI (/agent/chat) -> response cache (Redis, 10 min TTL) -> agent loop -> vLLM
                                                                         -> tools: orders, refunds, email

Every chat request first checks the Redis response cache, keyed by the normalized message;
only a cache miss reaches the model. The agent loop lets the model call tools until it
answers, at most four tool rounds per request.
