"""This module contains the main process of the robot."""

from io import BytesIO
import json
import uuid
from datetime import datetime
from functools import lru_cache
import threading
import re

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement, QueueStatus
from itk_dev_shared_components.sap import multi_session, opret_kundekontakt
from itk_dev_shared_components.graph import authentication as graph_authentication
from itk_dev_shared_components.graph import mail as graph_mail
from bs4 import BeautifulSoup
import pyodbc
import itk_dev_event_log

from robot_framework import config


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    data_bucket_conn_string = orchestrator_connection.get_constant(config.DATA_BUCKETS).value

    check_email(orchestrator_connection, data_bucket_conn_string)

    event_log = orchestrator_connection.get_constant("Event Log")
    itk_dev_event_log.setup_logging(event_log.value)

    for _ in range(0, config.MAX_TASK_COUNT, config.THREAD_COUNT):
        # Get new queue elements
        queue_elements: list[QueueElement] = []
        for _ in range(config.THREAD_COUNT):
            queue_element = orchestrator_connection.get_next_queue_element(config.QUEUE_NAME)
            if queue_element is None:
                break
            queue_elements.append(queue_element)

        # Stop if no more queue elements
        if len(queue_elements) == 0:
            orchestrator_connection.log_info("No more queue elements.")
            return

        orchestrator_connection.log_info(f"Creating kundekontakter: {len(queue_elements)}")

        lock = threading.Lock()
        args_list = [[qe, orchestrator_connection, lock, data_bucket_conn_string] for qe in queue_elements]

        multi_session.run_batch(do_task, args_list)


def check_email(orchestrator_connection: OrchestratorConnection, data_bucket_conn_string: str):
    """Check the email folder for any new tasks.
    If a new email is found, create queue elements.

    Args:
        orchestrator_connection: The connection to Orchestrator.
    """
    graph_creds = orchestrator_connection.get_credential(config.GRAPH_API)
    graph_access = graph_authentication.authorize_by_username_password(graph_creds.username, **json.loads(graph_creds.password))
    mails = graph_mail.get_emails_from_folder("itk-rpa@mkb.aarhus.dk", "Indbakke/Masseoprettelse OPUS Debitor", graph_access)
    mails = [mail for mail in mails if mail.sender == 'noreply@aarhus.dk' and 'RPA - Masseoprettelse af kundekontakter i OPUS Debitor (fra Selvbetjening.aarhuskommune.dk)' in mail.subject]

    orchestrator_connection.log_info(f"Emails in folder: {len(mails)}")

    data_bucket_connection = pyodbc.connect(data_bucket_conn_string)

    for mail in mails:
        # Get email text
        soup = BeautifulSoup(mail.body, "html.parser")
        sections = soup.find_all('p')
        sender = sections[0].get_text(separator=" ").split(' ', maxsplit=1)[1].split(": ")[1]
        art = sections[1].get_text(separator=" ").split(' ', maxsplit=1)[1]
        text = sections[2].get_text(separator=" ").split(' ', maxsplit=1)[1]

        if sender not in json.loads(orchestrator_connection.process_arguments)["approved_senders"]:
            orchestrator_connection.log_info(f"Sender not on list of approved senders: {sender}")
            graph_mail.delete_email(mail, graph_access)
            continue

        # Insert into data bucket
        bucket_id = uuid.uuid4()
        data_bucket_connection.execute("INSERT INTO DataBuckets VALUES (?, ?, ?, ?)", bucket_id, f"{art};{text}", orchestrator_connection.process_name, datetime.now())
        data_bucket_connection.commit()
        orchestrator_connection.log_info(f"Data inserted into bucket: {bucket_id}")

        # Read attached file
        attachments = graph_mail.list_email_attachments(mail, graph_access)
        file = graph_mail.get_attachment_data(attachments[0], graph_access)
        references = read_file(file)

        # Create queue elements
        data = {"bucket_id": str(bucket_id)}
        data = json.dumps(data)

        orchestrator_connection.log_info(f"Creating queue elements: {len(references)}")
        for reference in references:
            orchestrator_connection.create_queue_element(config.QUEUE_NAME, reference=reference, data=data, created_by="Robot")

        graph_mail.delete_email(mail, graph_access)


def read_file(file: BytesIO) -> list[str]:
    """Read a file with reference data.
    Removes dangling semicolons and headers.

    Returns:
        A cleaned list of lines from the file.
    """
    pattern = re.compile(r"\d+;?\d*")
    lines = file.read().decode().splitlines()

    lines = [line.rstrip(";") for line in lines if pattern.fullmatch(line)]

    return lines


@lru_cache
def get_bucket_data(key: str, data_bucket_conn_string: str) -> str:
    """Get data from the data buckets with the given key.
    This function uses an lru cache to reduce database calls.

    Args:
        key: The key of the value in the data bucket.
        data_bucket_conn_string: The connection string to the database.

    Returns:
        The value of the data bucket with the given key.
    """
    data_bucket_connection = pyodbc.connect(data_bucket_conn_string)
    return data_bucket_connection.execute("SELECT value FROM DataBuckets WHERE [key] = ?", key).fetchval()


def do_task(session, queue_element: QueueElement, orchestrator_connection: OrchestratorConnection, lock: threading.Lock, data_bucket_conn_string: str):
    """A function for multithreading.
    Extract queue element data.
    Create kundekontakt.
    Mark queue element as Done/Failed

    Args:
        session: A SAP session.
        queue_element: A queue element.
        orchestrator_connection: The orchestrator connection for setting status.
        lock: A threading lock used in opret_kundekontakter.
        data_bucket_conn_string: The connection string to the data bucket.
    """
    data = json.loads(queue_element.data)

    reference_list = queue_element.reference.split(";")
    fp = reference_list[0]
    aftaleindhold = [reference_list[1]] if len(reference_list) == 2 else None

    bucket_data = get_bucket_data(data['bucket_id'], data_bucket_conn_string)
    art, notat = bucket_data.split(";", maxsplit=1)

    try:
        opret_kundekontakt.opret_kundekontakter(session, fp, aftaleindhold, art, notat, lock)
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE)
        itk_dev_event_log.emit(orchestrator_connection.process_name, "Note created")
    # we need to catch every exception to mark the queue element as failed. The error is re-raised.
    # pylint: disable-next=broad-exception-caught
    except Exception as exc:
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED)
        raise exc
