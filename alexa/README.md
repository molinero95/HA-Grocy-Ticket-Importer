# Alexa skill: Mi Despensa (MVP)

Status: interaction-model scaffold only; NOT deployed or connected to Grocy.

## Setup
1. Create a Custom skill in Alexa Developer Console, locale es-ES, invocation name **mi despensa**.
2. Paste `interaction-model.es-ES.json` into the JSON editor and build the model.
3. Set an HTTPS endpoint backed by a Lambda handler (to be implemented). Do not point Alexa at the Home Assistant ingress URL; ingress requires a HA session and is not a public API.
4. The handler must validate Alexa request authenticity, resolve product names against Grocy's existing catalog, and add to Grocy's default shopping list using a private, authenticated bridge. Never embed Grocy API keys in the interaction model or source control.
5. If a name is ambiguous, ask for clarification; if not found, do not create a new catalog product. Ensure retry-safe idempotency using request identifiers.

## Target phrases
- «Alexa, abre Mi Despensa»
- «Alexa, dile a Mi Despensa que añada leche a la lista de la compra»

## Pending
- Implement Lambda handler, Alexa request verification, safe HA/Grocy bridge, and unit tests.
- Confirm secure connectivity from AWS to Home Assistant without exposing private Grocy endpoints.
- Configure credentials in AWS Secrets Manager or encrypted environment settings.
- Validate in Alexa simulator and physical Echo before enabling household use.
