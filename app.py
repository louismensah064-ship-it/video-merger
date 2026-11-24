import os
import uuid
import subprocess
import requests
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()
API_SECRET = "my-secret-password-123"
OUTPUT_DIR = "/tmp/videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class MergeRequest(BaseModel):
    scene1_url: str
    scene2_url: str

def download_file(url: str, dest: str):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

@app.post("/merge")
def merge_videos(req: MergeRequest, x_secret: str = Header(None)):
    if x_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    job_id = str(uuid.uuid4())
    in1 = f"{OUTPUT_DIR}/{job_id}_1.mp4"
    in2 = f"{OUTPUT_DIR}/{job_id}_2.mp4"
    out = f"{OUTPUT_DIR}/{job_id}_final.mp4"

    try:
        download_file(req.scene1_url, in1)
        download_file(req.scene2_url, in2)

        cmd = [
            "ffmpeg", "-y",
            "-threads", "1",
            "-i", in1,
            "-i", in2,
            "-filter_complex",
            "[0:v]fps=30,format=yuv420p,setsar=1[v0];"
            "[1:v]fps=30,format=yuv420p,setsar=1[v1];"
            "[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
            "[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "24",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-movflags", "+faststart",
            "-threads", "1",
            out
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        for f in (in1, in2):
            if os.path.exists(f):
                os.remove(f)

    return {"filename": f"{job_id}_final.mp4"}

@app.get("/files/{filename}")
def get_video(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="video/mp4")
