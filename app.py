import shutil
import subprocess
import time

import docker
import psutil
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/status")
def status():
    memory = psutil.virtual_memory()
    system_disk = shutil.disk_usage("/")
    data_disk = shutil.disk_usage("/mnt/data")

    try:
        temperature_output = subprocess.check_output(
            ["sensors"],
            text=True,
        )

        temperature = None

        for line in temperature_output.splitlines():
            if "Package id 0:" in line:
                temperature = line.split("+")[1].split("°")[0]
                break
    except Exception:
        temperature = None

    try:
        docker_client = docker.from_env()
        docker_running = len(docker_client.containers.list())
    except Exception:
        docker_running = None

    return jsonify(
        uptime_seconds=int(time.time() - psutil.boot_time()),
        cpu_percent=psutil.cpu_percent(interval=0.2),

        memory_used=memory.used,
        memory_total=memory.total,

        system_disk_used=system_disk.used,
        system_disk_total=system_disk.total,

        data_disk_used=data_disk.used,
        data_disk_total=data_disk.total,

        temperature=temperature,
        docker_running=docker_running,
    )
