FROM python:3.11-slim
WORKDIR /app
RUN pip install pika
COPY consumer.py .
CMD ["python", "consumer.py"]
