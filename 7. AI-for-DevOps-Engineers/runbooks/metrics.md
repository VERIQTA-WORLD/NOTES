# Veriqta request signals

Use the business-request error fraction, traffic and latency together. Five-hundred errors divided by all eligible requests gives an error fraction; an error count per second alone does not.

Normal CPU does not rule out dependency waits, queueing, locks, garbage collection pauses, network delays or downstream degradation. Compare trace span timing with dependency and application metrics before assigning a cause.

No requests or missing telemetry means insufficient evidence. A quiet graph does not establish recovery. Generate representative traffic and check core business behavior.
