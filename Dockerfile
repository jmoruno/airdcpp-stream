FROM python:3.12-alpine
# pip no hace falta en ejecucion (y arrastra vulnerabilidades conocidas)
RUN rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/bin/pip*
COPY app.py /app.py
USER 99:100
CMD ["python", "-u", "/app.py"]
