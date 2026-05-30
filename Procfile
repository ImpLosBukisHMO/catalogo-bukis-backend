web: cd catalogo_backend && gunicorn catalogo_backend.wsgi --bind 0.0.0.0:$PORT --workers 2
release: cd catalogo_backend && python manage.py migrate --noinput && python manage.py collectstatic --noinput
