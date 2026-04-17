# DSS Frontend

This frontend can now run in two modes:

## 1) Mock mode (recommended for design / UI work)

No backend required.

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

By default, `.env.local.example` enables local mock data.

### Available mock sets

Set `VITE_MOCK_MODE` in `.env.local`:

- `default` – normal job cards
- `long` – long titles and long summaries for layout testing
- `missing` – missing optional fields for fallback testing
- `empty` – empty-state testing

## 2) Real API mode

Edit `.env.local`:

```bash
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```

Then start the backend separately and run:

```bash
npm run dev
```

## Files added for mock workflow

- `src/mocks/jobs.mock.js` – mock job fixtures
- `src/api.js` – mock / real API switch
- `.env.local.example` – local env template

This keeps the UI team unblocked while the Python backend and database remain optional.
