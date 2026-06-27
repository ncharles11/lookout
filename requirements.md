# **Functional and Technical Specifications**

## **Project: Lookout \-Monitoring & Alerting Platform for Small Infrastructures**

This document defines the functional, technical, and security specifications for the development of a monitoring tool *self-hosted*. The goal is to design an ultra-lightweight, "zero configuration" and visually impactful solution capable of monitoring the health of servers, containers and APIs for small teams.

## **1\. Project Objectives**

* **To watch** the health status of modestly sized infrastructures (CPU, RAM, Disk, container statuses, API uptime).  
* **Alert** intelligently in case of failure, while avoiding alert fatigue (anti-noise).  
* **Offer a turnkey deployment** drastically limiting the barrier to technical entry (installation via a simple command).  
* **To serve as a high-flying technical showcase** demonstrating mastery of asynchronous architectures, temporal data processing and complex interface design, with a view to obtaining a permanent Software Engineer position by November 2026\.

## **2\. Functional Specifications**

### **2.1. Metrics Collection and Health Checks**

The system must be able to acquire data according to two distinct paradigms:

* **Mode Pull (Blackbox) :** The central server makes periodic pings (HTTP/TCP) to target services to measure the response time (latency) and validate the status code (e.g., 200 OK).  
* **Mode Push (Whitebox) :** An ultra-light agent, capable of running on classic servers as well as constrained environments (such as Raspberry Pi), sends system metrics (CPU, RAM, disk usage, Docker process status) to the central server.

### **2.2. Intelligent Alerting Motor (Anti-Flapping)**

**Strict business rule:** The system must not spam communication channels during micro-interruptions or oscillations around a threshold.

* **Sliding window mechanism:** An alertCRITICALis only triggered if the failure condition is maintained over a defined number of cycles (e.g., 3 consecutive failures) or a fixed duration.  
* **Resolution hysteresis:** The threshold for returning to normal (RESOLVED) must be different from the alert threshold (e.g., Alert if CPU \> 90%, Resolution if CPU \< 85% for 1 minute).  
* **Distribution channels:** Notifications via Webhooks (Discord, Slack, Telegram) and emails (SMTP).

### **2.3. Dashboard and Real-Time Visualization (UI/UX)**

* **Design System :** The interface is HUD-oriented, adopting a cyberpunk and minimalist aesthetic with a strong dark theme. The graphics must be fluid and legible at a glance.  
* **Real Time:** State changes (e.g., a server going offline) must be pushed instantly to the frontend via WebSockets, without requiring a page refresh.  
* **Zero Configuration:** Unlike complex solutions, the user does not configure their charts. Dashboards are pre-defined, optimized, and automatically generated as soon as a service is detected.

## **3\. Technical Specifications & Architecture**

### **3.1. Stack Technique**

* **Backend / Central Server:** Python 3.11+ with the framework**FastAPI**(for its native handling of asynchronicity and WebSockets).  
* **Collection Agent:** Lightweight Python script (usingpsutil And docker-py) executed as a daemon.  
* **Frontend :** **React** or **Next.js** with **TypeScript** and Tailwind CSS (for rapid prototyping of the HUD interface).  
* **Temporal database:** **TimescaleDB** (PostgreSQL extension) to centralize both relational data (users, configurations) and time series (metrics) in a single container.  
* **Conteneurisation :** Docker and Docker Compose.

### **3.2. Software Architecture**

| Component | Main Role | Communication |
| :---- | :---- | :---- |
| **Agent distant** | Collects the host system state and lists the containers. | HTTP POST requests to the Backend. |
| **Backend (FastAPI)** | Health check scheduler, REST API, rules engine, WebSocket management. | HTTP (REST) \+ WebSockets (WS). |
| **Database** | Persistent storage, time indexing, aggressive retention (automatic cleaning). | SQL queries optimized for timescale. |
| **Client Web (SPA)** | API consumption and responsive visual rendering. | HTTP \+ Listening WS. |

## **4\. Endpoint Specifications (Excerpt)**

The API must adhere to REST standards, clearly expose its collection and delivery routes, and include self-generated OpenAPI documentation.

| Method | Route | Description | Context |
| :---- | :---- | :---- | :---- |
| WS | /ws/v1/dashboard | WebSocket stream pushing the consolidated state of the infrastructure in real time. | Dashboard UI |
| POST | /api/v1/metrics/push | Receiving metrics sent by remote agents. | Agent distant |
| GET | /api/v1/services/status | Paginated list of the current status of all monitored services. | Dashboard UI |
| POST | /api/v1/config/services | Adding a new URL or target server to monitor. | Admin |
| POST | /api/v1/alerts/test | Manually triggering a notification to validate webhooks (Slack/Discord). | Admin |

## **5\. Security and Resilience Requirements**

### **5.1. Security of Exchanges**

* **Agent Authentication:** Each agent must authenticate themselves with the central server via a *Bearer Token* (static API key) generated during initial setup.  
* **UI Security:** Access to the dashboard is protected by session or JWT authentication, and stored securely.  
* **Rate Limiting :** Protection of public API endpoints (including metric reception) to avoid saturating the database in case of a runaway faulty agent.

### **5.2. Data Lifecycle Management**

* **Retention :** Implementation of a strict retention policy via native TimescaleDB features (e.g. aggregation of data older than 24 hours, permanent deletion of raw metrics older than 7 days) to ensure that the database never saturates the user's disk.

## **6\. Testing and Deployment Strategy**

### **6.1. Code Quality and Testing**

* **Unit Tests:** Strict validation of the anti-flapping engine and state transitions (UP \-\> WARNING \-\> CRITICAL).  
* **Mocking :** Simulation of failing or slow HTTP endpoints to test the asynchronous behavior of the FastAPI collector.

### **6.2. Deployment (The major advantage)**

* **One-Line Installer :** The complete installation of the central server (Backend \+ Database \+ Compiled Frontend) must fit in a single filedocker-compose.yml.  
* The launch command required by the end user must be limited to:docker compose up \-d.

