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
import threading

app = Flask(__name__)

# Global storage for the daily report
DAILY_LOG = []

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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        self.history = []
        self.last_checked = None

    def add_history(self, latency_ms):
        self.history.append(latency_ms)
        self.last_checked = datetime.now()
        if len(self.history) > 30:
            self.history.pop(0)

    @property
    def name(self): raise NotImplementedError()
    @property
    def status_url(self): raise NotImplementedError()
    @property
    def home_url(self): return self.status_url
    @property
    def icon(self): return "fas fa-server"
    def get_status(self): raise NotImplementedError()

    def get_detailed_stats(self):
        data = self.history if self.history else [0]
        avg_resp = round(sum(data) / len(data), 2)
        min_resp = min(data)
        max_resp = max(data)
        uptime_7d = 100.0 if random.random() > 0.1 else 99.8
        uptime_30d = 99.99
        uptime_365d = 99.95
        last_check_str = self.last_checked.strftime("%H:%M:%S") if self.last_checked else "Just now"
        
        incidents = []
        if random.random() > 0.8:
             incidents.append({
                 "status": "Resolved",
                 "cause": "High Latency in US-East",
                 "started": (datetime.now() - timedelta(days=2)).strftime("%b %d, %H:%M"),
                 "duration": "14m"
             })

        # --- Generate Mock Nested Components ---
        components = []
        
        # Define structure with optional sub-components
        service_structure = {
            'Amazon Web Services': [
                {'name': 'Elastic Compute Cloud (EC2)', 'subs': ['Region: us-east-1', 'Region: eu-west-1', 'API Endpoint', 'Management Console']},
                {'name': 'Simple Storage Service (S3)', 'subs': ['Standard Storage', 'Glacier', 'Transfer Acceleration']},
                {'name': 'RDS', 'subs': ['MySQL', 'PostgreSQL', 'Aurora']},
                {'name': 'CloudFront', 'subs': []},
                {'name': 'Route 53', 'subs': ['DNS Queries', 'Health Checks', 'Domain Registration']}
            ],
            'Google Cloud': [
                {'name': 'Compute Engine', 'subs': ['VM Instances', 'Disks', 'Images']},
                {'name': 'Cloud Storage', 'subs': ['Multi-Regional', 'Regional', 'Nearline']},
                {'name': 'Kubernetes Engine', 'subs': ['Cluster Management', 'API Server']}
            ],
            'Microsoft Azure': [
                {'name': 'Virtual Machines', 'subs': ['Windows VMs', 'Linux VMs']},
                {'name': 'Azure SQL Database', 'subs': ['Database Engine', 'Connectivity']},
                {'name': 'Blob Storage', 'subs': []}
            ],
            'Atlassian': [
                {'name': 'Jira Software', 'subs': ['Issue Tracking', 'Boards', 'Backlog']},
                {'name': 'Confluence', 'subs': ['Pages', 'Editor', 'Comments']},
                {'name': 'Bitbucket', 'subs': ['Git over HTTPS', 'Git over SSH', 'Pull Requests']}
            ]
        }

        # Default for others
        defaults = [{'name': 'API', 'subs': []}, {'name': 'Dashboard', 'subs': []}, {'name': 'Database', 'subs': ['Read Replicas', 'Write Master']}]
        
        structure = service_structure.get(self.name, defaults)
        
        for item in structure:
            # Parent Status
            p_status = "Operational"
            if random.random() > 0.95: p_status = "Maintenance"
            
            children = []
            for sub_name in item['subs']:
                c_status = "Operational"
                if p_status != "Operational": 
                    c_status = p_status # Inherit issues
                elif random.random() > 0.98: 
                    c_status = "Partial Outage"
                
                children.append({
                    "name": sub_name,
                    "status": c_status
                })
            
            components.append({
                "name": item['name'],
                "status": p_status,
                "children": children
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
            "components": components
        }

class StatusPagePlugin(Service):
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            b = BeautifulSoup(r.content, 'html.parser')
            page_status = b.find(class_=['status', 'index'])
            if not page_status:
                if "All Systems Operational" in r.text: return Status.ok
                return Status.unavailable
            status_classes = page_status.attrs.get('class', [])
            status = next((x for x in status_classes if x.startswith('status-')), None)
            if status == 'status-none': return Status.ok
            elif status == 'status-critical': return Status.critical
            elif status == 'status-major': return Status.major
            elif status == 'status-minor': return Status.minor
            elif status == 'status-maintenance': return Status.maintenance
            else: return Status.unavailable
        except Exception as e: return Status.unavailable

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
            if "Service is operating normally" in r.text or "status0.gif" in r.text: return Status.ok
            elif "status1.gif" in r.text: return Status.ok
            elif "status2.gif" in r.text: return Status.minor
            elif "status3.gif" in r.text: return Status.critical
            return Status.ok 
        except: return Status.unavailable

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
        except: return Status.unavailable

class GCloud(Service):
    name = 'Google Cloud'
    status_url = 'https://status.cloud.google.com/'
    icon = "fab fa-google"
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "Available" in r.text or "No incidents" in r.text: return Status.ok
            return Status.ok 
        except: return Status.unavailable

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
        except: return Status.unavailable

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
        except: return Status.unavailable

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
        except: return Status.unavailable

SERVICES = [AWS(), GCloud(), GitHub(), Azure(), Atlassian(), Cloudflare(), Slack(), Docker()]
SERVICE_MAP = {s.name: s for s in SERVICES}

def get_mock_incident(service_name):
    now_str = datetime.now().strftime("%b %d, %Y %I:%M %p")
    templates = [
        {"title": f"Minor Incident", "desc": f"Investigating - We are currently investigating an issue affecting connectivity to {service_name}. Users may experience sporadic errors."},
        {"title": f"{service_name} Service Disruption", "desc": "Monitoring - We have detected elevated error rates. Engineering teams are actively working on a fix to restore normal service operation."},
        {"title": "Transaction Search Delay", "desc": "Update - Indexing for recent transactions is delayed by approximately 15 minutes. Data integrity is not affected."}
    ]
    incident = random.choice(templates)
    return {"title": incident["title"], "description": incident["desc"], "timestamp": f"Last update on {now_str}"}

def check_single_service(service):
    start_time = time.time()
    status = service.get_status()
    end_time = time.time()
    latency_ms = int((end_time - start_time) * 1000)
    service.add_history(latency_ms)
    
    incident_data = None
    if status != Status.ok:
        incident_data = get_mock_incident(service.name)

    return {
        'name': service.name,
        'url': service.status_url,
        'icon': service.icon,
        'status': status,
        'incident': incident_data,
        'history': service.history
    }

def generate_excel_file():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    results.sort(key=lambda x: x['name'])
    data = []
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in results:
        status_name = r['status'].name.upper() if r['status'] else "UNKNOWN"
        data.append({"Service Name": r['name'], "Status URL": r['url'], "Current Status": status_name, "Report Timestamp": report_time})
    df = pd.DataFrame(data)
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

# ==========================================
# BACKGROUND SCHEDULER FOR DAILY REPORT
# ==========================================
def background_scheduler():
    """Runs every 15 minutes to snapshot all services."""
    print("Background Scheduler Started...")
    while True:
        now = datetime.now()
        
        # Reset log at midnight
        if now.hour == 0 and now.minute < 15 and len(DAILY_LOG) > 90:
            DAILY_LOG.clear()
            print("Daily Log Reset for new day.")

        # Calculate seconds until next 15 minute interval
        # Intervals: 00, 15, 30, 45
        next_minute = (now.minute // 15 + 1) * 15
        if next_minute == 60:
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=next_minute, second=0, microsecond=0)
        
        delay = (next_time - now).total_seconds()
        time.sleep(delay)
        
        # --- Run Checks ---
        print(f"Running Scheduled Check at {datetime.now().strftime('%H:%M:%S')}")
        snapshot = {
            "timestamp": datetime.now().strftime("%H:%M"),
            "services": {}
        }
        
        # We don't use ThreadPool here to avoid race conditions with the main app pool, 
        # and speed isn't critical for background task
        for service in SERVICES:
            try:
                # Direct check, not updating 'history' to keep UI sparklines separate if needed, 
                # but checking 'get_status' triggers a real request.
                # To strictly follow 'not affected by page reloading', we do a fresh check.
                status = service.get_status()
                snapshot["services"][service.name] = status.name.upper()
            except:
                snapshot["services"][service.name] = "UNKNOWN"
        
        DAILY_LOG.append(snapshot)
        # Sleep a bit to avoid double execution in the same second
        time.sleep(2)

# Start the background thread
threading.Thread(target=background_scheduler, daemon=True).start()

# ==========================================
# FLASK ROUTES
# ==========================================

@app.route('/')
def index():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    results.sort(key=lambda x: x['name'])
    return render_template('index.html', services=results, Status=Status)

@app.route('/monitoring')
def monitoring():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    sort_map = {
        Status.critical: 0,
        Status.major: 1,
        Status.minor: 2,
        Status.unavailable: 3,
        Status.maintenance: 4,
        Status.ok: 5
    }
    results.sort(key=lambda x: (sort_map.get(x['status'], 6), x['name']))
    total = len(results)
    running = sum(1 for r in results if r['status'] == Status.ok)
    issues = total - running
    return render_template('monitoring.html', services=results, Status=Status, total=total, running=running, issues=issues)

@app.route('/service/<name>')
def service_detail(name):
    service = SERVICE_MAP.get(name)
    if not service: abort(404)
    live_data = check_single_service(service)
    return render_template('service_detail.html', service=service, status=live_data['status'], stats=service.get_detailed_stats(), Status=Status)

@app.route('/download_report')
def download_report():
    output, filename = generate_excel_file()
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/download_daily_report')
def download_daily_report():
    """Generates Excel from the background DAILY_LOG"""
    if not DAILY_LOG:
        # Return empty or error if no data yet
        return "No daily data collected yet. Please wait for the next 15-minute interval.", 404

    # Transform Data for DataFrame
    # Goal: Rows = 12:00, 12:15... | Cols = Service Names
    
    # 1. Extract unique timestamps and service names
    data = []
    for entry in DAILY_LOG:
        row = {"Time": entry["timestamp"]}
        row.update(entry["services"])
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # Write to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Daily 24h Report')
        worksheet = writer.sheets['Daily 24h Report']
        # Auto-width
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len

    output.seek(0)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"Daily_Report_{date_str}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/get_report_text')
def get_report_text():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    results.sort(key=lambda x: x['name'])
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for r in results:
        status_str = r['status'].name.upper() if r['status'] else "UNKNOWN"
        rows.append({"name": r['name'], "status": status_str, "time": report_time})
    if rows:
        max_name = max(len(r["name"]) for r in rows)
        max_status = max(len(r["status"]) for r in rows)
    else: max_name = 10; max_status = 10
    w_name = max(len("Service Name"), max_name) + 5
    w_status = max(len("Status"), max_status) + 5
    lines = [f"{'Service Name'.ljust(w_name)}{'Status'.ljust(w_status)}Timestamp", "-" * (w_name + w_status + 20)]
    for row in rows: lines.append(f"{row['name'].ljust(w_name)}{row['status'].ljust(w_status)}{row['time']}")
    return jsonify({"body": "\n".join(lines)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)