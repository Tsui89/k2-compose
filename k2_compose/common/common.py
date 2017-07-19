[SERVICE_UNDEPLOYED, SERVICE_STOP, SERVICE_ERROR, SERVICE_RUNNING] = [i for i in range(4)]
CONTAINER_STATUS = ['undeployed', 'stopped', 'error', 'running']
COLOR = ['autobgblack', 'autobgred', 'autobgyellow', 'autobggreen']


[HOST_DISCONNECT, HOST_CONNECT] = [i for i in range(2)]
HOST_STATUS = ['stopped', 'running']
COLOR_HOST = ['autobgred', 'autobggreen']


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

DEBUG = False

from os import getenv
DOCKER_API_VERSION = getenv('DOCKER_API_VERSION', '1.23')
