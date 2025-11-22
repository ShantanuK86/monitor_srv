import requests
from bs4 import BeautifulSoup
from enum import Enum
import concurrent.futures
from flask import Flask, render_template, abort
import time
import random
from datetime import datetime, timedelta

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

    # --- New Method: Generate Mock History Data for the Dashboard ---
    def get_detailed_stats(self):
        """
        Since we don't have a database, we simulate historical data 
        to populate the dashboard UI requested.
        """
        # 1. Mock Response Times (last 30 points)
        response_times = [random.randint(20, 150) for _ in range(30)]
        # Add a random spike
        response_times[random.randint(0, 29)] = random.randint(300, 800)
        
        # 2. Mock Uptime Stats
        uptime_7d = 100.0 if random.random() > 0.2 else 99.8
        uptime_30d = 99.99
        uptime_365d = 99.95

        # 3. Mock Incidents
        incidents = []
        if random.random() > 0.7:
             incidents.append({
                 "status": "Resolved",
                 "cause": "High Latency in US-East",
                 "started": (datetime.now() - timedelta(days=2)).strftime("%b %d, %H:%M"),
                 "duration": "14m"
             })
        
        return {
            "response_times": response_times,
            "avg_response": round(sum(response_times) / len(response_times), 2),
            "min_response": min(response_times),
            "max_response": max(response_times),
            "uptime_7d": uptime_7d,
            "uptime_30d": uptime_30d,
            "uptime_365d": uptime_365d,
            "last_check": "26 seconds ago",
            "incidents": incidents
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
    """Helper to run in thread"""
    return {
        'name': service.name,
        'url': service.status_url,
        'icon': service.icon,
        'status': service.get_status()
    }

@app.route('/')
def index():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    results.sort(key=lambda x: x['name'])
    return render_template('index.html', services=results, Status=Status)

@app.route('/service/<name>')
def service_detail(name):
    # Find the service object
    service = SERVICE_MAP.get(name)
    if not service:
        abort(404)
    
    # Get real-time status
    current_status = service.get_status()
    
    # Get mock data for dashboard visualization
    stats = service.get_detailed_stats()
    
    return render_template(
        'service_detail.html', 
        service=service, 
        status=current_status,
        stats=stats,
        Status=Status
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)