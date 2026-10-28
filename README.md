# PolygonMigration

## Overview
PolygonMigration is a Django-based web application designed to facilitate the migration of programming problems and their test cases from the [Polygon](https://polygon.codeforces.com/) platform to a local database and Azure Blob Storage. It provides a user-friendly interface for staff users to fetch, review, tag, and migrate problems, as well as manage test cases and metadata.

## Features
- **Polygon Integration:** Fetch problems and test cases directly from Polygon using API keys.
- **Database Migration:** Store problem statements, metadata, and test cases in a PostgreSQL database.
- **Pluggable Cloud Storage:** Upload test cases to any S3-compatible service (AWS S3, MinIO, Cloudflare R2) or Azure Blob Storage via `problems/storage/`.
- **Tagging & Metadata:** Add, search, and manage tags and difficulty levels for each problem.
- **Admin Interface:** Manage users, problems, tags, and test cases via Django admin.
- **Custom User Model:** Email-based authentication with extended user profile fields.
- **Staff-Only Access:** Only staff users can access migration features.

## Workflow
1. **Login:** Staff users log in via `/users/login/` using their email and password.
2. **Fetch Problem:** Enter a Polygon Problem ID to fetch problem details and test cases.
3. **Review & Tag:** Review the fetched problem, select difficulty, and add tags.
4. **Migrate to Database:** Save the problem and metadata to the local database.
5. **Migrate Test Cases:** Optionally, migrate test cases to the database and/or cloud storage.
6. **View & Manage:** Use the admin interface for advanced management of problems, tags, and users.

## Quick Start (Docker for infrastructure)

```bash
# 1. Infrastructure: PostgreSQL, Redis, MinIO (S3-compatible storage with a web console)
docker compose up -d

# 2. Python environment
python3.12 -m venv .venv && source .venv/bin/activate      # or: uv venv --python 3.12 .venv
pip install -r requirement.txt

# 3. Configuration
cd PolygonMigration
cp .env.example .env     # fill in POLYGON_API_KEY / POLYGON_API_SECRET and a SECRET_KEY;
                         # the DB / Redis / S3 defaults already match docker-compose.yml

# 4. Database + admin user + server
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- App: http://localhost:8000/ (login at `/users/login/`, Django admin at `/admin/`)
- Storage console (MinIO): http://localhost:9001/ (user/password `minioadmin`), bucket `testcases`

## Cloud Storage

Test-case files are written through the `TestCaseStorage` interface in
`problems/storage/base.py`. The migration flow never touches a provider SDK directly;
`problems.storage.get_storage()` returns the backend selected by `STORAGE_PROVIDER`:

| `STORAGE_PROVIDER` | Backend | Env vars |
|---|---|---|
| `s3` (default) | `problems/storage/s3.py` — AWS S3, MinIO, Cloudflare R2, any S3 API | `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`, `S3_ENDPOINT_URL` (empty for AWS) |
| `azure` | `problems/storage/azure.py` — Azure Blob Storage (original implementation) | `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_USERNAME`, `AZURE_PASSWORD`, `AZURE_CONTAINER_NAME` |

File layout (keyed by the **database** problem id, test numbers 1-based and zero-padded):

```
test_cases/{problem_id}/01        # input of test 1
test_cases/{problem_id}/01.a      # expected output of test 1
test_cases/{problem_id}/custom_checker       # compiled custom checker (if the problem has one)
test_cases/{problem_id}/custom_checker.cpp   # checker source, only if compilation failed
```

Re-running the storage migration deletes everything under `test_cases/{problem_id}/`
before uploading, so storage always mirrors the current Polygon test set.

To add a provider: subclass `TestCaseStorage`, implement `upload_bytes`, `list_keys`,
`delete_prefix`, and add a branch to `get_storage()`.

## Manual Setup (without Docker)

Install PostgreSQL and Redis locally, create a database and user:

```sql
CREATE DATABASE polygon_migration;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE polygon_migration TO postgres;
```

Point `DB_*` and `REDIS_*` in `.env` at them, and either run any S3-compatible
service locally or set `S3_*` to a real bucket (AWS S3 / Cloudflare R2).

## Usage
- **Login:** Go to `/users/login/` and log in as a staff user.
- **Main Interface:** Use the home page to fetch and migrate problems by Polygon ID.
- **Admin Panel:** Access `/admin/` for advanced management.
- **Migration:**
  - Fetch a problem by Polygon ID.
  - Select difficulty and tags.
  - Migrate to the database.
  - Migrate test cases to the database and/or cloud storage.

## Environment Variables Reference
| Variable                  | Description                                 |
|--------------------------|---------------------------------------------|
| SECRET_KEY                | Django secret key                           |
| DEBUG                     | Django debug mode (True/False)              |
| ALLOWED_HOSTS             | Comma-separated allowed hosts               |
| DB_NAME                   | PostgreSQL database name                    |
| DB_USER                   | PostgreSQL user                             |
| DB_PASSWORD               | PostgreSQL password                         |
| DB_HOST                   | PostgreSQL host                             |
| DB_PORT                   | PostgreSQL port                             |
| POLYGON_API_KEY           | Polygon API key                             |
| POLYGON_API_SECRET        | Polygon API secret                          |
| STORAGE_PROVIDER          | `s3` or `azure`                             |
| S3_BUCKET_NAME            | Bucket for test-case files                  |
| S3_ACCESS_KEY_ID          | S3 access key                               |
| S3_SECRET_ACCESS_KEY      | S3 secret key                               |
| S3_REGION                 | S3 region (`auto` for R2)                   |
| S3_ENDPOINT_URL           | Custom endpoint (MinIO / R2); empty for AWS |
| STORAGE_CONSOLE_URL       | Optional link to the storage console shown in the UI |
| AZURE_*                   | Azure Blob Storage credentials (when `STORAGE_PROVIDER=azure`) |
| REDIS_HOST                | Redis host (optional)                       |
| REDIS_PORT                | Redis port (optional)                       |
| REDIS_PASSWORD            | Redis password (optional)                   |
| REDIS_SSL                 | Redis SSL (optional, True/False)            |

## Project Structure
```
PolygonMigration/
├── contents/         # Topic and content management
├── problems/         # Polygon migration logic, models, views
│   └── storage/      # TestCaseStorage interface + S3 / Azure backends
├── users/            # Custom user model and authentication
├── static/           # Static files (CSS, JS, etc.)
├── staticfiles/      # Collected static files (for production)
├── logs/             # Log files
├── manage.py         # Django management script
├── PolygonMigration/ # Project settings and URLs
```