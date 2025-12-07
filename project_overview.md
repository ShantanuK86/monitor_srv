Project Overview: isServiceUp - Service Monitoring & Incident Dashboard

1. Project Purpose

This project is a comprehensive Service Status Monitoring and Incident Management Dashboard. It is designed to track the health of various cloud services (AWS, Azure, Google Cloud, GitHub, etc.), display real-time status updates, provide historical trend analysis, and allow for the management of hardware inventory. The application mimics the functionality of status pages like Atlassian Statuspage but adds custom features like file-based reporting and a hardware inventory system.

2. Core Architecture

Framework: Python Flask web framework.

Concurrency: Uses concurrent.futures.ThreadPoolExecutor to perform parallel network requests for checking service statuses, ensuring the dashboard loads quickly despite multiple external API calls.

Data Persistence (Simulated):

In-Memory Storage: Global variables (DAILY_LOG, LATEST_DASHBOARD_DATA, LATEST_HARDWARE_DATA) are used to persist state between requests during the runtime of the application.

File-Based: Uploaded CSV/Excel files are processed and stored in memory to drive dashboard visualizations.

Background Tasks: A background thread (background_scheduler) runs intervals (every 15 minutes) to snapshot service health for daily reporting.

3. Key Features & Functionality

A. Main Dashboard (Service Monitoring) - index.html

Real-time Status Checks: Scrapes or queries status pages for AWS, Azure, GCP, etc.

Parallel Execution: Checks 8+ services simultaneously using 10 worker threads.

Smart Refresh:

Dynamic dropdown for auto-refresh intervals (Off, 2m, 15m).

State is persisted in localStorage so settings survive page reloads.

Incident Alerting:

"Experiencing Issues" Banner: A collapsible accordion that appears only when services are not "Operational".

Details: Shows specific incident titles, descriptions, and timestamps (mocked for demo purposes).

Service List:

Displays services in a clean list format with status icons.

Modal Detail View: Clicking a service opens a modal with:

Weekly Trend Chart: A bar chart showing incident counts over the last 3 months.

Sub-services List: A nested list of components (e.g., EC2, S3) with their own statuses.

B. Analytics Dashboard - dashboard.html

Data Ingestion: Accepts CSV/Excel uploads containing incident logs.

Required Schema: services, state (open, closed, inprogress), stage (stg, prd), creationtime, recentreporttime.

Dynamic Filtering:

Date Range: Flatpickr-based calendar filter.

Dropdowns: Filter by Service Name, Stage, and Issue State.

Search: Text-based search for service names.

KPI Cards:

Total Incidents: Aggregate count.

Open Issues: Count of currently active issues.

Stage Breakdown: Visual bar showing Prod vs. Staging ratio.

Closed Issues: Count of resolved incidents.

Interactive Charts:

Trend Chart: A Chart.js bar chart showing incident volume over time.

Stacked/Grouped: Supports Daily, Weekly, and Monthly views.

Service Breakdown Grid:

Cards for each service showing individual sparklines (7-day and 30-day trends).

Pagination (8 cards per page).

C. Hardware Inventory - hardware_list.html

Inventory Management: Displays a list of hardware assets.

CRUD Operations:

Upload: Bulk upload via CSV/Excel.

Edit: Inline editing of table rows.

Delete: Remove individual rows.

Customization: A "Columns" dropdown allows users to toggle the visibility of specific table columns dynamically.

4. UI/UX Design System

Theme: Strict Dark Mode (bg-dark-900) using Tailwind CSS.

Color Palette:

Backgrounds: Slate/Gray scale (#0d1117, #161b22, #21262d).

Status Colors:

Green (text-green-400): Operational/Closed.

Yellow (text-yellow-400): Minor/In Progress.

Red (text-red-400): Critical/Open.

Blue (text-blue-400): Maintenance/Staging.

Components:

Glassmorphism: Used in navbars and sticky headers (backdrop-blur-md).

Modals: Centralized popups for details and uploads.

Sparklines: SVG-based mini charts generated via JavaScript path logic (no external library for sparklines).

5. API & Data Handling

Endpoints:

GET /: Main monitoring view.

GET /dashboard: Analytics view.

POST /upload_file: Processes incident logs, normalizes dates to ISO 8601, and calculates initial stats.

GET /get_report_text: Generates a text/clipboard summary of current statuses.

POST /update_hardware_row & POST /delete_hardware_row: JSON-based API for inventory management.

Date Handling: Critical reliance on ISO 8601 (YYYY-MM-DDTHH:MM:SS.000Z). The backend enforces UTC conversion to prevent filtering errors on the frontend.

Mocking: get_mock_incident simulates realistic failure scenarios (titles, descriptions) when live scraping isn't possible or for demonstration.

6. Libraries Used

Backend: Flask, pandas, requests, beautifulsoup4, openpyxl.

Frontend: Tailwind CSS (via CDN), Chart.js (Visualizations), Flatpickr (Date/Time selection), FontAwesome (Icons).

7. Instructions for Recreation

To recreate this project:

Initialize a standard Flask app structure.

Implement the Service base class and subclasses for specific providers (AWS, Azure, etc.) with scraping logic.

Use ThreadPoolExecutor for the main index route to ensure speed.

Build the templates using the provided Tailwind color config to ensure the specific "Dark Mode" aesthetic.

Implement the Javascript filtering logic on the client side for the Dashboard to allow instant interactivity without server round-trips for every filter change.