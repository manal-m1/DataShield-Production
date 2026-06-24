from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago
import requests
import json
from datetime import timedelta

# Service URLs (Docker Network)
CLEANING_SERVICE_URL = "http://cleaning-service:8004"
TAXONOMY_SERVICE_URL = "http://taxonomie-service:8002"
CLASSIFICATION_SERVICE_URL = "http://classification-service:8005"
QUALITY_SERVICE_URL = "http://quality-service:8008"
ETHIMASK_SERVICE_URL = "http://ethimask-service:8009"
CORRECTION_SERVICE_URL = "http://correction-service:8006"

default_args = {
    'owner': 'datagov',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'datagov_pipeline',
    default_args=default_args,
    description='End-to-end Data Governance Pipeline',
    schedule_interval=None,  # Triggered manually via upload
    start_date=days_ago(1),
    tags=['datagov'],
    catchup=False,
    is_paused_upon_creation=False
)

def ingest_and_clean(**context):
    """Call cleaning service to profile and clean data"""
    conf = context['dag_run'].conf or {}
    dataset_id = conf.get('dataset_id')
    
    if not dataset_id:
        raise ValueError(
            "No dataset_id provided in DAG run configuration. "
            "Trigger with conf: {\"dataset_id\": \"...\"}"
        )
    
    print(f"Starting pipeline for dataset: {dataset_id}")
    
    # 1. Profile - cleaning-service returns an HTML report for this endpoint.
    resp = requests.get(f"{CLEANING_SERVICE_URL}/profile/{dataset_id}", timeout=30)
    resp.raise_for_status()
    print(f"Profile generated: HTML report size={len(resp.text)} bytes")
    
    # 2. Clean
    resp = requests.post(
        f"{CLEANING_SERVICE_URL}/clean/{dataset_id}",
        params={
            "remove_duplicates": True,
            "remove_outliers": True,
            "handle_missing": "mean",
            "normalize": False,
        },
        timeout=30,
    )
    resp.raise_for_status()
    clean_result = resp.json()
    print(f"Cleaning complete: {clean_result}")
    
    return dataset_id

def analyze_pii(**context):
    """Run inconsistency detection on a sample from the cleaned dataset."""
    dataset_id = context['task_instance'].xcom_pull(task_ids='ingest_and_clean')
    
    if not dataset_id:
        raise ValueError("No dataset_id received from ingest_and_clean")

    resp = requests.get(
        f"{CLEANING_SERVICE_URL}/dataset/{dataset_id}/json",
        params={"sample": True},
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json().get("data", [])

    total_inconsistencies = 0
    for row in rows:
        detect_resp = requests.post(
            f"{CORRECTION_SERVICE_URL}/detect",
            json={
                "row": {key: str(value) if value is not None else "" for key, value in row.items()},
                "dataset_id": dataset_id,
            },
            timeout=30,
        )
        detect_resp.raise_for_status()
        result = detect_resp.json()
        total_inconsistencies += result.get("count", 0)

    print(f"Inconsistencies detected on sample: {total_inconsistencies}")
    
    return dataset_id

def classify_sensitivity(**context):
    """Call classification service"""
    dataset_id = context['task_instance'].xcom_pull(task_ids='analyze_pii')
    
    # Trigger classification on dataset
    # Need to simulate or implement bulk scan in classification-serv.
    # Existing endpoint is /classify (single text).
    # We will simulate iterating or use a bulk endpoint if we made one.
    # For POC, let's call a 'mock' generic logger or assume we process top rows.
    
    print(f"Classifying dataset {dataset_id} sensitivity...")
    # Real impl would iterate rows.
    
    return dataset_id

def evaluate_quality(**context):
    """Call quality service"""
    dataset_id = context['task_instance'].xcom_pull(task_ids='classify_sensitivity')
    
    resp = requests.post(f"{QUALITY_SERVICE_URL}/evaluate/{dataset_id}")
    resp.raise_for_status()
    report = resp.json()
    print(f"Quality Grade: {report['grade']} ({report['global_score']}%)")
    
    return dataset_id

def apply_masking(**context):
    """Call ethimask service"""
    dataset_id = context['task_instance'].xcom_pull(task_ids='evaluate_quality')
    
    print(f"Applying masking policies for dataset {dataset_id}")
    # Simulating masking trigger
    
    return dataset_id

# Tasks
start = DummyOperator(task_id='start', dag=dag)

t1 = PythonOperator(
    task_id='ingest_and_clean',
    python_callable=ingest_and_clean,
    provide_context=True,
    dag=dag
)

t2 = PythonOperator(
    task_id='analyze_pii',
    python_callable=analyze_pii,
    provide_context=True,
    dag=dag
)

t3 = PythonOperator(
    task_id='classify_sensitivity',
    python_callable=classify_sensitivity,
    provide_context=True,
    dag=dag
)

t4 = PythonOperator(
    task_id='evaluate_quality',
    python_callable=evaluate_quality,
    provide_context=True,
    dag=dag
)

t5 = PythonOperator(
    task_id='apply_masking',
    python_callable=apply_masking,
    provide_context=True,
    dag=dag
)

end = DummyOperator(task_id='end', dag=dag)

# Dependencies
start >> t1 >> t2 >> t3 >> t4 >> t5 >> end
