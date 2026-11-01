# Despensa Alexa stock skill — setup after implementation

This release prepares the endpoint. The user will configure Amazon and Cloudflare later; voice is disabled by default. The existing shopping-list integration and its `todo.*` entity are independent.

## Listener and routing

- The normal HA ingress stays on port 8099, restricted to HA's proxy. Gunicorn for the panel stays on loopback 8765.
- A separate voice-only Gunicorn process binds internal port 8100 **only** when enabled. Its sole route is `POST /alexa/despensa`; it has no UI, photo, receipt or shopping APIs.
- The optional Supervisor host-port mapping defaults to null. A Cloudflared add-on on HA's internal network may target the voice port directly using the add-on's actual internal DNS hostname. Confirm reachability during setup. A tunnel on a different host will need an explicitly configured reachable origin.
- On the existing public HA hostname, match `^/alexa/despensa$` before the general HA route and send it to the voice service. Keep the complete path. A locally managed tunnel would use this illustrative rule, with the real hostname/service substituted:

```yaml
ingress:
  - hostname: YOUR_HA_HOSTNAME
    path: ^/alexa/despensa$
    service: http://YOUR_ADDON_INTERNAL_HOSTNAME:8100
  - hostname: YOUR_HA_HOSTNAME
    service: http://YOUR_HA_INTERNAL_HOSTNAME:8123
  - service: http_status:404
```

Cloudflare Access login and browser challenges must not intercept Amazon's exact endpoint. Keep the rest of HA's protections in place. The endpoint itself authenticates Amazon signatures and the configured owner; an unguessable URL is not authentication. Do not expose the panel's port or bypass its CSRF checks. Do not cache voice responses or rewrite request bodies.

## Amazon setup

1. Create a **Custom** skill in Spanish (Spain), invocation **mi despensa**.
2. Import [the es-ES interaction model](alexa/interaction-model-es-ES.json). It defines `GetStockIntent` with `Product` (`AMAZON.SearchQuery`) and `LowStockIntent`, plus help/cancel/stop/fallback.
3. Set the HTTPS endpoint to the public HA hostname followed by `/alexa/despensa`, with the trusted certificate presented by Cloudflare. No Lambda is required.
4. Obtain the skill application ID and the Alexa **userId** for the owner's account from the development simulator's request JSON. It is the `context.System.user.userId`/`session.user.userId`, not an email or person/profile ID. Configure these privately; never paste full requests or account IDs into issues/logs.
5. Set add-on options `alexa_skill_id`, `alexa_skill_user_id`, then `alexa_skill_enabled: true`. These default to empty/false and no external service is activated just by upgrading.
6. Test the development skill on the owner's Echo account. Launch/help reads no stock; stock requests use read-only Grocy API calls. Confirm the exact path cannot reach panel APIs, unsigned requests fail, owner identity matches, and prompts work physically.

Example utterances:

- Alexa, pregúntale a mi despensa cuánto queda de leche.
- Alexa, pregúntale a mi despensa si tenemos arroz.
- Alexa, pregúntale a mi despensa qué productos tienen stock bajo.

Exact names and saved Alexa aliases resolve to active canonical products. Multiple candidates ask for a full name; missing products and failed reads are not interpreted as zero. Responses use current stock units, not shopping quantities or purchased packs. Low-stock summaries list at most five products and respect warning opt-outs.

## Verification boundary

The verifier checks the raw request's `Signature-256`, an Amazon-trusted system-root certificate chain, SAN `echo-api.amazon.com`, a signed timestamp within 150 seconds, the configured skill ID and one authorized Amazon account ID. Certificate retrieval is bounded and restricted to HTTPS `s3.amazonaws.com/echo.api/*.pem`, without redirects. The endpoint does not require a browser session and never mounts or weakens the ordinary application routes.

Automated cryptographic tests generate a disposable test CA and patch certificate transport/trust only inside tests. The isolated Grocy contract verifies stock responses preserve complete product, shopping, stock and history snapshots. This does not establish physical Echo, Cloudflare policy or installed Supervisor acceptance; those remain setup steps.

References: [Amazon web-service requirements](https://developer.amazon.com/en-US/docs/alexa/custom-skills/host-a-custom-skill-as-a-web-service.html), [Cloudflare path routing](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/configuration-file/).
