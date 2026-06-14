"""
Application configuration and constants.
Loaded from environment variables via .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- HuggingFace ---
HF_TOKEN: str = os.getenv("HF_TOKEN", "")

# --- Models ---
ROUTER_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"       # routes question → tables (Novita)
SQL_MODEL: str = "defog/sqlcoder-7b-2"                 # generates SQL (Featherless AI)
SUMMARISER_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"   # summarises DB results (Novita)

# --- Database ---
DB_PATH: str = os.getenv("DB_PATH", "analytics.db")

# --- Generation params ---
SQL_MAX_NEW_TOKENS: int = 300
ROUTER_MAX_NEW_TOKENS: int = 50
TEMPERATURE: float = 0.1

# --- Table metadata ---
# Single source of truth for schema descriptions used by router + SQL agents.
# Column descriptions are intentionally explicit to prevent the SQL model from
# hallucinating JOIN tables or misinterpreting column names.
TABLE_METADATA: dict = {
    "palo_alto_logs": {
        "description": (
            "Stores Palo Alto firewall log records covering traffic, threat, system, and config events. "
            "Each row is one firewall log entry with full network details, action taken, and traffic volume."
        ),
        "columns": {
            "id":               "INTEGER — unique log entry identifier (primary key, auto-increment)",
            "log_content":      "TEXT    — full raw log line with all field values comma-separated (Palo Alto syslog format)",
            "log_type":         "TEXT    — category of the log entry: traffic, threat, system, or config",
            "log_receive_time": "TEXT    — exact datetime the log was received (YYYY-MM-DD HH:MM:SS:mmm)",
            "log_date":         "TEXT    — date of the log event (YYYY-MM-DD)",
            "threat_type":      "TEXT    — specific threat or event subtype (e.g. url, virus, end, drop, monitoring, commit)",
            "src_ip_address":   "TEXT    — source IP address of the connection (e.g. '10.234.5.12'). NOT a foreign key.",
            "dst_ip_address":   "TEXT    — destination IP address of the connection. NOT a foreign key.",
            "application_nm":   "TEXT    — application identified by the firewall (e.g. dns-base, ssl, http, kerberose)",
            "src_port":         "INTEGER — source port number of the connection",
            "dest_port":        "INTEGER — destination port number (e.g. 80, 443, 53, 22, 3389)",
            "ip_protocol":      "TEXT    — network protocol: tcp, udp, or icmp",
            "type_of_action":   "TEXT    — action taken by the firewall: allow, deny, drop, alert, block, reset-both",
            "category":         "TEXT    — URL or threat category (e.g. search-engines, malware, any, not-resolved)",
            "app_risk_lvl":     "INTEGER — application risk level score from 1 (low) to 5 (critical)",
            "bytes_sent":       "INTEGER — number of bytes sent in the session",
            "bytes_received":   "INTEGER — number of bytes received in the session",
            "src_action":       "TEXT    — policy action source: from-policy, to-policy, pbf-from-policy, or n/a",
        },
    },

    "ping_identity_logs": {
        "description": (
            "Stores Ping Identity authentication and access management event logs. "
            "Each row represents one identity event — login, logout, MFA challenge, or password reset — "
            "with full user, device, location, and risk details."
        ),
        "columns": {
            "id":                    "INTEGER   — unique row identifier (primary key, auto-increment)",
            "log_id":                "TEXT      — unique log entry ID (e.g. 'LOG00042')",
            "event_timestamp":       "TIMESTAMP — exact datetime of the event (YYYY-MM-DD HH:MM:SS, e.g. '2024-03-15 09:32:11')",
            "event_date":            "DATE      — date of the event (YYYY-MM-DD, e.g. '2024-03-15')",
            "user_id":               "TEXT      — unique user identifier (e.g. 'U1023')",
            "username":              "TEXT      — login username of the user (e.g. 'john.d'). NOT a foreign key.",
            "email":                 "TEXT      — email address of the user (e.g. 'john.d@company.com'). NOT a foreign key.",
            "ip_address":            "TEXT      — IP address from which the event originated. NOT a foreign key.",
            "device_type":           "TEXT      — type of device used: Desktop, Laptop, Mobile, or Tablet",
            "operating_system":      "TEXT      — OS on the device: Windows, macOS, Linux, Android, or iOS",
            "browser_name":          "TEXT      — browser used: Chrome, Edge, Safari, Firefox, or Brave",
            "application_name":      "TEXT      — application accessed (e.g. Snowflake, Salesforce, ServiceNow, Workday, Jira)",
            "authentication_method": "TEXT      — method used to authenticate: SSO, Password, OAuth, or MFA",
            "event_type":            "TEXT      — type of identity event: Login, Logout, MFA Challenge, or Password Reset",
            "event_status":          "TEXT      — outcome of the event: Success or Failed",
            "failure_reason":        "TEXT      — reason for failure if event_status is Failed (e.g. 'Invalid Password', 'Account Locked', 'MFA Failed'). NULL if Success.",
            "session_id":            "TEXT      — unique session identifier for the event (e.g. 'S01042'). NOT a foreign key.",
            "location_country":      "TEXT      — country where the event originated (e.g. India, USA, UK, Germany, Singapore, Japan). NOT a foreign key.",
            "location_city":         "TEXT      — city where the event originated (e.g. Mumbai, New York, London). NOT a foreign key.",
            "risk_score":            "REAL      — risk score assigned to the event from 0.0 (low risk) to 100.0 (high risk)",
            "mfa_status":            "TEXT      — MFA verification result: Passed, Failed, or Not Required",
        },
    },

    "zscaler_logs": {
        "description": (
            "Stores Zscaler web proxy and cloud security logs. "
            "Each row represents one web session — capturing the user, URL visited, threat detected, "
            "bandwidth used, file downloads, policy applied, and risk score."
        ),
        "columns": {
            "id":                    "INTEGER   — unique row identifier (primary key, auto-increment)",
            "log_id":                "TEXT      — unique log entry ID (e.g. 'ZLOG00042')",
            "event_timestamp":       "TIMESTAMP — exact datetime of the web session (YYYY-MM-DD HH:MM:SS, e.g. '2024-05-10 14:22:00')",
            "event_date":            "DATE      — date of the session (YYYY-MM-DD, e.g. '2024-05-10')",
            "username":              "TEXT      — login username of the user (e.g. 'john.d'). NOT a foreign key.",
            "email":                 "TEXT      — email address of the user. NOT a foreign key.",
            "source_ip":             "TEXT      — internal source IP of the user device. NOT a foreign key.",
            "destination_ip":        "TEXT      — destination IP of the web server. NOT a foreign key.",
            "url":                   "TEXT      — full URL accessed (e.g. 'https://youtube.com/page21'). NOT a foreign key.",
            "domain":                "TEXT      — domain of the URL (e.g. youtube.com, dropbox.com, salesforce.com)",
            "web_category":          "TEXT      — category of the website: Streaming, File Sharing, Business Apps, Social Networking, Technology, Shopping",
            "action":                "TEXT      — Zscaler action taken: Allowed or Blocked",
            "ssl_inspection_status": "TEXT      — SSL inspection result: Inspected or Bypassed",
            "bandwidth_mb":          "REAL      — bandwidth consumed by the session in megabytes",
            "threat_detected":       "TEXT      — whether a threat was detected: Yes or No",
            "threat_type":           "TEXT      — type of threat if detected: Malware, Phishing, Botnet, Spyware, or None",
            "policy_rule":           "TEXT      — Zscaler policy rule applied (e.g. 'Default Policy', 'High Risk Block', 'File Download Control')",
            "cloud_app":             "TEXT      — cloud application identified (e.g. Salesforce, Microsoft365, GitHub, Dropbox)",
            "file_download":         "TEXT      — whether a file was downloaded: Yes or No",
            "file_type":             "TEXT      — type of file downloaded (e.g. PDF, EXE, ZIP, DOCX) or None if no download",
            "location":              "TEXT      — city where the user is located (e.g. Mumbai, New York, London). NOT a foreign key.",
            "department":            "TEXT      — department of the user: IT, HR, Finance, Operations, Sales, Engineering, Marketing",
            "device_posture":        "TEXT      — device compliance status: Compliant or Non-Compliant",
            "zscaler_node":          "TEXT      — Zscaler node that processed the request (e.g. 'IN-MUM-01', 'US-NYC-01'). NOT a foreign key.",
            "session_duration_sec":  "INTEGER   — duration of the web session in seconds",
            "risk_score":            "REAL      — risk score of the session from 0.0 (low) to 100.0 (high)",
            "location_country":      "TEXT      — country where the user is located (e.g. India, USA, UK, Germany, Singapore). NOT a foreign key.",
        },
    },

    "linux_logs": {
        "description": (
            "Stores Linux system event logs from servers across global data centers. "
            "Each row is one system event — SSH logins, process starts, service restarts, "
            "file access, privilege escalations — with full server, user, resource usage, and environment details."
        ),
        "columns": {
            "id":                   "INTEGER   — unique row identifier (primary key, auto-increment)",
            "log_id":               "TEXT      — unique log entry ID (e.g. 'LNX00042')",
            "event_timestamp":      "TIMESTAMP — exact datetime of the event (YYYY-MM-DD HH:MM:SS, e.g. '2024-08-12 03:45:00')",
            "event_date":           "DATE      — date of the event (YYYY-MM-DD, e.g. '2024-08-12')",
            "hostname":             "TEXT      — hostname of the server where the event occurred (e.g. 'web-prod-01', 'db-prod-02'). NOT a foreign key.",
            "server_ip":            "TEXT      — internal IP address of the server. NOT a foreign key.",
            "username":             "TEXT      — Linux username that triggered the event (e.g. root, ubuntu, admin, nginx). NOT a foreign key.",
            "process_id":           "INTEGER   — process ID (PID) of the process involved",
            "process_name":         "TEXT      — name of the process (e.g. nginx, sshd, cron, mysqld, dockerd)",
            "service_name":         "TEXT      — name of the system service involved: SSH, Cron, Nginx, MySQL, Docker, PostgreSQL",
            "log_level":            "TEXT      — severity level of the log: INFO, WARN, ERROR, or CRITICAL",
            "event_type":           "TEXT      — type of system event: SSH Login, Process Start, Service Restart, File Access, Privilege Escalation",
            "command_executed":     "TEXT      — shell command executed during the event (e.g. 'sudo su', 'systemctl restart nginx')",
            "source_ip":            "TEXT      — source IP address that initiated the event. NOT a foreign key.",
            "destination_port":     "INTEGER   — destination port number (e.g. 22 for SSH, 80 for HTTP, 443 for HTTPS, 3306 for MySQL)",
            "auth_method":          "TEXT      — authentication method used: SSH Key, Password, or Sudo",
            "event_status":         "TEXT      — outcome of the event: Success or Failed",
            "cpu_usage_percent":    "REAL      — CPU usage percentage at the time of the event (0.0 to 100.0)",
            "memory_usage_percent": "REAL      — memory usage percentage at the time of the event (0.0 to 100.0)",
            "disk_usage_percent":   "REAL      — disk usage percentage at the time of the event (0.0 to 100.0)",
            "kernel_module":        "TEXT      — Linux kernel module involved: ext4, xfs, tcp, overlay, bridge, nfs",
            "session_id":           "TEXT      — unique session identifier (e.g. 'SID10042'). NOT a foreign key.",
            "error_code":           "TEXT      — error code if applicable: ERR001, ERR002, ERR003. NULL if no error.",
            "log_message":          "TEXT      — human-readable log message (e.g. 'Permission denied', 'User logged in successfully')",
            "environment":          "TEXT      — deployment environment: PROD, DEV, or UAT",
            "data_center":          "TEXT      — data center name where the server resides (e.g. 'Bangalore-DC1', 'Virginia-DC1'). NOT a foreign key.",
            "location_country":     "TEXT      — country where the data center is located (e.g. India, USA, UK, Germany). NOT a foreign key.",
        },
    },

    "bluecoat_proxy_logs": {
        "description": (
            "Stores BlueCoat proxy gateway logs capturing all web traffic routed through the enterprise proxy. "
            "Each row is one HTTP/HTTPS request — with user, URL, proxy action, cache, SSL, threat score, and bandwidth details."
        ),
        "columns": {
            "id":                    "INTEGER   — unique row identifier (primary key, auto-increment)",
            "log_id":                "TEXT      — unique log entry ID (e.g. 'BC00042')",
            "event_timestamp":       "TIMESTAMP — exact datetime of the proxy request (YYYY-MM-DD HH:MM:SS)",
            "event_date":            "DATE      — date of the request (YYYY-MM-DD)",
            "client_ip":             "TEXT      — internal IP address of the client device. NOT a foreign key.",
            "username":              "TEXT      — username of the person who made the request (e.g. 'john.d'). NOT a foreign key.",
            "request_url":           "TEXT      — full URL of the request (e.g. 'https://youtube.com/page27'). NOT a foreign key.",
            "url_host":              "TEXT      — hostname/domain of the request (e.g. youtube.com, salesforce.com, github.com)",
            "url_path":              "TEXT      — path component of the URL (e.g. '/page22'). NOT a foreign key.",
            "http_method":           "TEXT      — HTTP method used: GET, POST, or CONNECT",
            "proxy_action":          "TEXT      — action taken by the proxy: TUNNELED, OBSERVED, or DENIED",
            "policy_group":          "TEXT      — proxy policy applied: Default Policy, Restricted Policy, or Guest Policy",
            "filter_result":         "TEXT      — content filter result: Allowed, Warning, or Blocked",
            "category_name":         "TEXT      — web category of the URL: Streaming, Social, Business, File Sharing, Technology",
            "cache_status":          "TEXT      — proxy cache result: HIT, MISS, or REFRESH",
            "cache_object_size_kb":  "INTEGER   — size of the cached object in kilobytes",
            "download_duration_ms":  "INTEGER   — time taken to complete the download in milliseconds",
            "ssl_tunnel":            "TEXT      — whether SSL tunnel was used: Yes or No",
            "ssl_cipher":            "TEXT      — SSL cipher suite used (e.g. TLS_AES_256_GCM_SHA384) or None",
            "referrer_url":          "TEXT      — HTTP referrer URL. NOT a foreign key.",
            "user_agent":            "TEXT      — browser/client user agent string (e.g. 'Chrome/137', 'Firefox/140')",
            "content_type":          "TEXT      — MIME content type of the response (e.g. text/html, application/json)",
            "mime_type":             "TEXT      — simplified MIME type: HTML, JSON, PDF, ZIP, PNG",
            "threat_score":          "REAL      — threat risk score from 0.0 (clean) to 100.0 (high threat)",
            "bandwidth_consumed_mb": "REAL      — total bandwidth consumed by the request in megabytes",
            "proxy_appliance":       "TEXT      — BlueCoat ProxySG appliance that handled the request (e.g. 'ProxySG-MUM-01', 'ProxySG-NYC-01'). NOT a foreign key.",
            "location_country":      "TEXT      — country where the proxy appliance is located (e.g. India, USA, UK). NOT a foreign key.",
        },
    },
}
