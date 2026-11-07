# Two-Developer Workflow

Both developers work in this repository on separate devices.

## Ownership

### Frontend developer
- `frontend/`
- UI integration and frontend tests.
- Consumes published backend OpenAPI contracts.

### Backend developer
- `backend/`
- Database migrations, business logic, API implementation and backend tests.
- Owns OpenAPI contract.

### Shared ownership
- `docs/`
- Root configuration.
- Shared API/type conventions.
- Any changes crossing application boundaries.

## Working rules

1. Pull latest changes before starting.
2. Keep changes within owned directories where possible.
3. Coordinate before editing shared configuration or contracts.
4. Backend publishes OpenAPI after endpoint changes.
5. Frontend never invents endpoints or response shapes.
6. Never commit `.env`, credentials, tokens or customer data.
7. Run relevant tests before pushing.
8. Use small, descriptive commits.
9. Do not commit generated build output.
10. Review migration changes before applying to shared environments.
