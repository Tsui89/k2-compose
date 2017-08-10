[SERVICE_UNDEPLOYED, SERVICE_STOP, SERVICE_ERROR, SERVICE_RUNNING] = [i for i in range(4)]
CONTAINER_STATUS = ['undeployed', 'stopped', 'error', 'running']
COLOR = ['autoblack', 'autored', 'autoyellow', 'autogreen']


[HOST_DISCONNECT, HOST_CONNECT] = [i for i in range(2)]
HOST_STATUS = ['stopped', 'running']
COLOR_HOST = ['autored', 'autogreen']


HOSTS_KEY = "hosts"
HOST_KEY = "host"
HOSTNAME_KEY = "hostname"
HEALTH_CHECK_KEY = "health_check"
DEPENDS_KEY = "s_depends_on"
URLS_KEY = "urls"
CM_SERVER_KEY = "cm_server"
IMAGE_KEY = "image"
PROJECT_KEY = "project"
S_EXTRA_HOSTS = "s_extra_hosts"

DOCKER_COMPOSE_FILE = ".docker-compose.yml"
DOCKER_PROJECT_PREFIX = "k2-compose"
DOCKER_PROJECT_SUFFIX = '_1'
DEPLOYMENT_ID = "test_deployment"
YAML_PATH = "./"
CONTAINER_EXIT_WAIT = 10
SYS_RETURN_CODE = 0  # container exit code ignore health check

HEALTH_CHECK_EXEC_TIME_UNDEPLOYED = -20002
HEALTH_CHECK_EXEC_TIME_STOPPED = -20001
HEALTH_CHECK_EXEC_TIME_ERROR = -20000
HEALTH_CHECK_EXEC_TIME_RUNNING = 0

HEALTH_CHECK_EXEC_TIME_ERROR_DEFAULT=-10

DEBUG = False

HOSTS_METRIC = 'hosts'
SERVICES_METRIC = 'services'
CONTAINERS_METRIC = 'containers'

from os import getenv
DOCKER_API_VERSION = getenv('DOCKER_API_VERSION', '1.23')

DOCKER_HOST_DEFAULT="unix:///var/run/docker.sock"


import globalVar


def set_debug():
    globalVar.set_debug()


def get_debug():
    return globalVar.get_debug()