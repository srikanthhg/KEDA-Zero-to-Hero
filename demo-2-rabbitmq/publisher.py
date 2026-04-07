import pika
import sys

rabbitmq_host = "rabbitmq"
queue_name = "orders"

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=rabbitmq_host)
)
channel = connection.channel()
channel.queue_declare(queue=queue_name, durable=True)

num_messages = int(sys.argv[1]) if len(sys.argv) > 1 else 50

for i in range(1, num_messages + 1):
    message = f"Order-{i}"
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=message,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print(f"Sent: {message}")

connection.close()
print(f"Published {num_messages} messages to the '{queue_name}' queue.")
