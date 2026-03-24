Industrial ERP for DASRI Waste Management
Based on Odoo 18 Community Edition
This project is a specialized Industrial ERP designed to manage the full life cycle of Medical Waste (DASRI - Déchets d’Activités de Soins à Risques Infectieux). Developed for Ingenius IT, the system ensures traceability, regulatory compliance, and operational efficiency for healthcare waste management companies.

🚀 Key Features
📄 Contract & Compliance Management
Digital Contracts: Manage healthcare facility contracts with automated pricing (per weight, per trip, or mixed).

Electronic Signatures: Integrated signature widget for hospitals to sign contracts and manifests (Bordereaux) directly in the system.

Legal Locking: Automatic record locking post-signature to ensure data integrity.

🚛 Logistics & Field Operations
Route Planning: Manage collection missions by geographic zones, assigned vehicles, and drivers.

Real-time Tracking: Driver-led workflow (Draft -> In Progress -> Done) with integrated GPS/Location support.

Bordereau Tracking: Automated generation of DASRI manifests with visual status alerts (Green/Red/Grey).

🏭 Industrial Processing & Warehousing
Weight Management: Precise tracking of Gross/Tare/Net weights with automated discrepancy (Ecart) detection.

Inventory Integration: Seamless link with Odoo's stock.picking for real-time waste storage monitoring.

Treatment Monitoring: Track waste processing through specialized incineration units and treatment steps.

💰 Automated Billing & Analytics
Smart Invoicing: Monthly automated billing wizards based on actual collected quantities or scheduled trips.

KPI Dashboards: Real-time operational and financial insights (Waste volume by zone, treatment efficiency, revenue).

PDF Reporting: Professional, regulatory-compliant reports for every stage of the process.

🛠 Tech Stack
Framework: Odoo 18 Community Edition

Backend: Python

Frontend: XML (Odoo QWeb), JavaScript (OWL)

Database: PostgreSQL

OS Support: Linux (Ubuntu/Debian)

📂 Module Structure
Plaintext
dasri/
├── models/             # Business Logic (Contracts, Missions, Reception, etc.)
├── views/              # UI Layouts (Forms, Trees, Kanbans, Dashboards)
├── security/           # Access Rights (ir.model.access.csv) & Groups
├── data/               # Demo Data & Sequential Numbering
├── reports/            # PDF QWeb Report Templates
└── wizards/            # Multi-step assistants for Invoicing
🛠 Installation & Setup
Clone this repository into your Odoo custom_addons folder.

Ensure dependencies (mail, fleet, stock, account) are installed.

Update your odoo.conf to include the path.

Restart Odoo and install the DASRI Management module from the Apps menu.

👥 Roles & Permissions
Hospital Admin: Signs contracts and manifests.

Planner: Manages schedules and zones.

Driver: Executes missions and performs field validation.

Warehouse Manager: Validates weight and storage.

Treatment Officer: Oversees incineration and disposal.

Supervised by: Mme Naweel Nakkai (ISET) & M. Alaa Abidi (Ingenius IT)
