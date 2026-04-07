import pika
import time
import os

rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
queue_name = os.environ.get("QUEUE_NAME", "orders")

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=rabbitmq_host)
)
channel = connection.channel()
channel.queue_declare(queue=queue_name, durable=True)

def callback(ch, method, properties, body):
    message = body.decode()
    print(f"Processing order: {message}")
    time.sleep(3)
    print(f"Done: {message}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=queue_name, on_message_callback=callback)

print("Consumer started. Waiting for messages...")
channel.start_consuming()
