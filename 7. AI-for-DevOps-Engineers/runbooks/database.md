# Veriqta database connectivity

A running database Pod does not prove the API can connect, authenticate or query its schema. Confirm the database Service, EndpointSlice readiness, the API's DB_HOST and DB_PORT, and a business request.

The lab database listens on TCP 5432. An API configured for 5433 has a configuration mismatch. Do not print DB_PASSWORD, connection URLs or all environment variables. Inspect only the host and port fields.

If a release causes request failures, compare its Pod template with the last healthy revision. Check data/schema compatibility before rollback. Validate /health and /api/users after recovery, then observe errors and latency under traffic.
