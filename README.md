# FastAPI Calculator with Users, JWT Login, and Calculation BREAD

A FastAPI back end backed by PostgreSQL. Users register and log in to get a JWT, then browse, read, edit, add, and delete their own calculations. Data is stored with SQLAlchemy and validated with Pydantic, passwords are hashed with bcrypt, and a factory picks the right logic for each calculation type. The project is tested at three levels and deployed to Docker Hub through GitHub Actions.

## Features

- `POST /users/register` and `POST /users/login`, with bcrypt password hashing and JWT access tokens
- Calculation BREAD routes (Browse, Read, Edit, Add, Delete) that only show the logged-in user's data
- SQLAlchemy `User` and `Calculation` models, linked by a foreign key
- Pydantic schemas: `UserCreate`, `UserLogin`, `UserRead`, `Token`, `CalculationCreate`, `CalculationRead`
- `CalculationFactory` that returns the right operation for Add, Sub, Multiply, or Divide
- Interactive API documentation at `/docs` (Swagger UI) and `/redoc`
- Unit, integration, and end-to-end tests
- CI/CD pipeline that tests against a real PostgreSQL container, scans the image with Trivy, and pushes it to Docker Hub

## Project Structure

```
fastapi-calculator/
├── app/
│   ├── auth.py                  Password hashing, JWT tokens, get_current_user
│   ├── calculation_factory.py   Operation classes, CalculationFactory, build_calculation
│   ├── database.py              Engine, session, Base, and init_db
│   ├── models.py                SQLAlchemy User and Calculation models
│   ├── schemas.py               Pydantic user, token, and calculation schemas
│   ├── operations/              Arithmetic functions
│   └── routers/
│       ├── users.py             Register and login routes
│       └── calculations.py      Calculation BREAD routes
├── tests/
│   ├── unit/                    Factory, schema, hashing, token, and arithmetic tests
│   ├── integration/             Route and PostgreSQL tests for users and calculations
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

- API documentation: http://localhost:8000/docs
- Calculator page: http://localhost:8000
- pgAdmin: http://localhost:5050

## API Endpoints

| Method | Path                 | Auth   | Purpose                                         | Success |
|--------|----------------------|--------|-------------------------------------------------|---------|
| POST   | `/users/register`    | none   | Create an account                               | 201     |
| POST   | `/users/login`       | none   | Check the password and return a JWT             | 200     |
| GET    | `/calculations`      | Bearer | Browse your calculations, oldest first          | 200     |
| GET    | `/calculations/{id}` | Bearer | Read one calculation                            | 200     |
| PUT    | `/calculations/{id}` | Bearer | Edit a, b, and type; the result is recomputed   | 200     |
| POST   | `/calculations`      | Bearer | Add a calculation; the result is computed       | 201     |
| DELETE | `/calculations/{id}` | Bearer | Delete a calculation                            | 204     |
| GET    | `/health`            | none   | Health check used by Docker                     | 200     |

Error responses use the form `{"error": "message"}`:

| Status | When                                                                      |
|--------|---------------------------------------------------------------------------|
| 400    | Invalid data (bad type, divide by zero, text instead of a number, taken username) |
| 401    | Missing, invalid, or expired token, or a wrong username or password       |
| 404    | The calculation does not exist or belongs to another user                 |

## Authentication

1. `POST /users/login` with a username and password returns `{"access_token": "...", "token_type": "bearer"}`.
2. Send the token with each calculation request: `Authorization: Bearer <token>`.
3. Tokens expire after 30 minutes. Log in again to get a new one.

Security details:

- Passwords are stored only as bcrypt hashes and never appear in a response. Passwords over 72 bytes are rejected because bcrypt ignores anything past that.
- A wrong password and an unknown username get the same 401 message and take the same time, so attackers cannot tell which usernames exist.
- The owner of a calculation always comes from the token, never from the request body. Another user's calculation returns 404, so its existence is not revealed.
- Tokens are signed with `JWT_SECRET_KEY`. The built-in default is for development only; set your own in production, for example `-e JWT_SECRET_KEY=$(openssl rand -hex 32)`.

## Manual Testing with OpenAPI (/docs)

1. Start the app with `docker compose up --build` and open http://localhost:8000/docs.
2. **Register:** open `POST /users/register`, click **Try it out**, enter a username, email, and password, then click **Execute**. Expect `201`.
3. **Log in:** open `POST /users/login`, enter the same username and password, and click **Execute**. Expect `200`. Copy the `access_token` value, without the quotes.
4. **Authorize:** click **Authorize** at the top right, paste the token into **Value**, click **Authorize**, then **Close**. The lock icons on the calculation routes close.
5. **Add:** `POST /calculations` with `{"a": 10, "b": 4, "type": "Divide"}`. Expect `201` and `"result": 2.5`. Note the `id`.
6. **Browse:** `GET /calculations`. Expect `200` and a list containing the new calculation.
7. **Read:** `GET /calculations/{calc_id}` with that id. Expect `200`.
8. **Edit:** `PUT /calculations/{calc_id}` with `{"a": 6, "b": 7, "type": "Multiply"}`. Expect `200` and `"result": 42`.
9. **Delete:** `DELETE /calculations/{calc_id}`. Expect `204`. Reading it again returns `404`.
10. **Errors:** `POST /calculations` with `{"a": 10, "b": 0, "type": "Divide"}` returns `400` with `Cannot divide by zero.` Clicking **Authorize**, then **Logout**, makes every calculation route return `401`.

The same documentation is available as a read-only page at http://localhost:8000/redoc.

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

**Stored result.** The result is computed when a calculation is added and saved in the `result` column, so browsing never recomputes anything. Editing a calculation runs the factory again and saves the new result.

**Validation happens in two places.**

- `CalculationCreate` (Pydantic) checks input before it reaches the database. It accepts only real numbers (no text, booleans, NaN, or infinity), matches the type regardless of case (`add` becomes `Add`), and rejects `Divide` with `b = 0`. The Add and Edit routes both use it.
- PostgreSQL enforces the same rules with check constraints, so a row that skips the schema is still rejected.

**Factory.** `CalculationFactory.create("Divide")` returns a `DivideOperation`. Each operation class reuses the functions in `app/operations`.

## Running Tests Locally

The integration and end-to-end tests need a running PostgreSQL database. Start it first:

```bash
docker compose up -d db
```

Then run the tests:

```bash
pytest tests/unit          # factory, schemas, hashing, tokens, arithmetic (no database needed)
pytest tests/integration   # register, login, and calculation routes against PostgreSQL
pytest tests/e2e           # browser tests with Playwright
pytest                     # everything
```

The route tests are in two files:

```bash
pytest tests/integration/test_users.py               # register, login, data saved in the database
pytest tests/integration/test_calculation_routes.py  # BREAD, invalid data, ownership, tokens
```

The tests connect using the `DATABASE_URL` environment variable. If it is not set, they default to `postgresql://postgres:postgres@localhost:5432/fastapi_db`, which matches the Compose database.

If a test fails with `column "a" of relation "calculations" does not exist`, the database still has an old `calculations` table. Reset it with `docker compose down -v`, then `docker compose up -d db`.

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

Then open http://localhost:8000/docs. The `sleep 10` gives PostgreSQL time to start before the app connects. After about 30 seconds, `docker ps` shows the app container as `healthy`.

To stop and remove both containers:

```bash
docker rm -f calc-app calc-db
docker network rm calc-net
```
