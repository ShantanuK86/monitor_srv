import requests
from bs4 import BeautifulSoup
from enum import Enum
import concurrent.futures
from flask import Flask, render_template, abort, send_file, request, jsonify
import time
import random
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO

app = Flask(__name__)

# ==========================================
# 1. MODELS & CLASSES
# ==========================================

class Status(Enum):
    ok = 1              # green
    maintenance = 2     # blue
    minor = 3           # yellow
    major = 4           # orange
    critical = 5        # red
    unavailable = 6     # gray

class Service(object):
    def __init__(self):
        # Fake user agent to prevent 403 Forbidden errors
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        # Store response time history (in ms)
        self.history = []
        self.last_checked = None

    def add_history(self, latency_ms):
        """Add a new response time to history and maintain max size"""
        self.history.append(latency_ms)
        self.last_checked = datetime.now()
        # Keep only last 30 data points
        if len(self.history) > 30:
            self.history.pop(0)

    @property
    def name(self):
        raise NotImplementedError()

    @property
    def status_url(self):
        raise NotImplementedError()
    
    @property
    def home_url(self):
        return self.status_url

    @property
    def icon(self):
        # Returning a FontAwesome class or Emoji
        return "fas fa-server"

    def get_status(self):
        raise NotImplementedError()

    # --- Real History Data for Dashboard ---
    def get_detailed_stats(self):
        # Use actual history data
        data = self.history if self.history else [0]
        
        # Calculate real stats
        avg_resp = round(sum(data) / len(data), 2)
        min_resp = min(data)
        max_resp = max(data)

        # Mock Uptime Stats (Persistent long-term data requires DB)
        uptime_7d = 100.0 if random.random() > 0.1 else 99.8
        uptime_30d = 99.99
        uptime_365d = 99.95
        
        # Format last check time
        last_check_str = self.last_checked.strftime("%H:%M:%S") if self.last_checked else "Just now"
        
        # Mock Incidents
        incidents = []
        if random.random() > 0.8:
             incidents.append({
                 "status": "Resolved",
                 "cause": "High Latency in US-East",
                 "started": (datetime.now() - timedelta(days=2)).strftime("%b %d, %H:%M"),
                 "duration": "14m"
             })

        # --- Generate Mock Components based on Service Name ---
        components = []
        component_map = {
            'Amazon Web Services': [
                'Amazon Elastic Compute Cloud (EC2)', 
                'Amazon Chime', 
                'Amazon CloudFront', 
                'Amazon Elastic Container Registry Public', 
                'AWS Billing Console',
                'Amazon Simple Storage Service (S3)',
                'AWS Lambda'
            ],
            'Google Cloud': [
                'Google Compute Engine',
                'Google App Engine',
                'Google Cloud Storage', 
                'Google Kubernetes Engine',
                'Google BigQuery',
                'Google Cloud Functions',
                'Google Cloud Pub/Sub'
            ],
            'Microsoft Azure': [
                'Azure Virtual Machines',
                'Azure App Service', 
                'Azure SQL Database', 
                'Azure Blob Storage', 
                'Azure Active Directory',
                'Azure DevOps',
                'Azure Cosmos DB'
            ],
            'GitHub': ['Git Operations', 'API Requests', 'Webhooks', 'Issues', 'Pull Requests', 'Actions'],
            'Atlassian': ['Jira Software', 'Confluence', 'Bitbucket', 'Trello', 'StatusPage'],
            'Slack': ['Messaging', 'Calls', 'File Uploads', 'Notifications', 'Search', 'Login/SSO'],
            'Docker': ['Docker Hub', 'Docker Desktop', 'Image Registry', 'Authentication'],
            'Cloudflare': ['CDN', 'DNS', 'Edge Workers', 'API', 'WAF']
        }

        # Get relevant components or default ones
        names = component_map.get(self.name, ['API', 'Web Dashboard', 'Database', 'Third-party Integrations'])
        
        for comp_name in names:
            # Mostly OK, small chance of issue
            status = "Operational"
            if random.random() > 0.95:
                status = "Partial Outage" if random.random() > 0.5 else "Maintenance"
            
            components.append({
                "name": comp_name,
                "status": status
            })
        
        return {
            "response_times": data,
            "avg_response": avg_resp,
            "min_response": min_resp,
            "max_response": max_resp,
            "uptime_7d": uptime_7d,
            "uptime_30d": uptime_30d,
            "uptime_365d": uptime_365d,
            "last_check": last_check_str,
            "incidents": incidents,
            "components": components  # <--- Added components list
        }

class StatusPagePlugin(Service):
    """Generic plugin for Atlassian StatusPage based sites"""
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            b = BeautifulSoup(r.content, 'html.parser')
            page_status = b.find(class_=['status', 'index'])
            
            if not page_status:
                if "All Systems Operational" in r.text:
                    return Status.ok
                return Status.unavailable

            status_classes = page_status.attrs.get('class', [])
            status = next((x for x in status_classes if x.startswith('status-')), None)

            if status == 'status-none':
                return Status.ok
            elif status == 'status-critical':
                return Status.critical
            elif status == 'status-major':
                return Status.major
            elif status == 'status-minor':
                return Status.minor
            elif status == 'status-maintenance':
                return Status.maintenance
            else:
                return Status.unavailable
        except Exception as e:
            print(f"Error checking {self.name}: {e}")
            return Status.unavailable

# ==========================================
# 2. SERVICE IMPLEMENTATIONS
# ==========================================

class Atlassian(StatusPagePlugin):
    name = 'Atlassian'
    status_url = 'https://status.atlassian.com/'
    icon = "fab fa-jira"

class Cloudflare(StatusPagePlugin):
    name = 'Cloudflare'
    status_url = 'https://www.cloudflarestatus.com/'
    icon = "fab fa-cloudflare"

class AWS(Service):
    name = 'Amazon Web Services'
    status_url = 'https://status.aws.amazon.com/'
    icon = "fab fa-aws"

    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "Service is operating normally" in r.text or "status0.gif" in r.text:
                return Status.ok
            elif "status1.gif" in r.text: return Status.ok
            elif "status2.gif" in r.text: return Status.minor
            elif "status3.gif" in r.text: return Status.critical
            return Status.ok 
        except:
            return Status.unavailable

class Azure(Service):
    name = 'Microsoft Azure'
    status_url = 'https://azure.microsoft.com/en-us/status/'
    icon = "fab fa-microsoft"

    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            b = BeautifulSoup(r.content, 'html.parser')
            text = r.text.lower()
            if 'fewer than 3' in text or 'good' in text: return Status.ok
            
            div = str(b.select_one('.section'))
            if 'health-warning' in div: return Status.minor
            elif 'health-error' in div: return Status.critical
            return Status.ok
        except:
            return Status.unavailable

class GCloud(Service):
    name = 'Google Cloud'
    status_url = 'https://status.cloud.google.com/'
    icon = "fab fa-google"

    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "Available" in r.text or "No incidents" in r.text: return Status.ok
            return Status.ok 
        except:
            return Status.unavailable

class GitHub(Service):
    name = 'GitHub'
    status_url = 'https://www.githubstatus.com/'
    icon = "fab fa-github"

    def get_status(self):
        try:
            r = requests.get('https://www.githubstatus.com/api/v2/status.json', headers=self.headers, timeout=5)
            data = r.json()
            indicator = data.get('status', {}).get('indicator')
            if indicator == 'none': return Status.ok
            elif indicator == 'minor': return Status.minor
            elif indicator == 'major': return Status.major
            elif indicator == 'critical': return Status.critical
            elif indicator == 'maintenance': return Status.maintenance
            else: return Status.ok
        except:
            return Status.unavailable

class Slack(Service):
    name = 'Slack'
    status_url = 'https://status.slack.com/'
    icon = "fab fa-slack"

    def get_status(self):
        try:
            r = requests.get('https://slack-status.com/api/v2.0.0/current', headers=self.headers, timeout=5)
            data = r.json()
            if data.get('status') == 'ok': return Status.ok
            
            active_incidents = data.get('active_incidents', [])
            if not active_incidents: return Status.ok

            for incident in active_incidents:
                i_type = incident.get('type', '').lower()
                if i_type == 'incident': return Status.major
                if i_type == 'maintenance': return Status.maintenance
            
            return Status.minor
        except:
            return Status.unavailable

class Docker(Service):
    name = 'Docker'
    status_url = 'https://status.docker.com/'
    icon = "fab fa-docker"
    
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "All Systems Operational" in r.text: return Status.ok
            elif "Incident" in r.text: return Status.major
            return Status.unavailable
        except:
            return Status.unavailable

# ==========================================
# 3. FLASK ROUTES
# ==========================================

SERVICES = [
    AWS(),
    GCloud(),
    GitHub(),
    Azure(),
    Atlassian(),
    Cloudflare(),
    Slack(),
    Docker()
]

# Helper map to find service by name
SERVICE_MAP = {s.name: s for s in SERVICES}

def check_single_service(service):
    """
    Runs the check, measures latency, and updates history.
    Returns the status dictionary for the UI.
    """
    start_time = time.time()
    
    # 1. Perform the actual network request
    status = service.get_status()
    
    end_time = time.time()
    
    # 2. Calculate latency in milliseconds
    latency_ms = int((end_time - start_time) * 1000)
    
    # 3. Save to memory
    service.add_history(latency_ms)
    
    return {
        'name': service.name,
        'url': service.status_url,
        'icon': service.icon,
        'status': status
    }

def generate_excel_file():
    """Helper to generate the Excel file buffer"""
    # 1. Fetch current status data (this triggers latency updates too)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    results.sort(key=lambda x: x['name'])

    # 2. Prepare data for Excel
    data = []
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for r in results:
        status_name = r['status'].name.upper() if r['status'] else "UNKNOWN"
        data.append({
            "Service Name": r['name'],
            "Status URL": r['url'],
            "Current Status": status_name,
            "Report Timestamp": report_time
        })

    # 3. Create DataFrame
    df = pd.DataFrame(data)

    # 4. Write to BytesIO buffer
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Status Report')
        worksheet = writer.sheets['Status Report']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len

    output.seek(0)
    filename = f"Status_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return output, filename

@app.route('/')
def index():
    results = []
    # This loop refreshes all services and updates their history every time index loads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    results.sort(key=lambda x: x['name'])
    return render_template('index.html', services=results, Status=Status)

@app.route('/service/<name>')
def service_detail(name):
    service = SERVICE_MAP.get(name)
    if not service:
        abort(404)
    
    # Perform a live check when opening the details to get the very latest point
    # We re-use check_single_service so latency is recorded
    live_data = check_single_service(service)
    current_status = live_data['status']
    
    # Now fetch the stats which includes the history we just updated
    stats = service.get_detailed_stats()
    
    return render_template(
        'service_detail.html', 
        service=service, 
        status=current_status,
        stats=stats,
        Status=Status
    )

@app.route('/download_report')
def download_report():
    output, filename = generate_excel_file()
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/get_report_text')
def get_report_text():
    """Generates a table-formatted text summary for the clipboard"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    results.sort(key=lambda x: x['name'])
    
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Prepare data for formatting
    rows = []
    for r in results:
        status_enum = r['status']
        status_str = status_enum.name.upper() if status_enum else "UNKNOWN"
        rows.append({
            "name": r['name'],
            "status": status_str,
            "time": report_time
        })

    # Calculate max column widths
    if rows:
        max_name = max(len(r["name"]) for r in rows)
        max_status = max(len(r["status"]) for r in rows)
    else:
        max_name = 10
        max_status = 10
        
    # Add padding
    w_name = max(len("Service Name"), max_name) + 5
    w_status = max(len("Status"), max_status) + 5
    
    # Build Table Lines
    lines = []
    
    # Header Row
    header = f"{'Service Name'.ljust(w_name)}{'Status'.ljust(w_status)}Timestamp"
    lines.append(header)
    lines.append("-" * len(header))
    
    # Data Rows
    for row in rows:
        line = f"{row['name'].ljust(w_name)}{row['status'].ljust(w_status)}{row['time']}"
        lines.append(line)
    
    return jsonify({
        "body": "\n".join(lines)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)