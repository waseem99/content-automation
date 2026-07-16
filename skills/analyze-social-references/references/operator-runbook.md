# Operator command map

- Diagnose: `refintel doctor`, `refintel capabilities`, `refintel profiles`.
- Single input: `refintel run-reference SOURCE --rights DECLARATION --profile cpu`.
- Batch template: `refintel init-portfolio-request`.
- Batch run: `refintel run-portfolio reference-portfolio-request.json`.
- Facebook login: `refintel facebook-login` on the operator machine only.
- Facebook discovery/batch: `refintel facebook-page PAGE --brand BRAND --rights DECLARATION`.
- Comparison: `refintel compare-library FINGERPRINT... --output-dir OUTPUT`.
- Handoff: successful complete runs write `exports/portfolio_sync_packet.json`.

CPU is the default complete deterministic profile. GPU requires local CUDA and Ollama. Low-memory
disables every-frame decoding and uses a smaller speech model, so disclose reduced evidence.

Every failure must name a supported next action. Prefer an authorized local export when public
extraction is unavailable. Never bypass access controls, upload cookies, place media in Vercel, or
interpret an approval as permission to generate or publish.

