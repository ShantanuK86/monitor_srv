import requests
from bs4 import BeautifulSoup
from enum import Enum
import concurrent.futures
from flask import Flask, render_template, abort, send_file, request, jsonify, flash, redirect, url_for
import time
import random
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import threading
import os
import json

app = Flask(__name__)
app.secret_key = 'supersecretkey' # Required for flashing messages

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

        components = []
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
        defaults = [{'name': 'API', 'subs': []}, {'name': 'Dashboard', 'subs': []}, {'name': 'Database', 'subs': ['Read Replicas', 'Write Master']}]
        structure = service_structure.get(self.name, defaults)
        
        for item in structure:
            p_status = "Operational"
            if random.random() > 0.95: p_status = "Maintenance"
            children = []
            for sub_name in item['subs']:
                c_status = "Operational"
                if p_status != "Operational": c_status = p_status
                elif random.random() > 0.98: c_status = "Partial Outage"
                children.append({"name": sub_name, "status": c_status})
            components.append({"name": item['name'], "status": p_status, "children": children})
        
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

def background_scheduler():
    print("Background Scheduler Started...")
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute < 15 and len(DAILY_LOG) > 90:
            DAILY_LOG.clear()
            print("Daily Log Reset for new day.")
        next_minute = (now.minute // 15 + 1) * 15
        if next_minute == 60:
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=next_minute, second=0, microsecond=0)
        delay = (next_time - now).total_seconds()
        time.sleep(delay)
        print(f"Running Scheduled Check at {datetime.now().strftime('%H:%M:%S')}")
        snapshot = {"timestamp": datetime.now().strftime("%H:%M"), "services": {}}
        for service in SERVICES:
            try:
                status = service.get_status()
                snapshot["services"][service.name] = status.name.upper()
            except:
                snapshot["services"][service.name] = "UNKNOWN"
        DAILY_LOG.append(snapshot)
        time.sleep(2)

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
    sort_map = {Status.critical: 0, Status.major: 1, Status.minor: 2, Status.unavailable: 3, Status.maintenance: 4, Status.ok: 5}
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
    if not DAILY_LOG: return "No daily data collected yet. Please wait for the next 15-minute interval.", 404
    data = []
    for entry in DAILY_LOG:
        row = {"Time": entry["timestamp"]}
        row.update(entry["services"])
        data.append(row)
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Daily 24h Report')
        worksheet = writer.sheets['Daily 24h Report']
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
    if rows: max_name = max(len(r["name"]) for r in rows); max_status = max(len(r["status"]) for r in rows)
    else: max_name = 10; max_status = 10
    w_name = max(len("Service Name"), max_name) + 5
    w_status = max(len("Status"), max_status) + 5
    lines = [f"{'Service Name'.ljust(w_name)}{'Status'.ljust(w_status)}Timestamp", "-" * (w_name + w_status + 20)]
    for row in rows: lines.append(f"{row['name'].ljust(w_name)}{row['status'].ljust(w_status)}{row['time']}")
    return jsonify({"body": "\n".join(lines)})

# --- NEW DASHBOARD ROUTES ---

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('dashboard'))
    
    if file:
        try:
            # Determine file type and read
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                flash('Invalid file type. Please upload CSV or Excel.')
                return redirect(url_for('dashboard'))
            
            # --- DATA PROCESSING ---
            
            # 1. Clean Column Names (strip whitespace, lower case)
            df.columns = [c.strip().lower() for c in df.columns]
            
            # 2. Parse Dates
            # Format: YYYY-MM-DD THH:MM:SS.000Z (User specified space between date and time?)
            # We'll try flexible parsing first, then specific if needed.
            for col in ['creationtime', 'recentreporttime']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

            # 3. Extract Unique Filter Values
            services_list = sorted(df['services'].unique().astype(str).tolist()) if 'services' in df.columns else []
            stages_list = sorted(df['stage'].unique().astype(str).tolist()) if 'stage' in df.columns else []
            states_list = sorted(df['state'].unique().astype(str).tolist()) if 'state' in df.columns else []

            # 4. Prepare Global Stats (Total Revenue etc.)
            # Since the user didn't provide columns for Revenue/Sales, we'll simulate/derive or count
            # If there are no revenue columns, we can count incidents instead for "Total Revenue" placeholder or rename it.
            # Given the image has $1250.00, New Customers etc., I will calculate:
            # - Total Incidents (Active Accounts placeholder)
            # - Open vs Closed (Growth Rate placeholder)
            
            stats = {
                "total_incidents": len(df),
                "open_incidents": len(df[df['state'] == 'open']) if 'state' in df.columns else 0,
                "closed_incidents": len(df[df['state'] == 'closed']) if 'state' in df.columns else 0,
                "prod_incidents": len(df[df['stage'] == 'prd']) if 'stage' in df.columns else 0
            }

            # 5. Serialize for Frontend
            # We convert Timestamp objects to string ISO format for JSON serialization
            records = df.to_dict(orient='records')
            for r in records:
                for k, v in r.items():
                    if isinstance(v, (pd.Timestamp, datetime)):
                        r[k] = v.isoformat()

            return render_template('dashboard.html', 
                                   records=records, 
                                   services=services_list, 
                                   stages=stages_list, 
                                   states=states_list,
                                   stats=stats,
                                   filename=file.filename)

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('dashboard'))

@app.route('/hardware_list')
def hardware_list():
    global LATEST_HARDWARE_DATA
    
    # Load default static file if no data exists
    if not LATEST_HARDWARE_DATA:
        try:
            # Check if file exists, otherwise load from string (simulating repo file)
            default_csv = "hardware.csv"
            if os.path.exists(default_csv):
                df = pd.read_csv(default_csv)
            else:
                # Fallback if file isn't physically on disk in this env
                from io import StringIO
                csv_content = """sample_no,model_code,id,hwduid,country,year,type,name,local_set,pno,slot,vendor,sn,location,user,project
1,MBP-16-2023,1001,HWD-001,USA,2023,Laptop,MacBook Pro,US-HQ,P-101,A1,Apple,C02G1234ABCD,New York,John Doe,Project Alpha
2,DELL-XPS-15,1002,HWD-002,UK,2022,Laptop,Dell XPS 15,UK-Branch,P-102,B2,Dell,DL-5678EFGH,London,Jane Smith,Project Beta
3,HP-ZBOOK,1003,HWD-003,Germany,2021,Workstation,HP ZBook,DE-Office,P-103,C3,HP,HP-9012IJKL,Berlin,Hans Mueller,Project Gamma
4,CISCO-RTR,1004,HWD-004,France,2020,Router,Cisco ISR 4000,FR-Site,P-104,D4,Cisco,CS-3456MNOP,Paris,Network Team,Infrastructure Upgrade
5,LEN-TP-X1,1005,HWD-005,Japan,2023,Laptop,ThinkPad X1 Carbon,JP-Hub,P-105,E5,Lenovo,LN-7890QRST,Tokyo,Sato Tanaka,Project Delta
6,SRV-DELL-R740,1006,HWD-006,USA,2019,Server,Dell PowerEdge R740,US-DC,P-106,R1-U10,Dell,DL-SERVER-001,New York,IT Ops,Data Center Refresh
7,MON-DELL-27,1007,HWD-007,Canada,2022,Monitor,Dell Ultrasharp 27,CA-Office,P-107,D1,Dell,DL-MON-007,Toronto,Emily White,Project Epsilon
8,IPAD-PRO-12,1008,HWD-008,Australia,2023,Tablet,iPad Pro 12.9,AU-Branch,P-108,M1,Apple,AP-TAB-008,Sydney,Chris Green,Field Operations"""
                df = pd.read_csv(StringIO(csv_content))

            # Clean columns
            df.columns = [c.strip().lower().replace(' ', '_').replace('/', '_').replace('.', '') for c in df.columns]
            
            records = df.fillna('').to_dict(orient='records')
            LATEST_HARDWARE_DATA = {
                'records': records,
                'filename': 'hardware_list.csv (Default)',
                'columns': df.columns.tolist()
            }
        except Exception as e:
            print(f"Error loading default hardware list: {e}")
            
    return render_template('hardware_list.html', **LATEST_HARDWARE_DATA)

@app.route('/upload_hardware_file', methods=['POST'])
def upload_hardware_file():
    global LATEST_HARDWARE_DATA
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('hardware_list'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('hardware_list'))
    
    if file:
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                flash('Invalid file type. Please upload CSV or Excel.')
                return redirect(url_for('hardware_list'))
            
            df.columns = [c.strip().lower().replace(' ', '_').replace('/', '_').replace('.', '') for c in df.columns]
            records = df.fillna('').to_dict(orient='records')
            
            LATEST_HARDWARE_DATA = {
                'records': records,
                'filename': file.filename,
                'columns': df.columns.tolist()
            }
            
            return render_template('hardware_list.html', **LATEST_HARDWARE_DATA)

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('hardware_list'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)