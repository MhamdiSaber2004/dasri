# DASRI

Industrial ERP for DASRI Waste Management based on Odoo 18 Community Edition.

This repository is structured to host more than one application:

- `dasri/`: Odoo addon
- `mobile/`: future mobile application

## Overview

This project is a specialized Industrial ERP designed to manage the full life cycle of medical waste (DASRI - Dechets d'Activites de Soins a Risques Infectieux). Developed for Ingenius IT, the system focuses on traceability, regulatory compliance, and operational efficiency.

## Key Features

### Contract and Compliance Management

- Manage healthcare facility contracts with pricing by weight, trip, or mixed mode.
- Capture real hospital signatures on contracts and bordereaux.
- Lock signed records to preserve legal and operational integrity.

### Logistics and Field Operations

- Plan collection missions by zone, vehicle, and driver.
- Generate and track DASRI bordereaux through operational statuses.
- Follow client sites, mission stops, and route execution.

### Industrial Processing and Warehousing

- Record gross, tare, and net weights with discrepancy tracking.
- Integrate reception flows with Odoo stock operations.
- Track treatment operations through incineration and processing units.

### Billing and Analytics

- Generate monthly invoices from validated bordereaux.
- Monitor KPIs such as collected weight, trips, missions, and estimated revenue.
- Produce PDF reports for contracts, missions, bordereaux, reception, treatment, and KPI summaries.

## Tech Stack

- Framework: Odoo 18 Community Edition
- Backend: Python
- Frontend: XML / QWeb
- Database: PostgreSQL
- OS: Linux

## Repository Structure

```text
.
├── dasri/
│   ├── models/
│   ├── views/
│   ├── security/
│   ├── data/
│   ├── reports/
│   └── static/
└── mobile/   # planned later
```

## Odoo Installation

1. Clone this repository.
2. Copy or link the `dasri/` addon folder into your Odoo `custom_addons` path.
3. Ensure required dependencies are available in Odoo: `mail`, `fleet`, `hr`, `stock`, `account`.
4. Update `odoo.conf` and install or upgrade the module from Apps.

## Roles

- Hospital representative: signs contracts and bordereaux
- Planner: manages schedules and zones
- Driver: executes collection missions
- Reception officer: validates weight and storage
- Treatment officer: oversees processing and disposal

## Supervision

- Mme Naweel Nakkai (ISET)
- M. Alaa Abidi (Ingenius IT)
