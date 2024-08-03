from fastapi import FastAPI, File, BackgroundTasks
from PIL import Image
from fastapi.responses import Response
import os
import uuid
from accelerate import Accelerator
import boto3
from botocore.client import Config

s3_client = boto3.client(
    "s3",
    config=Config(
        region_name="ap-south-1",
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    ),
)
bucket_name = "tsai-emlo-dice"
objects_prefix = "sdxl-outputs"

results_map = {}

# fill results_map with data in S3
s3_results = s3_client.list_objects(Bucket=bucket_name, Prefix=objects_prefix)[
    "Contents"
]
for res in s3_results:
    job_id = res["Key"].split("/")[1]
    results_map[job_id] = {"status": "SUCCESS", "result": res["Key"]}


def submit_inference(uid:str, prompt:str,input_dir:str):
    results_map[uid] = {"status": "PENDING"}
    try:
        output_dir = "./sdxl-dreambooth-finetune/output"    
        os.system(f"accelerate launch /content/sdxl-dreambooth-finetune/main.py dreambooth --input-images-dir {input_dir} --instance-prompt {prompt} --resolution 512 --train-batch-size 1 --max-train-steps 1000  --mixed-precision fp16  --output-dir {output_dir}")
        # filename = f"{objects_prefix}/{uid}/result.jpeg"
        s3_client.upload_fileobj("<model>", bucket_name, filename)
        # save the s3 uri here
        results_map[uid] = {"status": "SUCCESS", "result": filename}
    except Exception as e:
        print(f"ERROR :: {e}")
        results_map[uid] = {"status": "ERROR"}


app = FastAPI(title="Fast API Test",description="Testing Fast API")

@app.get("/")
async def root():
    return{
        "message": "Welcome to the Fast API Test"
    }
    
@app.post("/train")
async def train(prompt: str,input_dir:str,background_tasks: BackgroundTasks):
    
    uid = str(uuid.uuid4())
    results_map[uid] = {"status": "PENDING"}
    background_tasks.add_task(submit_inference, uid, prompt,input_dir)
    return {"job-id": uid, "message": "job submitted successfully"}


@app.get("/status")
async def results(uid: str):
    # print(results_map)
    if uid not in results_map:
        return {"message": f"job-id={uid} is invalid", "status": "ERROR"}

    if results_map[uid]["status"] == "SUCCESS":
        obj_prefix = results_map[uid]["result"]

        print(f"{obj_prefix=}, {uid=}, {bucket_name=}")

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": obj_prefix},
            ExpiresIn=3600 * 36,  # 36 hours
        )

        return {"url": presigned_url, "status": "SUCCESS"}

    if results_map[uid]["status"] == "PENDING":
        




    return {
        "message": f"job status={results_map[uid]}",
        "status": results_map[uid]["status"],
    }
    
@app.post("/infer")
async def infer(prompt: str):
    return 


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8080)