Implement a new feature for ColabMusic: $ARGUMENTS

Follow this workflow:

1. **Plan first** — Before writing any code, outline:
   - Which apps/models are affected
   - What views and URLs are needed
   - What templates/components are needed
   - Any Celery tasks required
   - Security considerations

2. **Create a git branch** — `git checkout -b feature/$ARGUMENTS`

3. **Models** — Follow the django-models skill:
   - Add/modify models with proper Meta, __str__, get_absolute_url
   - Create and run migrations
   - Add factories for new models

4. **Views + URLs** — Follow the htmx-components skill:
   - CBVs for CRUD, function views for HTMX partials
   - Add URL patterns with proper namespacing

5. **Templates** — Follow the htmx-components skill:
   - Create partials in components/ for reusable pieces
   - Use HTMX attributes for dynamic behavior
   - Tailwind for styling with the project color scheme

6. **Security** — Follow the security-hardening skill:
   - Add authentication/authorization checks
   - Validate all inputs
   - Rate limit if applicable

7. **Tests** — Write tests for:
   - Model creation and validation
   - View responses (status codes, templates, redirects)
   - Permission checks (authenticated, owner, role)
   - Edge cases

8. **Verify** — Run the full check:
   ```bash
   python manage.py test apps/ --verbosity=2
   python manage.py check --deploy
   black apps/ && isort apps/ && flake8 apps/
   ```

9. **Commit** — Use conventional commit: `feat: $ARGUMENTS`
