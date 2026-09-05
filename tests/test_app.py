import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app


def container(name="Example", status="running", enabled="true", **labels):
    return SimpleNamespace(
        status=status,
        labels={"dashboard.enable": enabled, "dashboard.name": name, **labels},
    )


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.docker = patch.object(app.docker, "from_env", return_value=self.client)
        self.docker.start()
        self.addCleanup(self.docker.stop)

    def test_only_explicit_opt_in_and_public_fields(self):
        hidden = [container("private", enabled=value) for value in (None, "false", "True", "1", "")]
        hidden.append(SimpleNamespace(labels={}, status="running"))
        self.client.containers.list.return_value = hidden + [container(**{"secret": "token"})]
        services = app.discover_services()
        self.assertEqual(len(services), 1)
        self.assertEqual(set(services[0]), {"name", "description", "url", "tag", "order", "status"})
        self.assertNotIn("private", str(services))
        self.assertNotIn("token", str(services))
        self.client.containers.list.assert_called_once_with(all=True, filters={"label": "dashboard.enable=true"})
        self.client.close.assert_called_once()

    def test_services_order_links_and_states(self):
        self.client.containers.list.return_value = [
            container("Example Metrics", **{"dashboard.order": "30"}),
            container("Example Admin", "exited", **{"dashboard.order": "20", "dashboard.url": "https://admin.example.com/"}),
            container("Example App", **{"dashboard.order": "10", "dashboard.url": "/example-app/"}),
        ]
        services = app.discover_services()
        self.assertEqual([s["name"] for s in services], ["Example App", "Example Admin", "Example Metrics"])
        self.assertEqual([s["status"] for s in services], ["running", "exited", "running"])
        self.assertEqual(services[0]["url"], "/example-app/")
        self.assertEqual(services[1]["url"], "https://admin.example.com/")
        self.assertIsNone(services[2]["url"])

    def test_defaults_and_empty(self):
        self.client.containers.list.return_value = [container("", **{"dashboard.order": "bad"})]
        self.assertEqual(app.discover_services()[0]["name"], "Service")
        self.assertEqual(app.discover_services()[0]["order"], 100)
        self.client.containers.list.return_value = []
        self.assertEqual(app.discover_services(), [])

    def test_client_closed_on_failure(self):
        self.client.containers.list.side_effect = RuntimeError("Docker unavailable")
        with self.assertRaises(RuntimeError):
            app.discover_services()
        self.client.close.assert_called_once()

    def test_safe_urls(self):
        for value in ["javascript:alert(1)", "data:text/html,test", "//evil.test", "/\\evil.test", "https://user:pass@example.com", "https://[bad", "/\n/evil", "relative", ""]:
            with self.subTest(value=value):
                self.assertIsNone(app.safe_service_url(value))
        for value in ["/service/", "http://localhost:8080/", "https://example.com/"]:
            self.assertEqual(app.safe_service_url(value), value)

    def test_status_api_filtered_count_failure_and_recovery(self):
        with patch.object(app.psutil, "virtual_memory", return_value=SimpleNamespace(used=1, total=2)), \
             patch.object(app.shutil, "disk_usage", return_value=SimpleNamespace(used=1, total=2)), \
             patch.object(app.os.path, "isfile", return_value=False), \
             patch.object(app.psutil, "cpu_percent", return_value=1), \
             patch.object(app.psutil, "boot_time", return_value=0):
            self.client.containers.list.return_value = [container(), container("stopped", "exited"), container("secret", enabled="false")]
            client = app.app.test_client()
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["docker_running"], 1)
            self.assertNotIn("secret", response.get_data(as_text=True))
            self.assertFalse(response.json["data_disk_mounted"])
            self.client.containers.list.side_effect = RuntimeError("secret socket error")
            response = client.get("/status")
            self.assertIsNone(response.json["docker_services"])
            self.assertIsNone(response.json["docker_running"])
            self.assertNotIn("secret", response.get_data(as_text=True))
            self.client.containers.list.side_effect = None
            self.client.containers.list.return_value = []
            self.assertEqual(client.get("/status").json["docker_services"], [])


if __name__ == "__main__":
    unittest.main()
