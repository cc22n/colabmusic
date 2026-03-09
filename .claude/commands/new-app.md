Create a new Django app for ColabMusic with the following structure:

1. Create the app: `python manage.py startapp $ARGUMENTS` inside `apps/`
2. Create these files inside the new app:
   - `urls.py` with app_name set
   - `forms.py` (empty, with docstring)
   - `tasks.py` (empty, with Celery imports)
   - `tests/__init__.py`
   - `tests/factories.py` (with factory_boy imports)
   - `tests/test_models.py`
   - `tests/test_views.py`
   - `tests/test_forms.py`
3. Add the app to `INSTALLED_APPS` in `colabmusic/settings/base.py` as `"apps.$ARGUMENTS"`
4. Include the app's URLs in `colabmusic/urls.py`
5. Register models in `admin.py` with basic admin classes

Follow the django-models skill conventions for all model definitions.
