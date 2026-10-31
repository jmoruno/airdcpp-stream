FROM python:3.12-alpine
COPY app.py /app.py
USER 99:100
CMD ["python", "-u", "/app.py"]
