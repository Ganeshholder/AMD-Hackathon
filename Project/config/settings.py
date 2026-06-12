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
    "transactions": {
        "description": (
            "Stores financial transaction records. "
            "Each row is one transaction with its amount, country of origin, "
            "processing status, and timestamp."
        ),
        "columns": {
            "transaction_id": "INTEGER — unique transaction identifier (primary key)",
            "customer_id":    "INTEGER — ID of the customer who made the transaction",
            "amount":         "REAL    — transaction amount in currency units",
            "status":         "TEXT    — processing status: SUCCESS, FAILED, or PENDING",
            "country":        "TEXT    — country where the transaction originated (e.g. India, USA, UK, Germany, Singapore)",
            "created_at":     "TEXT    — datetime the transaction was created (YYYY-MM-DD HH:MM:SS)",
        },
    },
    "log_table": {
        "description": (
            "Stores system event logs with network and device details. "
            "Each row is one log event. "
            "NOTE: 'location' is a plain TEXT column storing a city name directly "
            "inside this table — there is NO separate location table."
        ),
        "columns": {
            "id":          "INTEGER — unique log entry identifier (primary key, auto-increment)",
            "location":    "TEXT    — city name stored directly in this column (e.g. 'Moorefurt'). NOT a foreign key. Do NOT join to any other table.",
            "log_time":    "TEXT    — datetime of the log event (YYYY-MM-DD HH:MM:SS)",
            "ip_address":  "TEXT    — IPv4 address of the client (e.g. '12.177.159.190')",
            "user_name":   "TEXT    — username of the user who triggered the event",
            "event_type":  "TEXT    — type of event: LOGIN, LOGOUT, FILE_ACCESS, PAYMENT, TRANSFER, FAILED_LOGIN",
            "device_type": "TEXT    — device used: Mobile, Laptop, Desktop, Tablet",
            "status":      "TEXT    — event outcome: SUCCESS, FAILED, PENDING",
        },
    },

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
}
