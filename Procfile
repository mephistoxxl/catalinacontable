web: gunicorn sistema.wsgi --worker-class ${WORKER_CLASS:-gevent} --workers ${WEB_CONCURRENCY:-3} --timeout ${GUNICORN_TIMEOUT:-120}
worker: python manage.py rqworker default sri reportes
