"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.adm.aarhuskommune.dk"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"
GRAPH_API = "Graph API"
SAP_LOGIN = "SAP Ejendomsbeskatning"
SAP_CREDENTIAL = "SAP Masseoprettelse i SAP"
DATA_BUCKETS = "Data Buckets"


# Queue specific configs
MAX_TASK_COUNT = 600  # Limits the number of queue elements to process per run.
QUEUE_NAME = "Masseoprettelse-af-journalnotat-i-KMD-Opus-Debitor"


THREAD_COUNT = 6
