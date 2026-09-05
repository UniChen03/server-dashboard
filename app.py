import shutil
import time
import os
from urllib.parse import urlsplit
import docker
import psutil
from flask import Flask, jsonify

app = Flask(__name__)

DATA_DISK_MARKER = "/mnt/data/.server-data-mounted"


def safe_service_url(value):
    """Allow local absolute paths and HTTP(S), never executable URLs."""
    if not value or any(ord(char) <= 32 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if value.startswith("/") and not value.startswith("//"):
            return value
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def discover_services():
    client = docker.from_env()
    try:
        containers = client.containers.list(
            all=True, filters={"label": "dashboard.enable=true"}
        )
        services = []
        for container in containers:
            labels = container.labels or {}
            # Enforce the allowlist even if the Docker endpoint ignores filters.
            if labels.get("dashboard.enable") != "true":
                continue
            try:
                order = int(labels.get("dashboard.order", "100"))
            except (ValueError, TypeError):
                order = 100
            services.append({
                "name": labels.get("dashboard.name") or "Service",
                "description": labels.get("dashboard.description", ""),
                "url": safe_service_url(labels.get("dashboard.url", "")),
                "tag": labels.get("dashboard.tag", ""),
                "order": order,
                "status": container.status,
            })
        services.sort(key=lambda service: (service["order"], service["name"], service["url"] or ""))
        return services
    finally:
        client.close()


@app.route("/status")
def status():
    memory = psutil.virtual_memory()
    system_disk = shutil.disk_usage("/")
    data_disk_mounted = os.path.isfile(DATA_DISK_MARKER)

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
        docker_services = discover_services()
        docker_running = sum(
            1 for service in docker_services
            if service["status"] == "running"
        )

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
