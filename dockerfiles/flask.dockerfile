ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Install Flask and common web dependencies
RUN pip install --no-cache-dir \
    flask \
    gunicorn \
    requests \
    jinja2

WORKDIR /app
EXPOSE 5000

CMD ["python", "-c", "from flask import Flask; print('Flask ready!')"]