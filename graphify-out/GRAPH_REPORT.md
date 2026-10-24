# Graph Report - taskmanager  (2026-10-24)

## Corpus Check
- Corpus is ~9,536 words - fits in a single context window. You may not need a graph.

## Summary
- 424 nodes · 774 edges · 17 communities (12 shown, 5 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Alembic Migrations & Schema
- Task Core Domain & Routes
- Container & Docker Infrastructure
- Tagging & Task Association
- FastAPI Core & App Configuration
- Pytest Test Suite & Async Fixtures
- Task Priority Service & Rules
- Task Comments & Notes Service
- Architecture Guidelines & Agent Rules
- Domain Exceptions Hierarchy
- Alembic Async Engine Environment
- Legacy Remote DB Synchronization
- Health Checks & Probes
- Package Metadata & Versioning

## God Nodes (most connected - your core abstractions)
1. `TaskService` - 24 edges
2. `TagService` - 22 edges
3. `Task` - 17 edges
4. `PriorityService` - 17 edges
5. `CommentService` - 16 edges
6. `TaskPriority` - 14 edges
7. `TaskTag` - 13 edges
8. `TaskComment` - 13 edges
9. `Base` - 13 edges
10. `TaskCreate` - 11 edges

## Surprising Connections (you probably didn't know these)
- `prepare_database()` --uses--> `Base`  [INFERRED]
  tests/conftest.py → src/taskmanager/models/base.py
- `test_comment_service()` --calls--> `CommentService`  [INFERRED]
  tests/test_services.py → src/taskmanager/services/comment_service.py
- `test_priority_service()` --calls--> `PriorityService`  [INFERRED]
  tests/test_services.py → src/taskmanager/services/priority_service.py
- `test_tag_service()` --calls--> `TagService`  [INFERRED]
  tests/test_services.py → src/taskmanager/services/tag_service.py
- `test_task_service_crud_and_status()` --uses--> `TaskStatusEnum`  [INFERRED]
  tests/test_services.py → src/taskmanager/models/enums.py

## Import Cycles
- None detected.

## Communities (17 total, 5 thin omitted)

### Community 0 - "Alembic Migrations & Schema"
Cohesion: 0.06
Nodes (16): downgrade(), upgrade(), get_session(), _utc_now(), CommentCreate, CommentRead, CommentUpdate, PriorityCreate (+8 more)

### Community 1 - "Task Core Domain & Routes"
Cohesion: 0.06
Nodes (16): create_task(), delete_task(), get_task(), get_task_service(), list_tasks(), list_tasks_between(), update_task(), TaskStatusEnum (+8 more)

### Community 2 - "Container & Docker Infrastructure"
Cohesion: 0.05
Nodes (41): context, dockerfile, condition, container_name, environment, healthcheck, image, logging (+33 more)

### Community 3 - "Tagging & Task Association"
Cohesion: 0.07
Nodes (11): assign_tag_to_task(), create_tag(), delete_tag(), get_all_tags(), get_all_tags_with_tasks(), get_tag_service(), unassign_tag_from_task(), update_tag() (+3 more)

### Community 4 - "FastAPI Core & App Configuration"
Cohesion: 0.06
Nodes (7): Settings, setup_logging(), create_app(), lifespan(), _seed_initial_statuses(), Base, TaskStatus

### Community 5 - "Pytest Test Suite & Async Fixtures"
Cohesion: 0.09
Nodes (10): anyio_backend(), client(), prepare_database(), session(), test_comments_flow(), test_health(), test_priorities_flow(), test_remote_db_stubs() (+2 more)

### Community 6 - "Task Priority Service & Rules"
Cohesion: 0.09
Nodes (8): create_priority(), delete_priority(), get_all_priorities(), get_priority(), get_priority_service(), update_priority(), TaskPriority, PriorityService

### Community 7 - "Task Comments & Notes Service"
Cohesion: 0.10
Nodes (7): create_comment(), delete_comment(), get_comment_service(), get_task_comments(), update_comment(), TaskComment, CommentService

### Community 8 - "Architecture Guidelines & Agent Rules"
Cohesion: 0.14
Nodes (24): Agent Architectural Layers Rule, AI Agent Guidelines, Agent Russian Language Standard, Agent Verification and Quality Standard, Agent Versioning Rule, HTTP API Routers Layer, Clean Architecture Layering, Code Style and Ruff Linting (+16 more)

### Community 9 - "Domain Exceptions Hierarchy"
Cohesion: 0.18
Nodes (6): CommentNotFoundError, DomainError, EntityNotFoundError, PriorityNotFoundError, TagNotFoundError, TaskNotFoundError

### Community 10 - "Alembic Async Engine Environment"
Cohesion: 0.18
Nodes (4): do_run_migrations(), run_async_migrations(), run_migrations_offline(), run_migrations_online()

### Community 11 - "Legacy Remote DB Synchronization"
Cohesion: 0.29
Nodes (3): check_remote_db_for_updates(), sync_download(), sync_upload()

## Knowledge Gaps
- **4 isolated node(s):** `taskmanager`, `Pydantic DTO Schemas Layer`, `Logging Architecture and Rotation`, `Quickstart and Execution`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 208 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskService` connect `Task Core Domain & Routes` to `Alembic Migrations & Schema`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `TaskService` (e.g. with `create_task()` and `delete_task()`) actually correct?**
  _`TaskService` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `taskmanager`, `Pydantic DTO Schemas Layer`, `Logging Architecture and Rotation` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Alembic Migrations & Schema` be split into smaller, more focused modules?**
  _Cohesion score 0.060528559249786874 - nodes in this community are weakly interconnected._
- **Why does `Base` connect `FastAPI Core & App Configuration` to `Alembic Migrations & Schema`, `Task Core Domain & Routes`, `Tagging & Task Association`, `Pytest Test Suite & Async Fixtures`, `Task Priority Service & Rules`, `Task Comments & Notes Service`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `TagService` (e.g. with `assign_tag_to_task()` and `create_tag()`) actually correct?**
  _`TagService` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `Task Core Domain & Routes` be split into smaller, more focused modules?**
  _Cohesion score 0.05501165501165501 - nodes in this community are weakly interconnected._