# Mock frontend setup

The frontend was adjusted so designers and frontend developers can work without starting the Python backend.

## What changed

- Added `frontend/src/mocks/jobs.mock.js`
- Updated `frontend/src/api.js` to support mock mode
- Added `frontend/.env.local.example`
- Updated `frontend/README.md`

## Run in mock mode

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

## Switch mock scenarios

Edit `frontend/.env.local`:

```bash
VITE_MOCK_MODE=default
```

Options:
- `default`
- `long`
- `missing`
- `empty`

## Use real backend again

Set:

```bash
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```
