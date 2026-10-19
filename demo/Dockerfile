# The Core image plus the demo Spider Plugin -- the way any deployment adds its Spiders.
# `core` is the Core image: docker-compose.yml builds it from this checkout and passes it in.
FROM core

COPY demo/plugin /demo/plugin
COPY demo/seed_demo.py demo/docker-entrypoint.sh /demo/

RUN uv pip install --no-cache /demo/plugin

ENTRYPOINT ["/demo/docker-entrypoint.sh"]
