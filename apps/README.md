# Document Check API

## Overview
FastAPI-based REST API for document checking service.

## Requirements
- Python 3.13+
- uv (Python package manager)

## Installation
```bash
# Install dependencies using uv
uv sync
```

## Running the API
```bash
# Start the development server
uv run uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints
- `GET /` - Welcome message
- `GET /api/hello` - Returns "Hello API"

## API Documentation
Once the server is running, you can access:
- Interactive API documentation: `http://localhost:8000/docs`
- Alternative API documentation: `http://localhost:8000/redoc`