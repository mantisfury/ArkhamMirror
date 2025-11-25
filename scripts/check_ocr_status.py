import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    sys.exit(1)

# Handle SQLite relative path if necessary
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    # If running from root, adjust path
    if not os.path.exists(db_path) and os.path.exists(f"backend/{db_path}"):
        DATABASE_URL = f"sqlite:///backend/{db_path}"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        # Check Documents
        print("\n--- Documents ---")
        result = connection.execute(
            text(
                "SELECT id, title, status, created_at FROM documents ORDER BY created_at DESC LIMIT 5"
            )
        )
        documents = result.fetchall()
        for doc in documents:
            print(
                f"ID: {doc.id} | Title: {doc.title} | Status: {doc.status} | Date: {doc.created_at}"
            )

        if not documents:
            print("No documents found.")
            sys.exit(0)

        latest_doc_id = documents[0].id

        # Check MiniDocs for the latest document
        print(f"\n--- MiniDocs for Doc ID {latest_doc_id} ---")
        result = connection.execute(
            text(f"SELECT id, status FROM minidocs WHERE document_id = {latest_doc_id}")
        )
        minidocs = result.fetchall()
        for md in minidocs:
            print(f"MiniDoc ID: {md.id} | Status: {md.status}")

        # Check PageOCR status (Completed Pages)
        print(f"\n--- Completed Pages for Doc ID {latest_doc_id} ---")
        result = connection.execute(
            text(f"""
            SELECT COUNT(*) as count 
            FROM page_ocr 
            WHERE document_id = {latest_doc_id} 
        """)
        )
        count = result.scalar()
        print(f"Pages completed: {count}")

        # Check Chunk Status
        print(f"\n--- Chunks for Doc ID {latest_doc_id} ---")
        result = connection.execute(
            text(f"SELECT COUNT(*) FROM chunks WHERE doc_id = {latest_doc_id}")
        )
        chunk_count = result.scalar()
        print(f"Total Chunks: {chunk_count}")

        # Check RQ Registry for Active and Failed Jobs
        print(f"\n--- RQ Job Status ---")
        try:
            from redis import Redis
            from rq import Queue
            from rq.registry import StartedJobRegistry, FailedJobRegistry

            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                redis_conn = Redis.from_url(redis_url)
                q = Queue(connection=redis_conn)

                # Started Jobs
                registry = StartedJobRegistry(queue=q)
                job_ids = registry.get_job_ids()
                if job_ids:
                    print(f"Running Jobs ({len(job_ids)}):")
                    for job_id in job_ids:
                        job = q.fetch_job(job_id)
                        if job:
                            print(f" - {job_id} | {job.func_name}")
                else:
                    print("No running jobs.")

                # Failed Jobs
                failed_registry = FailedJobRegistry(queue=q)
                failed_job_ids = failed_registry.get_job_ids()
                if failed_job_ids:
                    print(f"Failed Jobs ({len(failed_job_ids)}):")
                    for job_id in failed_job_ids:
                        job = q.fetch_job(job_id)
                        if job:
                            print(
                                f" - {job_id} | {job.func_name} | Error: {job.exc_info}"
                            )
                else:
                    print("No failed jobs.")

                print(f"Jobs in Queue: {len(q)}")
            else:
                print("REDIS_URL not set.")

        except Exception as rq_e:
            print(f"Error checking RQ: {rq_e}")

except Exception as e:
    print(f"Database error: {e}")
