Run a security audit on the ColabMusic codebase.

Check for these vulnerabilities following the security-hardening skill:

1. **Authentication & Authorization**
   - Views missing `login_required` or `LoginRequiredMixin`
   - Missing ownership checks before edit/delete operations
   - Role-based access not enforced where needed

2. **CSRF**
   - Forms missing `{% csrf_token %}`
   - Views decorated with `@csrf_exempt`
   - HTMX requests not including CSRF header

3. **Input Validation**
   - Direct use of `request.POST`/`request.GET` without form validation
   - File uploads without MIME type validation
   - Missing size limits on uploads
   - User input rendered without escaping

4. **SQL Injection**
   - Any use of `raw()`, `extra()`, or `connection.cursor()` with string formatting
   - f-strings or `.format()` in query parameters

5. **Configuration**
   - `DEBUG = True` in production settings
   - Missing security headers in production
   - Secrets hardcoded instead of using environment variables
   - Missing rate limiting on sensitive endpoints

6. **File Handling**
   - Files served without Content-Disposition headers
   - Missing presigned URL expiration
   - Upload paths allowing directory traversal

Report findings as a table: | Severity | File | Line | Issue | Fix |
