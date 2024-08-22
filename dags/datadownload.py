from datetime import timedelta
from airflow.models import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import requests
import psycopg2
import csv
from datetime import datetime

# Define the path for the input and output files
input_file = '/home/ugoo/airflow/web-server-access-log.txt'
extracted_and_transformed_file = '/home/ugoo/airflow/extracted-data.txt'
output_file = '/home/ugoo/airflow/result.csv'

# Define the tasks
def download():
    global input_file
    url = "https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-DB0250EN-SkillsNetwork/labs/Apache%20Airflow/Build%20a%20DAG%20using%20Airflow/web-server-access-log.txt"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
        
        with open(input_file, 'w') as file:
            file.write(response.text)
        print(f"File downloaded successfully: {input_file}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        raise

def extraction():
    global input_file, extracted_and_transformed_file
    try:
        with open(input_file, "r") as infile:
            data = infile.read()
            if not data:
                raise ValueError("Input file is empty.")
            lines = data.splitlines()
        
        with open(extracted_and_transformed_file, "w") as outfile:
            for line in lines:
                field_data = line.strip().split("#")
                if len(field_data) >= 4:
                    timestamp = field_data[0]
                    visitor_id = f"{field_data[3].capitalize()}"
                    outfile.write(timestamp + "#" + visitor_id + "\n")
        print(f"Data extracted and transformed successfully: {extracted_and_transformed_file}")
    
    except IOError as e:
        print(f"Error processing file: {e}")
        raise
    except ValueError as e:
        print(f"ValueError: {e}")
        raise

def load():
    global extracted_and_transformed_file, output_file
    try:
        with open(extracted_and_transformed_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line in infile:
                row = line.replace("#", ",")
                outfile.write(row + '\n')
        print(f"Data loaded successfully into CSV: {output_file}")
    
    except IOError as e:
        print(f"Error writing to file: {e}")
        raise

def upload():
    global output_file
    try:
        # PostgreSQL connection details
        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres.xoqgqpfqekpszphdvisd',
            password='NKRblwNFomenH15P',
            host='aws-0-eu-central-1.pooler.supabase.com',
            port='6543'
        )
        cursor = conn.cursor()

        # Create the tracking table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_tracking (
            id SERIAL PRIMARY KEY,
            last_processed TIMESTAMP
        );
        """)

        # Retrieve the last processed timestamp
        cursor.execute("SELECT last_processed FROM upload_tracking ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_processed = result[0] if result else None

        # Create table for logs if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_server_logs (
            timestamp TEXT,
            visitor_id TEXT
        );
        """)

        # Load CSV data into PostgreSQL
        with open(output_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader, None)  # Skip header row
            
            if not header or len(header) != 2:
                raise ValueError("CSV header is missing or has an incorrect number of columns.")
            
            for row in reader:
                # Skip empty rows
                if not row or len(row) != 2:
                    print(f"Skipping invalid row: {row}")
                    continue
                
                # Trim whitespace
                row = [field.strip() for field in row]
                timestamp, visitor_id = row

                # Convert timestamp to datetime object for comparison
                try:
                    row_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"Skipping invalid timestamp format: {timestamp}")
                    continue

                # Skip rows that are older than the last processed timestamp
                if last_processed and row_timestamp <= last_processed:
                    print(f"Skipping already processed row: {row}")
                    continue

                # Insert new data into PostgreSQL
                cursor.execute("""
                INSERT INTO web_server_logs (timestamp, visitor_id) VALUES (%s, %s);
                """, (timestamp, visitor_id))

        # Update the tracking table with the latest timestamp
        latest_timestamp = row_timestamp if 'row_timestamp' in locals() else datetime.now()
        cursor.execute("INSERT INTO upload_tracking (last_processed) VALUES (%s)", (latest_timestamp,))
        
        conn.commit()
        print(f"Data uploaded successfully to PostgreSQL database.")
    
    except psycopg2.Error as e:
        print(f"Error uploading data: {e}")
        raise
    except ValueError as e:
        print(f"ValueError: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def git_push():
    import subprocess
    import os

    repo_dir = '/home/ugoo/airflow'  # Path to your Git repository

    try:
        # Change to the repository directory
        os.chdir(repo_dir)
        
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit changes with a message
        subprocess.run(['git', 'commit', '-m', 'Automated commit from Airflow'], check=True)
        
        # Push changes to the remote repository
        subprocess.run(['git', 'push', 'origin', 'master'], check=True)
        
        print("Git operations completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
        raise

# Define the DAG default settings
default_args = {
    'owner': 'Ugoo Ezekoma',
    'start_date': days_ago(0),
    'email': ['ugoo@ezekomas.com'],
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Instantiate the DAG
dag = DAG(
    'Ugoo-DAG',
    default_args=default_args,
    description='My first designed workflow',
    schedule_interval=timedelta(hours=1),
)

# Define the tasks
download_data = PythonOperator(
    task_id='download',
    python_callable=download,
    dag=dag,
)

extraction_transform_data = PythonOperator(
    task_id='extraction_transform',
    python_callable=extraction,
    dag=dag,
)

load_data = PythonOperator(
    task_id='load',
    python_callable=load,
    dag=dag,
)

upload_data = PythonOperator(
    task_id='upload',
    python_callable=upload,
    dag=dag,
)

git_push_data = PythonOperator(
    task_id='git_push',
    python_callable=git_push,
    dag=dag,
)

# Set task dependencies
download_data >> extraction_transform_data >> load_data >> upload_data >> git_push_data
