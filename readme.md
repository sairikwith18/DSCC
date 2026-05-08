# Custom Distributed Load Balancer with Intelligent API Gateway

This project implements a dynamic, application-layer load balancer and API Gateway deployed across multiple AWS EC2 instances. It was designed using the PEDALS framework (Performance, Elasticity, Dependability, Availability, Latency, Scalability).

## Architecture overview
* **Frontend:** A lightweight dashboard that allows users to send specific workload types (Query vs. Upload).
* **Control Plane (API Gateway):** Acts as the reverse proxy. It contains an **Aggregator Service** that pings worker nodes to build a live Latency Matrix (tracking RTT and CPU load) and a **Selector Service** that makes intelligent routing decisions.
* **Worker Nodes (S1 & S2):** Independent Flask microservices processing the workloads and returning health metrics via `psutil`.

## Routing Logic
1. **Query Requests:** Routed to the server with the lowest Round-Trip Time (RTT) to prioritize network speed.
2. **Upload Requests:** Routed to the server with the lowest CPU load to prioritize computational power.
3. **Fault Tolerance:** If a node goes offline, the Gateway detects the timeout, updates the matrix, and automatically reroutes traffic to the healthy nodes without dropping the client connection.