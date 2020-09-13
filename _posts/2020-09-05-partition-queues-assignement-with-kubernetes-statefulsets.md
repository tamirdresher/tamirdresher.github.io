---
layout: post
title: "Distributed balanced partition-queues assignment using Kubernetes statefulSet"
date: 2020-09-05
---
Partitioning a domain is a useful way to achieve scalability of a system. The idea behind partitioning is that instead of putting everything in a single place, you divide the dataset or the work into multiple places based on some attribute, which is usually the identifier of the entity.

The division allows us to spread the storage and/or the processing to multiple machines or containers, and allows the horizontal scaling we were seeking to get.

One of the requirements that you might need to fulfill in a partitioned environment is to have a single master consumer per each partition. This is usually needed to achieve consistency and an ordered execution.

For example, if the system you are working on involves financial data, it makes perfect  sense to process all the transactions related to a specific account in the order they were registered.

Messaging systems such as Kafka, AWS Kinesis, Azure Event-Hub and Apache Pulsar make it very easy to create a system where each partition is only consumed by a single consumer (as long as the consumers are in the same consumer group).

With Kafka, AWS Kinesis and Azure Event Hub, the partition assignment is done using a cooperative algorithm executed by the clients. This process is called rebalance (you can read how Kafka is doing it [here](https://www.confluent.io/blog/incremental-cooperative-rebalancing-in-kafka/) and how Azure Event Hub is doing it [here](https://docs.microsoft.com/en-us/azure/event-hubs/event-processor-balance-partition-load )
  
I thought it would be an interesting academic exercise to implement a simpler partition assignment protocol that fits nicely in a Kubernetes hosted environment with a non-partitioned messaging system such as RabbitMQ where each partition will represented by a simple queue.

All the code related to this post can be found here: [https://github.com/tamirdresher/DistributedBalancedPartitionQueueAssignment](https://github.com/tamirdresher/DistributedBalancedPartitionQueueAssignment)  

## Balanced Distributed Resource Allocation

In a generalized way, the problem we are trying to solve is how to allocate resources in a distributed system where each resource can only be used by a single process and the resource distribution is balanced between those processes. For example, if the system has 10 license keys and we have 4 processes that need to use these licenses, we want the first 3 processes to use 2 licenses, and the fourth process to use only 4 licenses.

This is a challenging problem to solve because we need to take into account that the number of processes/nodes can change.

1. we can scale up or scale down the system based on load
2. A failure can happen at any time and processes become unreachable  

Also, we need to make sure that even if the number of processes (consumers from here on) changes, no resource will be used by two consumers in parallel.  

## Kubernetes statefulSets

In Kubernetes, a statefulSet is a type of deployment strategy that maintains a sticky identity and storage for each of the Pods.
statefulSet were designed to host a stateful application such as databases or persisted cache that need to maintains their state across restarts and reschedules. 
The nice thing about a statefulSet is that every pod is assigned an integer ordinal index, from 0 up through N-1, which is unique over the set.
When a pod crashes or is rescheduled, Kubernetes will take of all of complexity of reviving it and reassign it to the correct identity.
When scaling down the statefulSet, for example from 5 to 3 replicas, Kubernetes will terminate the last two pods in the set.
  

These attributes of the statefulSet make it easier for us to implement our solution.

  

## Implementing the Partition Queues Assignement with StatefulSet

Suppose we have a system that works with a traditional message broker such as RabbitMQ, ActiveMQ, SQS, Azure Storage Queues or alike.
We have a queue named "OrderEvents" that holds events about orders we wish to partition to P partitions.
To do that we create new queues, one per partition, with the name "OrderEvents-Px" where Px is the partition id.
Here is how the statefulSet.yaml looks in the demo application (after helm hydrated the template file with values)

```
apiVersion: apps/v1
kind: StatefulSet

metadata:
  name: consumer
  labels:
    app: consumer
    chart: consumer-0.1.0
    draft: draft-app
    release: balancedpartitions
    heritage: Helm
spec:
  revisionHistoryLimit: 0
  replicas: 2
  selector:
    matchLabels:
      app: consumer
      release: balancedpartitions
  serviceName: consumer
  template:
    metadata:
      labels:
        app: consumer
        draft: draft-app
        release: balancedpartitions
      annotations:
        buildID: ""
    spec:
      containers:
        - name: consumer
          image: "consumer:latest"
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 80
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health/readiness
              port: http
          readinessProbe:
            httpGet:
              path: /health/liveness
              port: http
          env:
            - name: STATEFULSET_NAME
              value: consumer
            - name: STATEFULSET_NAMESPACE
              value: default
            - name: PartitionCount
              value: "3"
            - name: PartitionQueuePrefix
              value: OrderEvents
            - name: RMQHost
              value: rabbitmq
          resources:
            {}
```
The important pieces here are that the _kind_ attribute was set to _StatefulSet_ and that the amount of replicas was set to 2. Also, I'm setting several environment variables so the consumer will know the prefix for the queues and how many partitions exist.  

From the producer standpoint it's easy. For each order, take the orderId, hash it, calculate the hash modulo the partition count and send it to the appropriate queue.
```
public void Publish(int orderId, string eventDescription)
{
    IModel rabbitChannel = _channelLazy.Value;
    var hashed = _hasher.ComputeHash(Encoding.UTF8.GetBytes(orderId.ToString()));
    var partition = BitConverter.ToUInt32(hashed, 0) % _configuration.PartitionCount;

    string queue = _configuration.PartitionQueuePrefix + partition; 

    string message = $"OrderId: {orderId}, Description: {eventDescription}";
    var body = Encoding.UTF8.GetBytes(message);

    rabbitChannel.BasicPublish(exchange: "",
                         routingKey: queue,
                         basicProperties: null,
                         body: body);
}
```
Note: For simplicity, I only did a naive hash and modulo. a better approach would be to use a consistent hash algorithm.  

Now the tricky part is to make each consumer connect to the correct queue.
If every consumer in our system knows it's unique integer ID, the amount of partitions and the total amount of consumers, the problem become easier to solve.
We can divide the amount of partitions by the number of consumers and each consumer will take its fraction (the last one will take the remainder if the division is not even)

This is the how the code looks:
```
int consumerId = ...
int parititionCount = ...
int assignableConsumerCount = Math.Min(consumerCount, parititionCount); //we can't assign more consumers that partitions
if (consumerId >= assignableConsumerCount)
{    
    return Enumerable.Empty<int>();
}

var partitionsPerConsumer = Math.DivRem(parititionCount, assignableConsumerCount, out var remainder);
var partitionsStart = consumerId * partitionsPerConsumer;
var amountOfPartitionsToTake = partitionsPerConsumer + (IsLastConsumer(consumerCount, consumerId) ? remainder : 0);

var newPartitions = Enumerable.Range(partitionsStart, amountOfPartitionsToTake);   
```

That's simple enough, but from where do we take these parameters?

The partition count can be injected through configuration so that's straightforward, but for the consumer id and consumer count we need to work a little more tight with Kubernetes.  

### Resolving the consumer ID and consumer count
#### consumer ID

When Kubernetes schedule a pod as part of statefulSet, it assigns its hostname in this format: $(statefulset name)-$(ordinal)

So, if we want to get the consumerId all we need to do is to strip the statefuleSet name from the hostname  

```
var idStr = Environment.MachineName.Replace($"{_statefulSetName}-", "");
var consumerId = int.Parse(idStr);
```
Note: the extraction can also be made outside of the code and as part of the container init script (https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
  
#### consumer count
The number of consumers is controlled by Kubernetes, by setting the number of replicas in the statefulSet manifest file or by simply running this command in the CLI

```
kubectl scale statefulsets <stateful-set-name> --replicas=<new-replicas>
```  

So we have two options
1. The consumer application will read the value directly from Kubernetes
2. Run an external process that will be triggered periodically or by some event to read the value from Kubernetes, then store it in persistent storage and notify the consumers
  
For the simplicity of this exercise, I decided to periodically read the value directly from Kubernetes using the [KubernetesClient](]https://www.nuget.org/packages/KubernetesClient/) package.

```
KubernetesClientConfiguration config = null;
if (IsHostedInKubernetes)
{
    config = KubernetesClientConfiguration.InClusterConfig();
}
else
{
    // don't forget to run 'kubectl proxy'
    config = new KubernetesClientConfiguration { Host = "http://127.0.0.1:8001" };
}

using (var client = new Kubernetes(config))
{
    var scale = await client.ReadNamespacedStatefulSetScaleAsync(_statefulSetName, _statefulSetNamespace);
    return scale.Spec.Replicas;
}
```

## Taking ownership on the queue

Now that each consumer knows what partitions are assigned to it, it makes sense for the consumer to subscribe to the queue and start pulling messages from it, but unfortunately things are not that simple.

Imagine the scenario where a consumer was reading messages from one of the queues and starts processing them, and before finishing, the number of replicas increased.

The new consumer that is now assigned to the queue can start processing messages while another consumer is still processing the old messages.

In systems where the order of processing is important (you don't want to process the update event before you finished processing the insert event for example) you need to make sure that you always have a single consumer for the queue.

### Distributed lock
The most common way to ensure that there is only one process using a resource is to use a Distributed Lock.    
There are several mechanisms you can use, here are some:
1.  [AWS DynamoDB Lock Client](https://aws.amazon.com/blogs/database/building-distributed-locks-with-the-dynamodb-lock-client/)
2.  [Azure Blob Lease operation](https://docs.microsoft.com/en-us/rest/api/storageservices/lease-blob)
3.  [ZooKeeper Lock](https://zookeeper.apache.org/doc/r3.1.2/recipes.html#sc_recipes_Locks)
4.  [Redis Redlock](https://redis.io/topics/distlock)
5. Database based lock such as [PotgreSQL Advisory Lock](https://www.postgresql.org/docs/12/explicit-locking.html#ADVISORY-LOCKS)
  

The idea is not complex. Before the consumer connects to the queue, it tries to take a hold of the distributed lock, and the ownership is revoked, the consumer frees the lock.

This makes sure that even if the new owner was faster than the previous owner, there won't be a risk of parallel execution on the same entity.
 

### RabbitMQ Single Active Consumer (SAC)
Because this whole exercise started with the question of how we can assign RabbitMQ queues to a set of consumers, it's only natural to try and leverage RabbitMQ capabilities.

The [Single Active Consumer](https://www.rabbitmq.com/consumers.html#single-active-consumer) mode allows to have only one consumer at a time consuming from a queue and to fail over to another registered consumer in case the active one is cancelled or dies.

This is a perfect fit to our problem. I can let the new consumer subscribe to the queue and rest assured that only after the previous consumer finishes, messages will start to flow to the new one.

Here is how the consumer code that handles a single partition looks like:

```
_channel.QueueDeclare(queue: _queue,
               durable: true,
               exclusive: false,
               autoDelete: false,
               arguments: new Dictionary<string, object> { { "x-single-active-consumer", true } });


_consumer = new EventingBasicConsumer(_channel);
_consumer.Received += (model, ea) =>
{
    var body = ea.Body.ToArray();
    var message = Encoding.UTF8.GetString(body);
    _logger.LogInformation(" [x] Received {0}", message);
    _channel.BasicAck(ea.DeliveryTag, false);
};
_channel.BasicConsume(queue: _queue,
                     autoAck: false,
                     consumer: _consumer);

```
Note that when the queue is declared, I pass the _x-single-active-consumer_ argument

# Summary
I hope you found this post interesting. I'm not sure yet if I'll get the chance to use this technique in a real production environment but it was fun solving.
You can find the code in my github [https://github.com/tamirdresher/DistributedBalancedPartitionQueueAssignment](https://github.com/tamirdresher/DistributedBalancedPartitionQueueAssignment) 

