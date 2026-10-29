# Configuration

Runtime configuration lives in two complementary places:

| What | Where | Notes |
|------|-------|-------|
| Typed settings & precedence | [`src/election_intelligence/config/settings.py`](../src/election_intelligence/config/settings.py) | The source of truth. Pydantic models with env-var overrides. |
| Local secrets & overrides | `.env` (copy from [`.env.example`](../.env.example)) | Gitignored. Never commit real keys. |
| Reference logging config | [`logging.yaml`](./logging.yaml) | Declarative equivalent of the programmatic logging setup. |

## Precedence

Highest wins:

1. Environment variables (prefix `EI_`, nested with `__`)
2. `.env` file
3. Field defaults in `settings.py`

## Examples

```bash
# Override the database thread count for one run
EI_DATABASE__THREADS=8 election-intelligence info

# Switch to structured JSON logs
EI_LOGGING__JSON_FORMAT=true election-intelligence info
```
