# Prisma (Python mirror)

The canonical Prisma schema and migration history live at
`apps/web/prisma/schema.prisma`. This file is a hand-kept mirror.

## Sync rule

The ONLY intentional diff between this file and the web schema is the
`generator` block (Python client instead of JS client). Every other change
— models, enums, indexes, fields — flows one way:

```
apps/web/prisma/schema.prisma   ──►   apps/api/prisma/schema.prisma
```

Note: the `datasource` block keeps `url = env("DATABASE_URL")` on this side
because `prisma-client-py`'s CLI requires it for `prisma generate` / `db pull`
validation, even though the Python client reads the URL from env at runtime.

When you change the schema:

1. Edit `apps/web/prisma/schema.prisma`.
2. From `apps/web/`, run `pnpm prisma migrate dev --name <change>`.
3. Copy the new model / enum / index block into this file verbatim, keeping
   this file's `generator` block untouched.
4. From `apps/api/`, run `uv run prisma generate` to refresh the Python
   client.

## What the Python side NEVER runs

- `prisma migrate dev`
- `prisma migrate deploy`
- `prisma db push`

The web app owns migrations. If `prisma db pull` is ever needed to detect
drift, run it from a scratch directory and diff by hand — do not let it
overwrite this file.
