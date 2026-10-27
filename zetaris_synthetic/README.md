# Synthetic Zetaris demo context

These three tips are fictional reference content. They contain no participant, child, profile, health or check-in records. The view stores the reference definitions in Zetaris; the app must query the real platform to retrieve them. The app never uses this SQL or its tips as fallback data.

## Register and query

In a running Zetaris SQL Editor, execute each numbered file as one separate request, in order:

1. `01_create_container.sql` creates the new `little_jahsi_demo` container. Administrator permission is required. If it already exists, inspect it before proceeding; the command deliberately does not replace anything.
2. `02_create_tips_view.sql` creates the `goal_tips` SchemaStore view in that container. This uses the documented SchemaStore view command with a standard Spark SQL SELECT and UNION ALL. It deliberately does not replace an existing view.
3. `03_select_tips.sql` queries the persisted view and should return three actual rows. Inspect those returned rows before using the connection.

At the application's fixed SQL prompt, paste the single statement from `03_select_tips.sql`.

## Validation status

The sponsor reference documents the container and view commands and standard Spark SQL query model. This particular synthetic view definition has not yet been executed on the target instance. Successful creation alone is insufficient: the SELECT and a resulting real application query must both succeed before reporting a live integration.

A CSV file on the participant's computer is not used because the sponsor file-source guide does not document a directly usable local PATH for it. This view avoids cloud storage and additional services.

Official references:

- https://github.com/zetaris/getting-started/blob/main/docs/guides/zetaris-lightning-sql-commands.md#12-schema-store-views
- https://github.com/zetaris/getting-started/blob/main/docs/guides/zetaris-lightning-sql-commands.md#3-general-rules
- https://github.com/zetaris/getting-started/blob/main/open_data/parquet_csv/HOWTO.md#3-sources-that-need-a-local-fetch-step-first
