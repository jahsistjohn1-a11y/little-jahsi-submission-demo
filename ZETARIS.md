# Zetaris context integration

This optional connection retrieves actual synthetic reference rows from Zetaris before generating a plan. It does not upload child profiles, feelings, reflections or check-ins. H-MEM and journey memory remain in the browser. Nightshift's native verifier, rubric requirements and acceptance threshold remain unchanged.

## Run

First obtain a working Zetaris instance, its numeric organization ID, a bearer token or API key with read access, and a table containing synthetic demonstration context. This application does not create cloud compute or authorize paid infrastructure. A local Zetaris instance can be used if it exposes the documented SQL endpoint.

Run in an interactive terminal:

```sh
python3 meterless_nightshift_lab/lab.py start --deepseek --zetaris
```

On Windows, use `py -3` instead of `python3`. Enter the DeepSeek key at its hidden prompt. Enter the Zetaris origin, organization ID, and one fixed SELECT query from the synthetic table. Enter the Zetaris credential at the hidden prompt. All credentials stay in server memory. No credential file or environment variable is needed. Restart and refresh the page after changing settings.

For a minimal synthetic fixture, follow [the three separate registration and query steps](zetaris_synthetic/README.md). Those statements are based on the sponsor command reference and still need execution on your actual instance. The fixed application query after successful registration is:

```sql
SELECT topic, tip FROM little_jahsi_demo.goal_tips LIMIT 3
```

Use HTTPS for remote instances. HTTP is permitted only for loopback addresses. The default route matches the current local platform bundle: `/api/proxy/query/sql/start`, with `select` and `pageLimit` request fields. For the older starter guide UI route, add `--zetaris-route legacy` to use `/api/proxy/sql-editor/sqls/run-query`. For a raw REST origin, add `--zetaris-route raw`, which uses `/api/v1.0/sql-editor/sqls/run`.

The query is fixed on the server and capped at five rows. Browser callers cannot supply SQL, an endpoint or a provider credential. Requests require a separate local session capability and the local application's Origin. TLS certificate validation stays enabled.

## Evidence and limitations

Configured does not mean verified. Each goal queries Zetaris and requires actual nonempty rows before calling the generator. A failed, empty, unreadable or oversized response blocks generation visibly. No fallback context is substituted. Retrieved rows are quoted as untrusted reference data in the actual generator prompt. The rubric continues to judge the user's exact goal.

The downloadable job record includes `zetaris`: actual rows, row count, request ID, SQL, endpoint and evidence filename. Private server evidence in ignored `.runtime/evidence/zetaris-*.json` preserves the original response, status and request without authorization headers or credentials. Use synthetic data only, and inspect evidence before sharing it.

Unit tests exercise transport authorization, provenance and failure handling without network access. They do not prove a live instance is connected. A successful real query and resulting plan must be demonstrated before claiming a completed Zetaris integration.

Sponsor API reference: https://github.com/zetaris/getting-started
