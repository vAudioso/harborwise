# web/

The HarborWise website. The API serves it at **http://localhost:8000/app/** (`make app`).

| File | What it is |
|---|---|
| `index.html` | The current website: a single self-contained page (React build) |
| `classic.html` | The earlier build, at `/app/classic.html` |
| `hw-extras.js` | Adds forecast confidence, ships alongside the berth, and the turnaround table, using the API's responses |

The site finds the API on its own origin, or at `http://localhost:8000`. Without the API it shows an offline sample. The endpoints it calls are described in [docs/api.md](../docs/api.md).
