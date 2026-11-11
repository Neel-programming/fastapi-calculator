# FastAPI Calculator with Secure User Model

A FastAPI calculator application with a PostgreSQL-backed user model. Users are stored with SQLAlchemy, validated with Pydantic, and their passwords are hashed with bcrypt. The project is tested at three levels and deployed to Docker Hub through GitHub Actions.

## Features

- Calculator API with add, subtract, multiply, and divide endpoints
- SQLAlchemy `User` model with unique username and email constraints
- Pydantic schemas: `UserCreate` for registration and `UserRead` for responses
- bcrypt password hashing with a verify function
- `POST /users` registration endpoint that never returns the password hash
- Unit, integration, and end-to-end tests
- CI/CD pipeline that tests against a real PostgreSQL container and pushes the image to Docker Hub

## Project Structure

```
fastapi-calculator/
├── app/
│   ├── auth.py              Password hashing and verification
│   ├── database.py          Engine, session, and Base
│   ├── models.py            SQLAlchemy User model
│   ├── schemas.py           Pydantic UserCreate and UserRead
│   └── operations/          Arithmetic functions
├── tests/
│   ├── unit/                Hashing, schema, and arithmetic tests
│   ├── integration/         API and database tests
│   └── e2e/                 Playwright browser tests
├── sql/setup.sql            Raw SQL from the database module
├── templates/index.html     Calculator web page
├── main.py                  FastAPI application
├── Dockerfile
├── docker-compose.yml       FastAPI, PostgreSQL, and pgAdmin
└── .github/workflows/test.yml
```

## Setup

```bash
git clone https://github.com/Neel-programming/fastapi-calculator.git
cd fastapi-calculator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

## Running the Application

Start all three services with Docker Compose:

```bash
docker compose up --build
```

- Calculator: http://localhost:8000
- pgAdmin: http://localhost:5050

## Running Tests Locally

The integration and end-to-end tests need a running PostgreSQL database. Start it first:

```bash
docker compose up -d db
```

Then run the tests:

```bash
pytest tests/unit          # hashing, schemas, arithmetic (no database needed)
pytest tests/integration   # API endpoints and user registration against PostgreSQL
pytest tests/e2e           # browser tests with Playwright
pytest                     # everything
```

The tests connect using the `DATABASE_URL` environment variable. If it is not set, they default to `postgresql://postgres:postgres@localhost:5432/fastapi_db`, which matches the Compose database.

## User Registration

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"neel","email":"neel@example.com","password":"supersecret123"}'
```

Response:

```json
{"id": 1, "username": "neel", "email": "neel@example.com", "created_at": "2026-11-10T18:57:33.184923"}
```

The password is hashed with bcrypt before it is stored. The response uses the `UserRead` schema, which has no password field, so the hash cannot be returned. Registering a duplicate username or email returns a 400 error.

## CI/CD

GitHub Actions runs on every push to `main`:

1. **Test:** starts a PostgreSQL service container, then runs the unit, integration, and end-to-end tests.
2. **Deploy:** if all tests pass, builds the Docker image and pushes it to Docker Hub.

## Docker Hub

Image: https://hub.docker.com/r/neelprogramming/fastapi-calculator

```bash
docker pull neelprogramming/fastapi-calculator:latest
```