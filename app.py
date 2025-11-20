import requests
from bs4 import BeautifulSoup
from enum import Enum
import concurrent.futures
from flask import Flask, render_template
import time

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

class StatusPagePlugin(Service):
    """Generic plugin for Atlassian StatusPage based sites"""
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            b = BeautifulSoup(r.content, 'html.parser')
            page_status = b.find(class_=['status', 'index'])
            
            if not page_status:
                # Fallback if the specific class isn't found
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
    name = 'Atlassian Jira'
    status_url = 'https://jira-software.status.atlassian.com/'
    icon = "fab fa-jira"

class Cloudflare(StatusPagePlugin):
    name = 'Cloudflare'
    status_url = 'https://www.cloudflarestatus.com/'
    icon = "fab fa-cloudflare"



class Confluence(Service):
    name = "Atlassian Confluence"
    status_url = "https://confluence.status.atlassian.com/api/v2/status.json"
    components_url = "https://confluence.status.atlassian.com/api/v2/components.json"
    icon = "fab fa-confluence"

    def get_status(self):
        try:
            r = requests.get(self.status_url, timeout=5)
            status_data = r.json()
            indicator = status_data.get("indicator", "").lower()
            
            # Map the indicator to your Status enum
            if indicator == "none":
                return Status.ok
            if indicator == "minor":
                return Status.minor
            if indicator in ["major", "critical"]:
                return Status.critical

            # Fallback: check components
            cr = requests.get(self.components_url, timeout=5)
            comps = cr.json().get("components", [])
            for c in comps:
                st = c.get("status", "")
                if st in ["major_outage", "partial_outage"]:
                    return Status.critical
                if st == "degraded_performance":
                    return Status.minor

            return Status.ok
        except Exception:
            return Status.unavailable


class AWS(Service):
    name = 'Amazon Web Services'
    status_url = 'https://status.aws.amazon.com/'
    icon = "fab fa-aws"

    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "Service is operating normally" in r.text or "status0.gif" in r.text or "No recent issues" in r.text:
                return Status.ok
            elif "status1.gif" in r.text: # Informational
                return Status.ok
            elif "status2.gif" in r.text:
                return Status.minor
            elif "status3.gif" in r.text:
                return Status.critical
            return Status.ok # AWS page is tricky, default to ok if reachable
        except:
            return Status.unavailable

class Azure(Service):
    name = "Microsoft Azure"
    status_url = "https://azure.status.microsoft/en-us/status"
    icon = "fab fa-microsoft"

    def get_status(self):
        try:
            r = requests.get(self.status_url, timeout=5)
            soup = BeautifulSoup(r.text, "html.parser")

            text = soup.get_text(" ", strip=True).lower()

            if "all services are healthy" in text or "no active events" in text:
                return Status.ok
            if "degradation" in text or "service advisory" in text:
                return Status.minor
            if "outage" in text or "unavailable" in text:
                return Status.critical

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
            b = BeautifulSoup(r.content, 'html.parser')
            
            # Look for the main status indicator
            if "Available" in r.text or "No incidents" in r.text:
                return Status.ok
            
            # Logic from prompt
            try:
                status_bar = b.find(class_='subheader')
                if status_bar:
                    status = next(x for x in status_bar.attrs['class'] if x.startswith('open-incident-bar-'))
                    if status == 'open-incident-bar-clear': return Status.ok
                    elif status == 'open-incident-bar-medium': return Status.major
                    elif status == 'open-incident-bar-high': return Status.critical
            except:
                pass
            
            return Status.ok # Default to OK if no obvious error found
        except:
            return Status.unavailable


class Slack(Service):
    name = 'Slack'
    status_url = 'https://status.slack.com/'
    icon = "fab fa-slack"

    def get_status(self):
        try:
            # Using the Slack Status API v2.0.0 as requested
            r = requests.get('https://slack-status.com/api/v2.0.0/current', headers=self.headers, timeout=5)
            data = r.json()
            
            # 1. Check the global status field
            if data.get('status') == 'ok':
                return Status.ok
            
            # 2. If not OK, check active incidents to determine severity
            active_incidents = data.get('active_incidents', [])
            
            if not active_incidents:
                # Status says not ok, but no public incidents listed? 
                # Assume minor issue or just cleared.
                return Status.ok

            # Priority: Critical/Major > Maintenance > Minor
            found_maintenance = False
            
            for incident in active_incidents:
                i_type = incident.get('type', '').lower()
                
                # If we find a confirmed incident, return Major immediately
                if i_type == 'incident':
                    return Status.major
                
                if i_type == 'maintenance':
                    found_maintenance = True
            
            if found_maintenance:
                return Status.maintenance
                
            # specific fallback if there are incidents but unknown type
            return Status.minor

        except Exception as e:
            print(f"Slack API Error: {e}")
            return Status.unavailable


class GitHub(Service):
    name = 'GitHub'
    status_url = 'https://www.githubstatus.com/'
    icon = "fab fa-github"

    def get_status(self):
        try:
            r = requests.get('https://www.githubstatus.com/api/v2/status.json', headers=self.headers, timeout=5)
            data = r.json()
            # API v2 returns: {"status": {"indicator": "none", "description": "..."}}
            indicator = data.get('status', {}).get('indicator')
            
            if indicator == 'none':
                return Status.ok
            elif indicator == 'minor':
                return Status.minor
            elif indicator == 'major':
                return Status.major
            elif indicator == 'critical':
                return Status.critical
            elif indicator == 'maintenance':
                return Status.maintenance
            else:
                return Status.ok
        except:
            return Status.unavailable


class Docker(Service):
    name = 'Docker'
    status_url = 'https://status.docker.com/'
    icon = "fab fa-docker"
    
    def get_status(self):
        try:
            r = requests.get(self.status_url, headers=self.headers, timeout=5)
            if "All Systems Operational" in r.text:
                return Status.ok
            elif "Incident" in r.text:
                return Status.major
            return Status.unavailable
        except:
            return Status.unavailable

# ==========================================
# 3. FLASK ROUTES
# ==========================================

SERVICES = [
    AWS(),
    GCloud(),
    Azure(),
    Atlassian(),
    Cloudflare(),
    Slack(),
    Docker(),
    GitHub(),
    Confluence(),
]

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
    # Parallel execution to speed up scraping
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {executor.submit(check_single_service, s): s for s in SERVICES}
        for future in concurrent.futures.as_completed(future_to_service):
            results.append(future.result())
    
    # Sort alphabetically
    results.sort(key=lambda x: x['name'])
    
    return render_template('index.html', services=results, Status=Status)

if __name__ == '__main__':
    app.run(debug=True, port=5000)