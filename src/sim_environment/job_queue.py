import uuid
import random

def generate_mock_jobs(num_jobs=5):
    """
    Generates a queue of mock AI compute workloads to be routed by the agent.
    """
    job_types = ["train_llama3_8b", "batch_image_processing", "whisper_transcription", "data_pipeline"]
    
    jobs = []
    for _ in range(num_jobs):
        job = {
            "job_id": f"job_{str(uuid.uuid4())[:8]}",
            "task": random.choice(job_types),
            "compute_hours": random.randint(1, 24),
            # If False, the agent can use temporal shifting (delay the job for greener energy)
            "is_urgent": random.choice([True, False]), 
            # Simulates data privacy laws (e.g., GDPR requiring EU processing)
            "locality_constraint": random.choice([None, "eu-central-1", "us-east-1", None]) 
        }
        jobs.append(job)
    return jobs

if __name__ == "__main__":
    import json
    print(json.dumps(generate_mock_jobs(2), indent=2))
