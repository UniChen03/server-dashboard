import shutil
import time
import os
import docker
import psutil
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/status")
def status():
    memory = psutil.virtual_memory()
    system_disk = shutil.disk_usage("/")
    data_disk_mounted = os.path.ismount("/mnt/data")

    if data_disk_mounted:
        data_disk = shutil.disk_usage("/mnt/data")
        data_disk_used = data_disk.used
        data_disk_total = data_disk.total
    else:
        data_disk_used = None
        data_disk_total = None

    try:
        temperatures = psutil.sensors_temperatures()

        cpu_temperature = None
        nvme_temperature = None

        for sensor in temperatures.get("coretemp", []):
            if sensor.label == "Package id 0":
                cpu_temperature = round(sensor.current, 1)
                break

        for sensor in temperatures.get("nvme", []):
            if sensor.label == "Composite":
                nvme_temperature = round(sensor.current, 1)
                break

    except Exception:
        cpu_temperature = None
        nvme_temperature = None

    try:
        docker_client = docker.from_env()
        containers = docker_client.containers.list(all=True)

        docker_running = sum(
            1 for container in containers
            if container.status == "running"
        )

        docker_services = {
            "job_tracker": "offline",
            "dashboard_api": "offline",
            "portainer": "offline",
        }

        for container in containers:
            if container.name == "job-application-tracker":
                docker_services["job_tracker"] = container.status

            elif container.name == "server-dashboard-api":
                docker_services["dashboard_api"] = container.status

            elif container.name == "portainer":
                docker_services["portainer"] = container.status

    except Exception:
        docker_running = None
        docker_services = None

    return jsonify(
    uptime_seconds=int(time.time() - psutil.boot_time()),
    cpu_percent=psutil.cpu_percent(interval=0.2),

    memory_used=memory.used,
    memory_total=memory.total,

    system_disk_used=system_disk.used,
    system_disk_total=system_disk.total,

    data_disk_used=data_disk_used,
    data_disk_total=data_disk_total,
    data_disk_mounted=data_disk_mounted,

    cpu_temperature=cpu_temperature,
    nvme_temperature=nvme_temperature,

    docker_running=docker_running,
    docker_services=docker_services,
)
