# KEDA - Zero to Hero

## Table of Contents

1. Why KEDA
2. What is KEDA
3. How KEDA Works
4. Install and Setup on KIND Cluster
5. Demo 1 - Scaling Based on Cron Schedule (Simple)
6. Demo 2 - Scaling Based on RabbitMQ Queue Length (Real World)

---

## 1. Why KEDA

### The Problem with Traditional Kubernetes Autoscaling

Kubernetes has a built in autoscaler called the Horizontal Pod Autoscaler (HPA).
The HPA can scale your pods based on CPU and Memory usage. That sounds useful, but
there is a big limitation.

Think about this real world example:

You have an order processing application. Orders come in through a message queue
(like RabbitMQ or Kafka). Your application picks up messages from the queue and
processes them.

Now here is the problem:

- Your application might be sitting idle with low CPU and Memory usage.
- But there could be 10,000 messages waiting in the queue.
- The HPA has no idea about those 10,000 messages. It only looks at CPU and Memory.
- So it will NOT scale up your application, even though there is a huge backlog of work.

This is where the real pain begins. The HPA does not understand events. It does not
know about queue lengths, stream lags, database row counts, or any external metric.

### Another Problem - Scaling to Zero

With the default HPA, your application always has at least one pod running, even
when there is zero traffic or zero events. You are paying for compute that is doing
absolutely nothing.

Imagine you have 50 microservices and 30 of them only process events a few times a
day. Those 30 services are running 24/7 doing nothing most of the time. That is a
waste of money.

### What We Actually Need

We need an autoscaler that can:

- Scale based on events, not just CPU and Memory
- Understand external systems like message queues, databases, and custom metrics
- Scale all the way down to zero pods when there is no work
- Scale back up from zero when new events arrive
- Work alongside the existing Kubernetes HPA without replacing it

This is exactly why KEDA was created.

### But Wait - Won't HPA Eventually Catch the CPU Spike?

This is a very common and fair question. The thinking goes like this:

"If there are 1000 messages in a queue, my app will start reading them. That
will cause a CPU spike. The HPA will see the CPU spike and scale up. So why
do I need KEDA?"

Here is why that logic breaks down:

1. Scale to Zero kills it completely.
   If you want to save cost and run 0 pods when the queue is empty, there
   is no pod running at all. No pod means no CPU usage. No CPU usage means
   HPA has nothing to react to. The messages just sit in the queue forever
   and nobody picks them up. HPA cannot bring a Deployment from 0 to 1.
   Only KEDA can do that.

2. Not every workload spikes CPU.
   Many real world applications are I/O bound, not CPU bound. Think of a
   service that reads a message, makes an HTTP call to another API, waits
   for the response, and writes to a database. The CPU usage stays at 5 to
   10 percent the entire time, even if the queue has 10,000 messages. The
   bottleneck is network and waiting, not CPU. HPA will never scale this
   app because CPU never crosses the threshold.

3. HPA is reactive. KEDA is proactive.
   HPA waits for your app to struggle first. The CPU has to spike, then
   the metrics server has to collect it, then HPA has to evaluate it, then
   it creates new pods, then the pods start up. By the time all of that
   happens, your queue backlog has grown even larger and your processing
   latency is terrible. KEDA directly watches the queue. It sees 1000
   messages and immediately knows it needs more pods. It does not wait for
   your app to struggle.

4. CPU does not tell you how many pods you need.
   Say your CPU is at 80 percent. Does that mean you need 2 more pods or
   20 more pods? HPA does not know. It just slowly adds pods one step at
   a time and waits to see if CPU drops. With KEDA, if there are 1000
   messages and your threshold is 10 messages per pod, KEDA knows exactly
   that you need 100 pods (or whatever your max is). The scaling is precise
   and instant.

5. HPA has a stabilization delay.
   HPA deliberately waits before scaling down (default 5 minutes) and also
   has a delay before scaling up. This is to avoid flapping. But for event
   driven workloads, this delay means your users are waiting longer than
   they should. KEDA can be configured with its own pollingInterval and
   cooldownPeriod to react much faster.

So to summarize: yes, HPA might eventually scale your app if the CPU happens
to spike. But it is slow, imprecise, does not work for I/O bound apps, and
completely fails when you want to scale to zero. KEDA solves all of these
problems because it watches the actual source of work (the queue) instead of
a side effect (CPU usage).

---

## 2. What is KEDA

KEDA stands for Kubernetes Event Driven Autoscaler.

It is a lightweight, open source component that you install into your Kubernetes
cluster. It was originally created by Microsoft and Red Hat, and is now a CNCF
(Cloud Native Computing Foundation) graduated project.

Here is what KEDA does in simple terms:

- It connects to external event sources (like a message queue, a database, a
  cron schedule, Prometheus metrics, and many more).
- It checks how many events are waiting, Redis, and many more).
- It is safe to install alongside any existing application. It only affects the
  apps you configure it for.

---

## 3. How KEDA Works

### Architecture Overview

When you install KEDA in your cluster, it runs three main components:

1. KEDA Operator (keda-operator)
   - This is the brain of KEDA.
   - It watches for ScaledObject and ScaledJob resources that you create.
   - It connects to the external event source (like a queue) and checks the
     metric (like queue length).
   - It activates or deactivates your Deployment by scaling it to or from zero.

2. Metrics API Server (keda-operator-metrics-apiserver)
   - This acts as a Kubernetes metrics server.
   - It exposes custom metrics (like queue length) to the Kubernetes HPA.
   - The HPA reads these metrics and decides how many pods to run.

KEDA does NOT replace the Horizontal Pod Autoscaler. It works WITH the HPA.
KEDA handles the scaling from 0 to 1 and from 1 to 0. Once there is at least
one pod running, KEDA creates an HPA behind the scenes and the HPA takes over
scaling from 1 to N.

### Key Points

- KEDA is a single purpose tool. It only does event driven scaling.
- It is lightweight. It does not add heavy overhead to your cluster.
- It supports 60 plus built in scalers (RabbitMQ, Kafka, AWS SQS, Azure Queue,
  Prometheus, Cron, MySQL, PostgreSQLhich would cause conflicts.

### How the Scaling Flow Works

Step 1: You create a ScaledObject (a custom Kubernetes resource).
        In this ScaledObject, you specify:
        - Which Deployment to scale
        - What event source to watch (called a "trigger")
        - The threshold for scaling (for example, scale up if queue has more than 5 messages)

Step 2: The KEDA Operator sees the ScaledObject and starts polling the event source.

Step 3: If there are no events, KEDA scales the Deployment to zero pods.

Step 4: When events arrive (for example, messages appear in the queue), KEDA scales
        the Deployment from 0 to 1.

Step 5: KEDA creates an HPA resource behind the scenes. The HPA now takes over
        and scales from 1 to N based on the metric value and threshold.

Step 6: When events are done and the queue is empty again, the HPA scales down
        to 1, and then KEDA scales from 1 to 0.

### Custom Resources (CRDs)

KEDA installs four Custom Resource Definitions:

1. ScaledObject
   - Used to scale Deployments and StatefulSets.
   - You define the target (which Deployment), the trigger (which event source),
     and the scaling rules (min replicas, max replicas, threshold).

3. Admission Webhooks (keda-admission-webhooks)
   - This validates the KEDA resources you create.
   - For example, it prevents you from creating two ScaledObjects that target
     the same Deployment, w to be processed.
- Based on that, it tells Kubernetes to scale your application up or down.
- If there are zero events, it can scale your application down to zero pods.
- When new events arrive, it brings your application back up.

2. ScaledJob
   - Used to scale Kubernetes Jobs.
   - Instead of scaling a long running Deployment, this creates new Job pods
     for each batch of events.

3. TriggerAuthentication
   - Stores authentication details (like passwords, connection strings) for
     connecting to the event source.
   - This is namespace scoped.

4. ClusterTriggerAuthentication
   - Same as TriggerAuthentication but cluster wide.
   - Can be shared across namespaces.

### What is a Scaler?

A scaler is a plugin inside KEDA that knows how to talk to a specific event source.

For example:
- The RabbitMQ scaler knows how to check the queue length of a RabbitMQ queue.
- The Kafka scaler knows how to check the consumer lag of a Kafka topic.
- The Cron scaler knows how to trigger scaling based on a time schedule.
- The Prometheus scaler knows how to run a PromQL query and use the result.

KEDA has 60 plus built in scalers. You can also write external scalers if needed.

---

## 4. Install and Setup on KIND Cluster

### Prerequisites

Make sure you have the following tools installed on your machine:

- Docker (KIND runs Kubernetes inside Docker containers)
- kubectl (command line tool for Kubernetes)
- Helm (package manager for Kubernetes)
- KIND (Kubernetes IN Docker)

### Step 1: Install KIND (if not already installed)

For Mac:
```
brew install kind
```

For Linux:
```
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

### Step 2: Create a KIND Cluster

```
kind create cluster --name keda-demo
```

Verify the cluster is running:
```
kubectl cluster-info --context kind-keda-demo
kubectl get nodes
```

You should see one node in Ready state.

### Step 3: Install KEDA using Helm

Add the KEDA Helm repository:
```
helm repo add kedacore https://kedacore.github.io/charts
```

Update the repository:
```
helm repo update
```

Install KEDA in the "keda" namespace:
```
helm install keda kedacore/keda --namespace keda --create-namespace
```

### Step 4: Verify KEDA is Running

```
kubectl get pods -n keda
```

You should see three pods running:
- keda-operator
- keda-operator-metrics-apiserver
- keda-admission-webhooks

Wait until all pods show STATUS as Running. It may take a minute or two.

You can also check the Custom Resource Definitions that KEDA installed:
```
kubectl get crd | grep keda
```

You should see:
- scaledobjects.keda.sh
- scaledjobs.keda.sh
- triggerauthentications.keda.sh
- clustertriggerauthentications.keda.sh

KEDA is now installed and ready to use.

---

## 5. Demo 1 - Scaling Based on Cron Schedule (Simple)

This is the simplest possible KEDA demo. We will use the Cron scaler to
automatically scale a Deployment up and down based on a time schedule.

No external systems like message queues are needed. Just a Deployment and a
ScaledObject.

### Use Case

Imagine you have a web application that gets heavy traffic during business hours
(9 AM to 6 PM) and almost no traffic at night. You want to:
- Run 5 replicas during business hours
- Scale down to 0 replicas at night

### Step 1: Create the Deployment

Save this as deployment.yaml or use the file provided in the demo-1-cron folder:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cron-demo-app
  namespace: default
spec:
  replicas: 0
  selector:
    matchLabels:
      app: cron-demo-app
  template:
    metadata:
      labels:
        app: cron-demo-app
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "100m"
              memory: "128Mi"
```

Apply it:
```
kubectl apply -f demo-1-cron/deployment.yaml
```

Check the pods:
```
kubectl get pods
```

You should see 0 pods because we set replicas to 0.

### Step 2: Create the ScaledObject with Cron Trigger

Save this as scaled-object.yaml or use the file provided in the demo-1-cron folder:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: cron-scaled-object
  namespace: default
spec:
  scaleTargetRef:
    name: cron-demo-app
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
    - type: cron
      metadata:
        timezone: Asia/Kolkata
        start: "0 9 * * *"
        end: "0 18 * * *"
        desiredReplicas: "5"
```

Let us break down the ScaledObject:

- scaleTargetRef.name: The name of the Deployment to scale (cron-demo-app).
- minReplicaCount: The minimum number of replicas (0 means scale to zero is enabled).
- maxReplicaCount: The maximum number of replicas allowed.
- triggers: The list of event sources.
  - type: cron means we are using the Cron scaler.
  - timezone: The timezone for the cron schedule.
  - start: When to scale up (0 9 * * * means 9:00 AM every day).
  - end: When to scale down (0 18 * * * means 6:00 PM every day).
  - desiredReplicas: How many replicas to run during the active window.

Apply it:
```
kubectl apply -f demo-1-cron/scaled-object.yaml
```

### Step 3: Verify

Check the ScaledObject:
```
kubectl get scaledobject
```

Check the pods:
```
kubectl get pods
```

If the current time is between 9 AM and 6 PM (in the timezone you specified),
you will see 5 pods running. If it is outside that window, you will see 0 pods.

Check the HPA that KEDA created:
```
kubectl get hpa
```

You will see an HPA created by KEDA for the cron-demo-app Deployment.

### Quick Test Tip

If you do not want to wait for 9 AM, change the start and end times to be around
your current time. For example, if it is 2:30 PM, use:

```
start: "0 14 * * *"    # 2:00 PM
end: "0 15 * * *"      # 3:00 PM
```

This way the scale up happens immediately and you can see it in action.

### Cleanup

```
kubectl delete -f demo-1-cron/scaled-object.yaml
kubectl delete -f demo-1-cron/deployment.yaml
```

---

## 6. Demo 2 - Scaling Based on RabbitMQ Queue Length (Real World)

This is a more realistic demo. We will:
- Deploy RabbitMQ in the cluster
- Deploy a consumer application that processes messages from a queue
- Create a KEDA ScaledObject that watches the queue length
- Publish messages to the queue and watch KEDA scale the consumer up
- Stop publishing and watch KEDA scale the consumer back to zero

### Use Case

You have an order processing system. Orders arrive as messages in a RabbitMQ queue.
A consumer application picks up messages and processes them. When there are many
orders, you need more consumer pods. When the queue is empty, you want zero pods
to save resources.

### Step 1: Deploy RabbitMQ

Save this as rabbitmq.yaml or use the file in the demo-2-rabbitmq folder:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rabbitmq
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
        - name: rabbitmq
          image: rabbitmq:3-management
          ports:
            - containerPort: 5672
              name: amqp
            - containerPort: 15672
              name: management
          env:
            - name: RABBITMQ_DEFAULT_USER
              value: "guest"
            - name: RABBITMQ_DEFAULT_PASS
              value: "guest"
          resources:
            requests:
              cpu: "200m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: default
spec:
  selector:
    app: rabbitmq
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
    - name: management
      port: 15672
      targetPort: 15672
```

Apply it:
```
kubectl apply -f demo-2-rabbitmq/rabbitmq.yaml
```

Wait for RabbitMQ to be running:
```
kubectl get pods -l app=rabbitmq
```

Wait until the pod shows STATUS as Running.

### Step 2: Deploy the Consumer Application

This is a simple Python application that connects to RabbitMQ, reads messages
from a queue called "orders", and processes them (just prints and sleeps to
simulate work).

Save the consumer code and Dockerfile in the demo-2-rabbitmq folder:

consumer.py:
```python
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
```

Dockerfile:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install pika
COPY consumer.py .
CMD ["python", "consumer.py"]
```

Build and load the image into KIND:
```
cd demo-2-rabbitmq
docker build -t order-consumer:latest .
kind load docker-image order-consumer:latest --name keda-demo
cd ..
```

Now deploy the consumer:

consumer-deployment.yaml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-consumer
  namespace: default
spec:
  replicas: 0
  selector:
    matchLabels:
      app: order-consumer
  template:
    metadata:
      labels:
        app: order-consumer
    spec:
      containers:
        - name: consumer
          image: order-consumer:latest
          imagePullPolicy: Never
          env:
            - name: RABBITMQ_HOST
              value: "rabbitmq"
            - name: QUEUE_NAME
              value: "orders"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "200m"
              memory: "256Mi"
```

Apply it:
```
kubectl apply -f demo-2-rabbitmq/consumer-deployment.yaml
```

Notice replicas is set to 0. No consumer pods are running yet. KEDA will start
them when messages arrive in the queue.

### Step 3: Create the TriggerAuthentication and ScaledObject

scaled-object.yaml:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secret
  namespace: default
type: Opaque
stringData:
  host: "amqp://guest:guest@rabbitmq.default.svc.cluster.local:5672/"
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: rabbitmq-trigger-auth
  namespace: default
spec:
  secretTargetRef:
    - parameter: host
      name: rabbitmq-secret
      key: host
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-consumer-scaled-object
  namespace: default
spec:
  scaleTargetRef:
    name: order-consumer
  minReplicaCount: 0
  maxReplicaCount: 10
  pollingInterval: 5
  cooldownPeriod: 30
  triggers:
    - type: rabbitmq
      metadata:
        queueName: orders
        mode: QueueLength
        value: "5"
      authenticationRef:
        name: rabbitmq-trigger-auth
```

Let us break down this ScaledObject:

- scaleTargetRef.name: The Deployment to scale (order-consumer).
- minReplicaCount: 0 means scale to zero when the queue is empty.
- maxReplicaCount: 10 means never run more than 10 consumer pods.
- pollingInterval: 5 means KEDA checks the queue every 5 seconds.
- cooldownPeriod: 30 means after the queue is empty, wait 30 seconds before
  scaling down. This prevents rapid up/down flapping.
- trigger type: rabbitmq tells KEDA to use the RabbitMQ scaler.
- queueName: orders is the name of the queue to watch.
- mode: QueueLength means scale based on how many messages are in the queue.
- value: "5" means for every 5 messages, KEDA will add one more pod.
  So 10 messages = 2 pods, 25 messages = 5 pods, 50 messages = 10 pods (capped at max).
- authenticationRef: Points to the TriggerAuthentication which has the connection
  details for RabbitMQ.

Apply it:
```
kubectl apply -f demo-2-rabbitmq/scaled-object.yaml
```

### Step 4: Verify Initial State

```
kubectl get scaledobject
kubectl get pods -l app=order-consumer
```

You should see the ScaledObject is active but 0 consumer pods because the queue
is empty.

### Step 5: Publish Messages to the Queue

We will use a publisher script that sends messages to the queue.

publisher.py:
```python
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
```

Build and load the publisher image:
```
cd demo-2-rabbitmq
docker build -t order-publisher:latest -f Dockerfile.publisher .
kind load docker-image order-publisher:latest --name keda-demo
cd ..
```

Dockerfile.publisher:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install pika
COPY publisher.py .
ENTRYPOINT ["python", "publisher.py"]
CMD ["50"]
```

Run the publisher as a Kubernetes Job to send 50 messages:
```
kubectl apply -f demo-2-rabbitmq/publisher-job.yaml
```

publisher-job.yaml:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: order-publisher
  namespace: default
spec:
  template:
    spec:
      containers:
        - name: publisher
          image: order-publisher:latest
          imagePullPolicy: Never
          args: ["50"]
          env:
            - name: RABBITMQ_HOST
              value: "rabbitmq"
      restartPolicy: Never
  backoffLimit: 1
```

### Step 6: Watch KEDA Scale the Consumer

Open a new terminal and watch the pods:
```
kubectl get pods -w
```

Within a few seconds (remember pollingInterval is 5 seconds), you will see KEDA
start creating consumer pods.

With 50 messages and a threshold of 5 messages per pod, KEDA will scale up to
10 pods (50 / 5 = 10, and maxReplicaCount is 10).

You can also watch the HPA:
```
kubectl get hpa -w
```

And check the ScaledObject:
```
kubectl describe scaledobject order-consumer-scaled-object
```

### Step 7: Watch KEDA Scale Down to Zero

As the consumers process messages, the queue gets smaller. KEDA will gradually
reduce the number of pods. Once the queue is completely empty, KEDA will wait
for the cooldownPeriod (30 seconds) and then scale the Deployment down to zero.

You can watch this happen in the terminal running:
```
kubectl get pods -w
```

Eventually, all consumer pods will be terminated and you are back to 0 replicas,
saving resources.

### Summary of What Happened

1. We started with 0 consumer pods (no waste).
2. We published 50 messages to the queue.
3. KEDA detected the messages within 5 seconds.
4. KEDA scaled the consumer from 0 to 10 pods.
5. The consumers processed all 50 messages.
6. The queue became empty.
7. KEDA scaled the consumer back down to 0 pods.

This is the power of event driven autoscaling.

### Cleanup

```
kubectl delete -f demo-2-rabbitmq/publisher-job.yaml
kubectl delete -f demo-2-rabbitmq/scaled-object.yaml
kubectl delete -f demo-2-rabbitmq/consumer-deployment.yaml
kubectl delete -f demo-2-rabbitmq/rabbitmq.yaml
```

To delete the KIND cluster entirely:
```
kind delete cluster --name keda-demo
```

---

## Key Takeaways

1. The default Kubernetes HPA only scales based on CPU and Memory. It cannot
   understand external events like queue lengths or custom metrics.

2. KEDA fills this gap. It connects Kubernetes to external event sources and
   scales your workloads based on real demand.

3. KEDA can scale to zero. This saves money when there is no work to do.

4. KEDA does not replace the HPA. It works with it. KEDA handles 0 to 1 and
   1 to 0. The HPA handles 1 to N.

5. KEDA is lightweight and safe. It only affects the Deployments you configure
   it for. Everything else in your cluster stays untouched.

6. KEDA supports 60 plus scalers out of the box, including RabbitMQ, Kafka,
   AWS SQS, Prometheus, Cron, MySQL, Redis, and many more.

---

## Quick Reference - Common KEDA Commands

```
# Check KEDA pods
kubectl get pods -n keda

# List all ScaledObjects
kubectl get scaledobject --all-namespaces

# Describe a ScaledObject
kubectl describe scaledobject <name>

# Check the HPA created by KEDA
kubectl get hpa

# Check KEDA operator logs
kubectl logs -n keda -l app=keda-operator

# List all ScaledJobs
kubectl get scaledjob --all-namespaces
```
