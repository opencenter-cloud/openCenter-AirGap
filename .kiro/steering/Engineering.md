---
inclusion: always
---
## Engineering Guidelines

### 1. Readability & Style
* **Code is Read More Than Written:** Prioritize clarity over cleverness. Avoid obscure one-liners or "magic" logic.
* **Idiomatic Consistency:** Strictly follow the official Style Guide for the language (e.g., Google Style Guide for C++/Python, Effective Go, Airbnb/Google for TS).
* **Naming:** Use verbose, descriptive variable and function names. A variable name should explain its contents; a function name should explain its action.
* **Formatting:** Assume the code will be run through an auto-formatter (`gofmt`, `clang-format`, `prettier`). Structure it so strictly that the formatter changes nothing.

### 2. Architecture & Design
* **Single Responsibility:** Functions should do one thing and do it well. Split complex logic into small, testable helper functions.
* **Composition over Inheritance:** Prefer interfaces and composition. Avoid deep inheritance hierarchies.
* **Explicit Dependencies:** Inject dependencies rather than instantiating them internally (Dependency Injection). This ensures testability.

### 3. Error Handling & Safety
* **No Silent Failures:** Never swallow errors. Propagate them or handle them with explicit logging.
* **Defensive Coding:** Validate inputs at the boundary. Assume external data is malformed until proven otherwise.
* **Type Safety:** Use strict typing. Avoid `any` (TS) or `interface{}` (Go) unless absolutely necessary.

### 4. Testing
* **Testability First:** Write code that is trivial to unit test. If a function is hard to test, it is badly designed.
* **Edge Cases:** Do not just handle the "happy path." Explicitly account for nulls, empty sets, and network timeouts.

### 5. Documentation
* **Self-Documenting Code:** The code flow should be obvious. Use comments only to explain *why* (context/decisions), not *what* (syntax).
* **Docstrings:** All exported functions and public APIs must have descriptive docstrings/comments (GoDoc, JSDoc).

### 6. Security
* **Secrets Management:** **Strict Prohibition.** Never hardcode secrets, API keys, or credentials in source code. Use environment variables or secret injection.
* **Input Sanitization:** Treat all user input as hostile. Prevent Injection (SQLi, XSS, Command Injection) by using parameterized queries and auto-escaping templates.
* **Zero Trust:** Do not rely on network perimeter security. Verify authentication and authorization (RBAC/ABAC) explicitly at every API endpoint.
* **Supply Chain Safety:** Pin all dependencies to specific versions (lockfiles/hashes). Never use mutable tags like `latest` in production.

### 7. Maintenance & Evolution
* **The "Atomic Commit" Rule:** Code, Tests, and Documentation are a single unit. Any logic change **must** be accompanied by:
    1.  Updated or new tests to verify the change.
    2.  Updated documentation/docstrings to reflect the new behavior.
* **No Stale Artifacts:** A change is incomplete if it leaves behind comments or tests that describe the old behavior.