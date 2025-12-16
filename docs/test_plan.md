# ArkhamMirror Test Plan

## 1. Introduction

This document outlines the strategy for improving test coverage for the ArkhamMirror project, moving from an approximate 5.8% coverage to a target of ~30%. The goal is to ensure the reliability and maintainability of critical components, specifically focusing on Workers, Services, and Reflex State classes, which encapsulate the core business logic and background processing.

The current test suite (`app/tests/legacy_backend/`) utilizes a mix of `unittest` and `pytest` frameworks and relies on outdated import paths (`backend.*`). This plan proposes standardizing on `pytest` and establishing a clear structure for new tests aligned with the consolidated `app/arkham/` project structure.

## 2. Testing Framework Standardization: Pytest

**Recommendation**: Standardize all new tests on `pytest`.

**Rationale**:
*   **Simplicity**: `pytest` requires less boilerplate code compared to `unittest`.
*   **Fixtures**: Powerful fixture system for managing test setup and teardown, promoting reusable test data and configurations.
*   **Plugins**: Rich ecosystem of plugins (`pytest-mock`, `pytest-cov`, `pytest-postgresql`, etc.) for extending functionality.
*   **Readability**: More readable and concise test code.

## 3. Project Structure for Tests

New test files will be organized within `app/tests/` to mirror the `app/arkham/` application structure.

```
app/
├── arkham/
│   ├── services/
│   │   ├── workers/
│   │   │   ├── ocr_worker.py
│   │   │   └── ...
│   │   └── timeline_service.py
│   ├── state/
│   │   ├── project_state.py
│   │   └── ...
│   └── ...
└── tests/
    ├── __init__.py
    ├── legacy_backend/          # Existing tests (will be migrated/updated eventually)
    │   ├── test_config.py
    │   └── ...
    ├── unit/
    │   ├── services/
    │   │   ├── workers/
    │   │   │   ├── test_ocr_worker.py
    │   │   │   └── ...
    │   │   └── test_timeline_service.py
    │   ├── state/
    │   │   ├── test_project_state.py
    │   │   └── ...
    │   └── ...
    ├── integration/             # For tests requiring actual external services
    │   ├── services/
    │   │   ├── workers/
    │   │   │   ├── test_ingest_worker_integration.py
    │   │   │   └── ...
    │   │   └── test_db_integration.py
    │   └── ...
    └── conftest.py              # Pytest configuration and shared fixtures
```

**Naming Convention**: Test files will be named `test_<module_name>.py` (e.g., `test_ocr_worker.py` for `ocr_worker.py`).

## 4. Testing Strategy for Components

### 4.1. Workers (`app/arkham/services/workers/`)

Workers perform heavy lifting and interact with various external systems (DB, Redis, Qdrant, LLM, file system). Testing them requires careful isolation.

*   **Unit Tests (`app/tests/unit/services/workers/`)**:
    *   **Focus**: Test the core logic within each worker function in isolation.
    *   **Dependencies**: Mock all external dependencies (database sessions, Redis client, Qdrant client, LLM API calls, file system operations) using `pytest-mock`.
    *   **Example**: Test `ocr_worker.py`'s image processing logic, text extraction, and metadata generation without actually performing OCR or saving to the DB. Test `embed_worker.py`'s chunk processing and embedding generation.
    *   **Verification**: Ensure correct function calls to mocked dependencies, proper data transformation, and expected return values.

*   **Integration Tests (`app/tests/integration/services/workers/`)**:
    *   **Focus**: Verify the end-to-end flow of a worker job, including interactions with Redis/RQ and the database.
    *   **Dependencies**: Use real Redis/RQ (via `pytest-redis` or `docker-compose` setup) and a test database (e.g., `pytest-postgresql` with a dedicated test schema, or an in-memory SQLite database for simpler cases). Mock LLM and Qdrant if they are complex to set up or not the primary focus of the integration test.
    *   **Example**: Test `ingest_worker.py`'s ability to enqueue sub-tasks, process a file through the pipeline, and store final results in the database.
    *   **Verification**: Check if data is correctly stored in the database, RQ jobs are processed, and expected side effects occur.

### 4.2. Services (`app/arkham/services/`)

Services contain the bulk of the application's business logic, data manipulation, and database interaction.

*   **Unit Tests (`app/tests/unit/services/`)**:
    *   **Focus**: Test individual methods or functions within a service in isolation.
    *   **Dependencies**: Mock database sessions and ORM queries directly. Use `pytest-mock` to replace `Session()` or query results.
    *   **Example**: Test `timeline_service.py`'s `extract_date_mentions` or `analyze_timeline_gaps` using mocked data. Test `project_service.py`'s `create_project` without hitting a real database.
    *   **Verification**: Assert correct calculations, data filtering, and logical branches.

*   **Integration Tests (`app/tests/integration/services/`)**:
    *   **Focus**: Validate that services correctly interact with the database (ORM queries, transactions).
    *   **Dependencies**: Use a dedicated test database (e.g., `pytest-postgresql` with `transactional_session` fixture) to ensure tests are isolated and don't interfere with each other or development data.
    *   **Example**: Test `project_service.py`'s `create_project` to ensure a project record is correctly inserted and retrieved from a real database. Test `search_service.py`'s query building.
    *   **Verification**: Confirm data persistence, correct query execution, and transactional integrity.

### 4.3. Reflex State Classes (`app/arkham/state/`)

Reflex State classes manage application state and orchestrate calls to services and UI updates.

*   **Unit Tests (`app/tests/unit/state/`)**:
    *   **Focus**: Test state transitions, computed properties, event handlers (e.g., button clicks, form submissions), and their interaction with mocked services.
    *   **Dependencies**: Mock all service calls and external data sources. The `rx.State` itself can be instantiated and its methods called directly.
    *   **Example**: Test `ProjectState`'s `create_project` method by mocking `project_service.create_project` and asserting that `load_projects` is called and UI state (e.g., `new_project_name`) is reset. Test computed properties like `selected_project_name`.
    *   **Verification**: Ensure state variables are updated correctly, service methods are called with expected arguments, and error messages are set.

## 5. Dependency Management in Tests

*   **Database**:
    *   **Unit Tests**: Mock `Session` and `session.query()` to return predefined data or simulate database operations.
    *   **Integration Tests**: Use `pytest-postgresql` or similar plugins to provision a clean PostgreSQL database for each test run or module. Leverage `transactional_session` fixtures to rollback changes after each test. For simpler integration tests not requiring full Postgres, an in-memory SQLite database can be used if it provides sufficient ORM compatibility.
*   **LLM/External Services (LM Studio, Qdrant, external APIs)**:
    *   **Unit Tests**: Always mock these services using `pytest-mock`. Simulate API responses to ensure deterministic and fast tests.
    *   **Integration Tests**: Only include real external service calls if the *interaction itself* is being tested (e.g., `embed_worker` sending data to Qdrant). For functional tests, mock these to focus on the application logic.
*   **Redis/RQ**:
    *   **Unit Tests**: Mock `redis.Redis` and `rq.Queue` to prevent actual network calls.
    *   **Integration Tests**: Use `pytest-redis` or `docker-compose` to spin up a Redis instance for testing worker queueing and processing.
*   **File System**:
    *   Use `pytest-tmpdir` or `pathlib` for creating temporary files and directories to avoid polluting the actual file system.

## 6. Running Tests

All new tests should be executable via `pytest` from the project root or the `app/` directory:

```bash
# Run all tests
pytest

# Run tests in a specific module
pytest app/tests/unit/services/workers/test_ocr_worker.py

# Run tests containing a specific string in their name
pytest -k "create_project"

# Show coverage (requires pytest-cov)
pytest --cov=app --cov-report=term-missing
```

## 7. Prioritization of Test Implementation

To achieve the target coverage and address critical areas first, tests will be implemented in the following order:

1.  **Workers (`app/arkham/services/workers/`)**:
    *   `ocr_worker.py` (checksums, text extraction)
    *   `parser_worker.py` (chunking, indexing)
    *   `embed_worker.py` (embedding generation, relationship creation)
    *   `ingest_worker.py` (overall ingestion pipeline orchestration)
    *   `clustering_worker.py`, `contradiction_worker.py` (if created/relevant)

2.  **Core Services (`app/arkham/services/`)**:
    *   `project_service.py` (CRUD for projects)
    *   `timeline_service.py` (date/event extraction utilities)
    *   `fact_comparison_service.py` (caching logic, analysis orchestration)
    *   `search_service.py` (query building, filtering)

3.  **State Classes (`app/arkham/state/`)**:
    *   `ProjectState.py` (project selection, CRUD actions)
    *   `IngestionStatusState.py` (status polling, document detail)
    *   `FactComparisonState.py` (analysis initiation, result display)
    *   `TimelineState.py` (data loading, filtering)

## 8. Outdated Tests (`app/tests/legacy_backend/`)

The tests in `app/tests/legacy_backend/` will remain untouched during this phase. Once the new testing framework and structure are established, these tests can be gradually migrated, updated to use `pytest`, adhere to new import paths, and integrate with the new test setup.

---

## 9. Human Checkpoints

A human checkpoint will be requested after:
*   This test plan document is finalized.
*   Initial unit tests for 1-2 workers are completed.
*   Initial unit tests for 1-2 services are completed.
*   Initial unit tests for 1-2 state classes are completed.

This allows for early feedback on the implementation of the test strategy.
