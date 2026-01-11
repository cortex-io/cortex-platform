"""
Global pytest configuration and fixtures for Cortex Python E2E tests with K3s
"""
import os
import sys
import subprocess
import time
import pytest
import requests
from kubernetes import client, config

# Set test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['LOG_LEVEL'] = 'INFO'
os.environ['K8S_NAMESPACE'] = 'cortex-test'

TEST_NAMESPACE = 'cortex-test'

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def kubectl(command, namespace=TEST_NAMESPACE, check=True):
    """Execute kubectl command"""
    full_command = f"kubectl {command} -n {namespace}"
    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True,
        check=check
    )
    return result.stdout.strip()


def wait_for_service(service_name, timeout=120):
    """Wait for a Kubernetes service to be ready"""
    start_time = time.time()
    interval = 2

    print(f"Waiting for service {service_name} to be ready...")

    while time.time() - start_time < timeout:
        try:
            result = kubectl(
                f"get deployment {service_name} -o jsonpath='{{.status.readyReplicas}}'",
                check=False
            )
            ready_replicas = int(result) if result else 0
            if ready_replicas > 0:
                print(f"Service {service_name} is ready")
                return True
        except (ValueError, subprocess.CalledProcessError):
            pass

        time.sleep(interval)

    raise TimeoutError(f"Service {service_name} did not become ready within {timeout}s")


def get_service_endpoint(service_name, port=80, namespace=TEST_NAMESPACE):
    """Get service endpoint URL"""
    return f"http://{service_name}.{namespace}.svc.cluster.local:{port}"


def health_check(service_url, retries=10, delay=2):
    """Perform health check on a service"""
    for i in range(retries):
        try:
            response = requests.get(f"{service_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"Health check passed for {service_url}")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Health check attempt {i + 1}/{retries} failed for {service_url}: {e}")
            if i < retries - 1:
                time.sleep(delay)

    raise Exception(f"Health check failed for {service_url} after {retries} retries")


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_environment():
    """Setup E2E test environment before running tests"""
    print("Setting up E2E test environment...")

    try:
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        # Create test namespace if it doesn't exist
        try:
            kubectl("get namespace", namespace="")
        except subprocess.CalledProcessError:
            print(f"Creating namespace {TEST_NAMESPACE}...")
            kubectl(f"create namespace {TEST_NAMESPACE}", namespace="")

        # Apply test resources
        print("Applying test resources...")
        test_resources_path = os.path.join(
            os.path.dirname(__file__),
            "../../k8s/test-resources"
        )
        if os.path.exists(test_resources_path):
            subprocess.run(
                f"kubectl apply -f {test_resources_path} -n {TEST_NAMESPACE}",
                shell=True,
                check=True
            )

        # Wait for core services
        print("Waiting for test services to be ready...")
        wait_for_service('test-redis')
        wait_for_service('test-postgres')

        print("E2E test environment ready")

    except Exception as e:
        print(f"Failed to setup E2E test environment: {e}")
        raise

    yield

    # Cleanup (optional)
    if os.environ.get('CLEANUP_TESTS', 'true') != 'false':
        print("Cleaning up E2E test resources...")
        # Uncomment to delete namespace after tests
        # kubectl(f"delete namespace {TEST_NAMESPACE} --wait=false", namespace="")


@pytest.fixture
def k8s_client():
    """Get Kubernetes API client"""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return client.CoreV1Api()


@pytest.fixture
def service_endpoint():
    """Factory fixture for getting service endpoints"""
    return get_service_endpoint


@pytest.fixture
def wait_helper():
    """Provide wait helper function"""
    def wait_for_condition(condition, timeout=30, interval=1):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition():
                return True
            time.sleep(interval)
        return False
    return wait_for_condition
