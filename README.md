# FastAPI Calculator with User and Calculation Models

A FastAPI calculator backed by PostgreSQL. Users and their calculations are stored with SQLAlchemy and validated with Pydantic, passwords are hashed with bcrypt, and a factory picks the right logic for each calculation type. The project is tested at three levels and deployed to Docker Hub through GitHub Actions.

## Features

- Calculator API with add, subtract, multiply, and divide endpoints
- SQLAlchemy `User` model with unique username and email constraints
- SQLAlchemy `Calculation` model linked to its user by a foreign key
- Pydantic schemas: `UserCreate`/`UserRead` and `CalculationCreate`/`CalculationRead`
- `CalculationFactory` that returns the right operation for Add, Sub, Multiply, or Divide
- bcrypt password hashing with a verify function
- `POST /users` registration endpoint that never returns the password hash
- Unit, integration, and end-to-end tests
- CI/CD pipeline that tests against a real PostgreSQL container, scans the image with Trivy, and pushes it to Docker Hub

## Project Structure

```
fastapi-calculator/
├── app/
│   ├── auth.py                  Password hashing and verification
│   ├── calculation_factory.py   Operation classes, CalculationFactory, build_calculation
│   ├── database.py              Engine, session, and Base
│   ├── models.py                SQLAlchemy User and Calculation models
│   ├── schemas.py               Pydantic user and calculation schemas
│   └── operations/              Arithmetic functions
├── tests/
│   ├── unit/                    Factory, schema, hashing, and arithmetic tests
│   ├── integration/             API and PostgreSQL tests for users and calculations
│   └── e2e/                     Playwright browser tests
├── sql/setup.sql                Raw SQL from the database module
├── templates/index.html         Calculator web page
├── main.py                      FastAPI application
├── Dockerfile
├── docker-compose.yml           FastAPI, PostgreSQL, and pgAdmin
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

## Calculation Model

| Column       | Type      | Notes                                              |
|--------------|-----------|----------------------------------------------------|
| `id`         | integer   | Primary key                                        |
| `a`          | float     | First operand                                      |
| `b`          | float     | Second operand                                     |
| `type`       | string    | `Add`, `Sub`, `Multiply`, or `Divide`              |
| `result`     | float     | Computed by the factory and stored                 |
| `user_id`    | integer   | Foreign key to `users.id`, `ON DELETE CASCADE`     |
| `created_at` | timestamp | Set automatically                                  |

**Stored result.** The result is computed once, when the record is created, and saved in the `result` column. Reading a user's history never recomputes anything, and results can be sorted or filtered in SQL. When editing is added in the next module, the same factory will recompute the result.

**Validation happens in two places.**

- `CalculationCreate` (Pydantic) checks input before it reaches the database. It accepts only real numbers (no text, booleans, NaN, or infinity), matches the type regardless of case (`add` becomes `Add`), and rejects `Divide` with `b = 0`.
- PostgreSQL enforces the same rules with check constraints, so a row that skips the schema is still rejected.

**Factory.** `CalculationFactory.create("Divide")` returns a `DivideOperation`. Each operation class reuses the functions in `app/operations`. `build_calculation()` uses the factory to compute the result and returns an unsaved `Calculation` row.

**Output.** `CalculationRead` returns the calculation fields only. It has no link to the user, so a calculation response can never include the owner's password hash.

## Running Tests Locally

The integration and end-to-end tests need a running PostgreSQL database. Start it first:

```bash
docker compose up -d db
```

Then run the tests:

```bash
pytest tests/unit          # factory, schemas, hashing, arithmetic (no database needed)
pytest tests/integration   # API endpoints, users, and calculations against PostgreSQL
pytest tests/e2e           # browser tests with Playwright
pytest                     # everything
```

To run only the calculation tests:

```bash
pytest tests/unit/test_calculations.py
pytest tests/integration/test_calculation_model.py
```

The tests connect using the `DATABASE_URL` environment variable. If it is not set, they default to `postgresql://postgres:postgres@localhost:5432/fastapi_db`, which matches the Compose database.

If a test fails with `column "a" of relation "calculations" does not exist`, the database still has an old `calculations` table. Reset it with `docker compose down -v`, then `docker compose up -d db`.

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
2. **Scan:** builds the Docker image and checks it with Trivy for critical and high vulnerabilities.
3. **Deploy:** if both pass, builds the image and pushes it to Docker Hub.

## Docker Hub

Image: https://hub.docker.com/r/neelprogramming/fastapi-calculator

The app creates its database tables on startup, so the image needs a PostgreSQL database to connect to. To run it from Docker Hub, start both containers on a shared network:

```bash
docker network create calc-net
docker run -d --name calc-db --network calc-net \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fastapi_db postgres:16
sleep 10
docker run -d --name calc-app --network calc-net -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@calc-db:5432/fastapi_db \
  neelprogramming/fastapi-calculator:latest
```

Then open http://localhost:8000. The `sleep 10` gives PostgreSQL time to start before the app connects.

To stop and remove both containers:

```bash
docker rm -f calc-app calc-db
docker network rm calc-net
```