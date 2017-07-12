#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from __future__ import print_function

import os
import sys
import json
import subprocess
import signal
import time
import copy
import yaml
import argparse
import logging
import requests
import re

from pick import pick
from health_agent import db_writer
from requests.exceptions import ConnectionError
from docker import Client, errors
from k2cutils.class_utils import cached_property
from multiprocessing.dummy import Pool as ThreadPool

from compose_utils.basenode import Node, DependsOn, RunsOn
from compose_utils.toposort import toposort
from compose_utils.host import Host, HOST_DISCONNECT, HOST_CONNECT, host_connect
from compose_utils.image_show import ImageInspect
from terminaltables import SingleTable, AsciiTable
from colorclass import Color

from image_history import ImageHistory

[SERVICE_UNDEPLOYED, SERVICE_STOP, SERVICE_ERROR, SERVICE_RUNNING] = [i for i in range(4)]
CONTAINER_STATUS = ['undeployed', 'stopped', 'error', 'running']
COLOR = ['autobgblack', 'autobgred', 'autobgyellow', 'autobggreen']

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

logging.basicConfig(format='%(levelname)s: %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')


def check_compose_file(filename):
    if not os.path.isfile(filename):
        logging.error("Yaml [%s] does not exist" % (filename))
        return False

    try:
        compose_data = yaml.safe_load(open(filename))
        # print compose_data
    except Exception as e:
        # logging.error(e)
        logging.error("Yaml format error, %s"%e)
        return False

    # try:
    #     if not compose_data.has_key(PROJECT_KEY):
    #         return False
    # except:
    #     return False

    return True


def confirm_input(msg=''):
    print '%s' % (msg), 'Are you sure? [yN]',
    try:
        confirm = raw_input()
        if confirm.lower() not in ['y', 'yes']:
            logging.error("Aborted by user.")
            sys.exit(-1)
    except KeyboardInterrupt:
        logging.error("Aborted by user.")
        sys.exit(-1)
    else:
        return True


# saved health-check status to influxdb when start/stop/restart/up/remove a service
def status_store(args):
    if not os.getenv("INFLUXDB"):
        return
    start_time = time.time()
    compose_concrete = ComposeConcrete(filename=args.file, url=args.url)
    logging.debug("%s consumed loading compose file" % (time.time() - start_time))
    # check cluster
    clusters = {}
    logging.debug('Checking docker cluster info...')
    for host_name, host_instance in compose_concrete.hosts_instance.items():
        cli = host_instance.client
        try:
            info = cli.info()
        except (errors.APIError, errors.DockerException) as e:
            logging.error(e.message)
        except Exception as e:
            logging.error(e.message)
        else:
            clusters.update({host_name: info['ClusterStore']})

    # if len(set(clusters.values())) > 1:
    #     print Color(
    #         '{autored}Not all docker hosts shares the same cluster store. Are they really in the same cluster?{/autored}')
    #     sys.exit(-1)
    # else:
    #     cluster = clusters.values()[0]
    cluster = clusters.values()[0]
    net = compose_concrete.net

    writer = db_writer.Writer(os.getenv("INFLUXDB"))
    result = {
        'tags': {
            'cluster': cluster,
            'net': net,
            'deployment': compose_concrete.project,
            'group': long(time.time() * 1000 * 1000 * 1000),  # nano
        },
        'services': {}
    }

    for service_name in args.services:
        start_time = time.time()
        k2compose = K2ComposeCMD(compose_concrete_instance=compose_concrete)
        status = k2compose.ps(services=[service_name], json_format=False)
        result['services'].update({service_name: (start_time, status.get(service_name))})
    writer.write(result)
    global SYS_RETURN_CODE
    sys.exit(SYS_RETURN_CODE)


def subprocesscmd(cmd_str='', timeout=None, discription='', env=os.environ, show_message=True):
    logging.debug('%s DOCKER_HOST=%s %s ' % (
        discription, env.get('DOCKER_HOST'), cmd_str))
    global SYS_RETURN_CODE
    poll_time = 0.2
    if show_message:
        stdout = None
        stderr = None
    else:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
    try:
        ret = subprocess.Popen(cmd_str, stdout=stdout, stderr=stderr, shell=True, env=env)
    except OSError as e:
        logging.error('%s %s %s %s' % (discription, e, cmd_str, str(env)))
        SYS_RETURN_CODE = SYS_RETURN_CODE if timeout else 166
        return False
    try:
        if timeout:
            deadtime = time.time() + timeout
            while time.time() < deadtime and ret.poll() is None:
                time.sleep(poll_time)
        else:
            ret.wait()
    except KeyboardInterrupt:
        ret.send_signal(signal.SIGINT)
        logging.error('Aborted by user.')
        SYS_RETURN_CODE = SYS_RETURN_CODE if timeout else 167
        return False

    if ret.poll() is None:
        ret.send_signal(signal.SIGINT)
        logging.error(
            '%s : Exec [%s] overtime.' % (discription, cmd_str))
        SYS_RETURN_CODE = SYS_RETURN_CODE if timeout else 168
        return False

    if not show_message:
        for line in ret.stdout:
            if line:
                logging.info('%s %s' % (discription, line.strip('\n')))
        for line in ret.stderr:
            if line:
                logging.error('%s %s' % (discription, line.strip('\n')))
    SYS_RETURN_CODE = SYS_RETURN_CODE if timeout else ret.returncode
    if ret.returncode == 0:
        return True


class ComposeService(Node):
    def __init__(self, id='', service=None):
        Node.__init__(self)
        self.type = "container"
        self.id = id
        self._service = service

        self.status_code = SERVICE_UNDEPLOYED
        self.status = CONTAINER_STATUS[SERVICE_UNDEPLOYED]
        self.color = COLOR[self.status_code]

    @cached_property
    def hostname(self):
        return self._service.get('host', 'local')

    @cached_property
    def health_check(self):
        return self._service.get('health_check', {})

    @cached_property
    def s_depends_on(self):
        return self._service.get('s_depends_on', [])

    @cached_property
    def image(self):
        return self._service.get('image', '')

    @cached_property
    def image_name(self):
        index = str(self.image).rfind(':')
        return str(self.image)[:index]

    @cached_property
    def image_tag(self):
        if ":" in str(self.image):
            index = str(self.image).rfind(':')
            return str(self.image)[index + 1:]
        else:
            return 'latest'

    @cached_property
    def ports(self):
        return self._service.get('ports',[])

    @cached_property
    def network_mode(self):
        return self._service.get('network_mode','')

    def show(self):
        table_data = []
        keys = self._service.keys()
        keys.sort()
        for key in keys:
            value = self._service.get(key)
            if isinstance(value, (str, int, bool)) is False:
                value = yaml.dump(value, default_flow_style=False).strip('\n')
            table_data.append([key, value])
        table_instance = SingleTable(table_data, self.id)
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table


class Container(ComposeService):
    def __init__(self, id='', service=None, hostip=''):
        ComposeService.__init__(self, id=id, service=service)
        self._hostip = hostip
        self._client = None
        self._service = service
        self._image_status = 'unchanged'
        # self._inspect_image=
        self.containerid = DOCKER_PROJECT_PREFIX + '_' + self.id + \
                           DOCKER_PROJECT_SUFFIX

        self.base_cmd = 'docker-compose -f %s -p %s ' % (
            DOCKER_COMPOSE_FILE, DOCKER_PROJECT_PREFIX)

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, client=None):
        self._client = client

    @property
    def hostip(self):
        return self._hostip

    @cached_property
    def image_history(self):
        history = ImageHistory.load(self.image_name, self.image_tag, self._hostip)
        return history if history is not None else ImageHistory(self.image_name, self.image_tag, self._hostip, self._client)

    def check_client(self, msg=''):
        return True

    def ps(self):
        if self.status_code is SERVICE_UNDEPLOYED:
            return
        cmd = '%s ps %s' % (self.base_cmd, self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip},
                      discription='ps detail:', show_message=False)

    def stats(self):
        try:
            stats = self.client.stats(self.containerid, stream=False, decode=True)
            mem_limit = stats['memory_stats']['limit']
            mem_percent = float(stats['memory_stats']['usage']*100)/mem_limit
            cpu_percent = 0.0
            cpu_delta = float(stats['cpu_stats']['cpu_usage']['total_usage']
                              - stats['precpu_stats']['cpu_usage']['total_usage'])
            system_delta = float(stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage'])
            processor_num = len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
            if cpu_delta > 0.0 and system_delta > 0.0:
                cpu_percent = (cpu_delta / system_delta) * processor_num * 100.0
            return round(cpu_percent, 2), round(mem_percent, 2), mem_limit
        except Exception, e:
            print e
            return None, None, None

    def ps_container(self):
        if not self.check_client('In ps container'):
            return
        try:
            inspect = self.client.inspect_container(self.containerid)
        except errors.NotFound as e:
            self.status_code = SERVICE_UNDEPLOYED
        except (errors.APIError, errors.DockerException) as e:
            self.status_code = SERVICE_UNDEPLOYED
        except Exception as e:
            logging.error(e.message)
            self.status_code = SERVICE_UNDEPLOYED
        else:
            status = inspect.get('State').get('Status')
            if status == 'running':
                self.status_code = SERVICE_ERROR
            else:
                self.status_code = SERVICE_STOP

        self.status = CONTAINER_STATUS[self.status_code]
        self.color = COLOR[self.status_code]

    def ps_image(self):
        if not self.check_client('In ps image') \
                or self.status_code is SERVICE_UNDEPLOYED:
            return
        try:
            inspect = self.client.inspect_image(self.image)
        except errors.NotFound as e:
            self._image_status = 'unchanged'
            return
        except (errors.DockerException, errors.APIError):
            self._image_status = 'unchanged'
            return
        except Exception as e:
            self._image_status = 'unchanged'
            return
        else:
            imageid = inspect.get('Id')

        try:
            container_inspect = self.client.inspect_container(
                self.containerid)
        except errors.NotFound as e:
            self._image_status = 'unchanged'
            return
        except (errors.APIError, errors.DockerException):
            self._image_status = 'unchanged'
            return
        except Exception as e:
            self._image_status = 'unchanged'
            return
        else:
            if imageid == container_inspect.get('Image'):
                self._image_status = 'unchanged'
            else:
                self._image_status = 'changed'

    def healthcheck(self):
        if self.status_code not in [SERVICE_ERROR, SERVICE_RUNNING]:
            return

        health_check = self.health_check

        cmd = health_check.get('shell', '')
        timeout = health_check.get('timeout', 10)

        if cmd:
            if subprocesscmd(cmd, timeout, show_message=False,
                             discription='In [%s] health check:' % self.id):
                self.status_code = SERVICE_RUNNING
            else:
                self.status_code = SERVICE_ERROR
        else:
            self.status_code = SERVICE_RUNNING

        self.status = CONTAINER_STATUS[self.status_code]
        self.color = COLOR[self.status_code]

    def up(self, parameter='', confirm_update=False):
        if not self.check_client('In UP '):
            return

        self.ps_container()
        self.healthcheck()
        global SYS_RETURN_CODE

        if self.status_code in [SERVICE_ERROR, SERVICE_RUNNING]:
            logging.warning('[%s] status is [%s].'
                            ' If you want to update, you must stop it is first.' % (
                                self.id, self.status))
            SYS_RETURN_CODE = 169
            return
        self.ps_image()
        if self._image_status != 'unchanged':
            msg = "Going to update [%s]." % (self.id)
            if confirm_update is False and confirm_input(msg) is False:
                SYS_RETURN_CODE = 170
                return
        cmd = 'DOCKER_HOST=%s docker-compose -f %s -p %s up %s %s' % (
            self.hostip, DOCKER_COMPOSE_FILE, DOCKER_PROJECT_PREFIX, parameter,
            self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip})
        pass

    def start(self):
        if not self.check_client('In start'):
            return
        self.ps_container()
        self.healthcheck()
        global SYS_RETURN_CODE

        if self.status_code is SERVICE_STOP:
            try:
                print 'Starting [%s] ...' % (self.id)
                self.client.start(self.containerid)
                SYS_RETURN_CODE = 0
                print 'Done.'
            except errors.NotFound as e:
                logging.error(e.message)
            except (errors.DockerException, errors.APIError) as e:
                logging.error(e.message)
            except Exception as e:
                logging.error(e.message)

        elif self.status_code in [SERVICE_ERROR, SERVICE_RUNNING]:
            SYS_RETURN_CODE = 171
            logging.error('[%s] status is [%s]. if you want restart ,'
                          ' please use restart or use stop first' % (
                              self.id, self.status))
        elif self.status_code is SERVICE_UNDEPLOYED:
            SYS_RETURN_CODE = 172
            logging.error('[%s] is undeployed.'
                          'You can`t do a start cmd on it.' % self.id)

    def logs(self, parameter=''):
        if not self.check_client('In logs'):
            return
        self.ps_container()
        if self.status_code is SERVICE_UNDEPLOYED:
            logging.error('The [%s] status is [%s]. '
                          'You cant get logs from it.' % (
                              self.id, self.status))
            return
        cmd = 'docker-compose -f %s -p %s logs %s %s' % (
            DOCKER_COMPOSE_FILE, DOCKER_PROJECT_PREFIX, parameter, self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip})

    def stop(self):
        if not self.check_client('In stop'):
            return
        global SYS_RETURN_CODE
        self.ps_container()
        if self.status_code is SERVICE_STOP:
            logging.warning(' [%s] status is [%s] already.' % (
                self.id, self.status))
            SYS_RETURN_CODE = 173
        elif self.status_code is SERVICE_UNDEPLOYED:
            SYS_RETURN_CODE = 174
            logging.error('[%s] status is [%s].' \
                          'You can`t do a stop cmd on it.' % (
                              self.id, self.status))
        else:
            try:
                print 'Stopping [%s] ...' % (self.id)
                self.client.stop(self.containerid, CONTAINER_EXIT_WAIT)
                SYS_RETURN_CODE = 0
                print 'Done.'
            except errors.NotFound as e:
                SYS_RETURN_CODE = 175
                logging.error(e.message)
            except (errors.APIError, errors.DockerException) as e:
                SYS_RETURN_CODE = 176
                logging.error(e.message)
            except Exception as e:
                SYS_RETURN_CODE = 176
                logging.error(e.message)

    def restart(self):
        if not self.check_client('In restart'):
            return
        self.stop()
        self.start()

    def bash(self):
        if not self.check_client('In bash'):
            return
        self.ps_container()
        if self.status_code in [SERVICE_UNDEPLOYED, SERVICE_STOP]:
            logging.error('[%s] is [%s].' % (self.id, self.status))
            return
        print Color('{autored}#####In [%s] Container#####{/autored}'%(self.id))
        cmd = '%s exec %s sh' % (self.base_cmd, self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip})
        print Color('{autored}#####Out [%s] Container#####{/autored}'%(self.id))

    def rm(self, force=False):
        if not self.check_client('In rm'):
            return
        global SYS_RETURN_CODE
        self.ps_container()
        if self.status_code is SERVICE_UNDEPLOYED:
            SYS_RETURN_CODE = 176
            logging.error('[%s] status is [%s].' % (self.id, self.status))
        else:
            try:
                print 'Removing [%s] ...' % (self.id)
                self.client.remove_container(self.containerid, force=force)
                SYS_RETURN_CODE = 0
                print 'Done.'
            except errors.NotFound as e:
                SYS_RETURN_CODE = 177
                logging.error(e.message)
            except errors.APIError as e:
                SYS_RETURN_CODE = 178
                logging.error(e.message)
            except errors.DockerException as e:
                SYS_RETURN_CODE = 179
                logging.error(e.message)
            except Exception as e:
                SYS_RETURN_CODE = 179
                logging.error(e.message)

    def pull(self):
        cmd = '%s pull %s' % (self.base_cmd, self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip})

    @classmethod
    def ps_thread(cls, container_instance=None):
        if not isinstance(container_instance, cls):
            logging.error('need container instance')
            return
        container_instance.ps_container()
        container_instance.healthcheck()
        container_instance.ps_image()
        if DEBUG:
            container_instance.ps()

    def image_label(self):

        try:
            container_inspect = self.client.inspect_container(self.containerid)
        except :
            imageid = self.image
        else:
            imageid = container_inspect.get('Image')

        try:
            data = self.client.inspect_image(imageid)
        except:
            return ImageInspect(service=self.id,image=self.image)()
        else:
            return ImageInspect(service=self.id, image=self.image, **data)()

    def tag(self, suffix):
        index = self.image.rfind(':')
        _repository = self.image[:index]
        _tag = self.image[index+1:]+suffix
        print 'Tagging %s => %s:%s ...'%(self.image, _repository,_tag)
        try:
            self.client.tag(image=self.image,repository=_repository, tag=_tag)
        except Exception as e:
            print e.message
            return False
        else:
            return True

    def push(self, suffix):
        index = self.image.rfind(':')
        _repository = self.image[:index]
        _tag = self.image[index+1:]+suffix
        message = self.id
        # print 'Pushing %s:%s ...'%(_repository,_tag)
        try:
            # print 'push is running. please wait...'
            for _result in self.client.push(repository=_repository,tag=_tag, stream=True):
                r=eval(_result)
                try:
                    message += " => "+r['aux']['Digest']
                except:pass

                try:
                    message += " => "+Color("{autored}%s{/autored}"%r['error'])
                except: pass

        except Exception as e:
            print e
            return message
        else:
            # print 'Done.'
            return message

class ComposeFile(object):
    def __init__(self, **kwargs):
        self.stream=None
        self.stream_name=''
        self._safe_load(**kwargs)
        global DOCKER_PROJECT_PREFIX
        if self.project:
            DOCKER_PROJECT_PREFIX = filter(str.isalnum, self.project)
        self.sorted_services = self.sort()

    def _safe_load(self, filename=None, url=None):
        if os.environ.get("DEPLOYMENT_URL") and not url:
            url = os.environ.get("DEPLOYMENT_URL") + "/files/" + filename
        if url:
            try:
                rsp = requests.get(url)
                if rsp.status_code != 200:
                    logging.error('error get url %s: %s %s' % (url, rsp.status_code, rsp.reason))
                rsp_json = rsp.json()
                file_content = rsp_json.get('content') if 'content' in rsp_json else rsp_json['body'].get('content')
                self.stream = yaml.safe_load(file_content)
                self.stream_name = url

            except Exception as e:
                logging.error('error get url %s: %s' % (url, e))
        elif check_compose_file(filename):
            self.stream = yaml.safe_load(open(filename))
            self.stream_name = filename
        else:
            sys.exit(-1)

    @cached_property
    def project(self):
        try:
            return self.stream.get('project', DOCKER_PROJECT_PREFIX)
        except KeyError:
            return DOCKER_PROJECT_PREFIX

    @cached_property
    def driver(self):
        try:
            return self.stream['networks']['default']['driver']
        except:
            return ''

    @cached_property
    def net(self):
        try:
            if dict(self.stream['networks']['default']).has_key('external'):
                return self.stream['networks']['default']['external']['name']
            else:
                return '%s_default' % self.project
        except KeyError:
            return None

    @cached_property
    def hosts(self):
        try:
            return self.stream.get('hosts',{'local':'127.0.0.1:4243'})
        except KeyError:
            return {}

    @cached_property
    def services(self):
        try:
            return self.stream.get('services')
        except KeyError:
            return {}

    def hostip(self, id='local'):
        hosts = self.hosts
        try:
            return hosts.get(id)
        except KeyError:
            return '127.0.0.1:4243'

    def get_service(self, id=''):
        try:
            return self.stream.get('services', {}).get(id)
        except KeyError:
            return None

    def sort(self):
        services_list = self.services.keys()
        services_list.sort()
        dependency_list = []
        for service_k, service_v in self.services.items():
            composeservice = ComposeService(service_k, service_v)
            for depends in composeservice.s_depends_on:
                dependency_list.append((depends, service_k))

        return toposort(services_list, dependency_list)

    def check_service(self, services=None, msg='In Check Service:'):
        tmp_services = []
        re_services = {}

        match_record={}
        for s in services:
            match_record.update({s:0})

        if services:
            #compile regular
            for service in services:
                tmp = service.replace('*', '.*')
                if re.search(r'\[\d-\d\]$', tmp) or '*' in tmp:
                    re_services.update({service:re.compile(r'%s'%tmp)})

            for service in self.sorted_services:

                if service in services:
                    tmp_services.append(service)
                    match_record[service] = match_record.get(service, 0) + 1

                for s,re_s in re_services.items():
                    if re_s.match(service):
                        if service not in tmp_services:
                            tmp_services.append(service)
                            match_record[s] = match_record.get(s, 0) + 1
                        else:
                            match_record[s] = match_record.get(s, 0) + 1
        else:
                tmp_services.extend(self.sorted_services)
        for s,s_match in match_record.items():
            if s_match == 0:
                logging.error('%s %s not match any service in YML.'%(msg,s))

        logging.debug("%s Match Results: %s"%(msg, match_record))
        # return set(tmp_services)
        return tmp_services

    def show(self, services=None):

        if services:
            services = self.check_service(services,msg='In SHOW:')
            for service in services:
                service_instance = ComposeService(id=service,
                                                  service=self.services.get(
                                                      service))
                service_instance.show()
        else:
            self.show_topology()

    def show_topology(self):
        table_data = []
        table_instance = SingleTable(table_data, self.stream_name)
        table_data.append(['host', 'dockerHost', 'services'])

        hosts = self.hosts.keys()
        hosts.sort()
        for host in hosts:
            dockerHost = self.hosts.get(host)
            services = []
            for service, service_information in self.services.items():
                if service_information.get('host', 'local') == host:
                    services.append(service)
            services.sort()
            services = yaml.dump(services, default_flow_style=False).strip('\n')

            table_data.append([host, dockerHost, services])
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table


class ComposeConcrete(ComposeFile):
    def __init__(self, **kwargs):
        ComposeFile.__init__(self, **kwargs)
        self.hosts_instance = {}
        self._containers = {}
        self.generateyml()
        self.concrete()

    def new_host_instance(self, host_object):
        self.hosts_instance.__setitem__(host_object.id, host_object)

    def getcontainer(self, service):
        return self._containers.get(service)

    def newcontainer(self, composeservice_object):
        self._containers.__setitem__(composeservice_object.id,
                                     composeservice_object)

    def get_host_instance_by_containerid(self, service):
        container = self._containers.get(service)
        try:
            return self.hosts_instance.get(container.hostname)
        except KeyError:
            logging.error('Get service [%s]`s host[%s] error.' % (
                service, container.host))
            return None

    def get_host_by_id(self, id):
        host = self.hosts_instance.get(id)
        if host:
            return host
        else:
            logging.error('Get host[%s] error.' % (id))
            sys.exit(-1)

    def generateyml(self):
        global DOCKER_COMPOSE_FILE
        DOCKER_COMPOSE_FILE = '.%s-compose.yml' % (DOCKER_PROJECT_PREFIX)
        parse_key = [DEPENDS_KEY, HEALTH_CHECK_KEY, HOST_KEY, URLS_KEY]
        stream_tmp = copy.deepcopy(self.stream)

        for key in [HOSTS_KEY, PROJECT_KEY, CM_SERVER_KEY]:
            if key in stream_tmp:
                stream_tmp.pop(key)

        #load extra_hosts
        _extra_hosts = {}
        if stream_tmp.has_key(S_EXTRA_HOSTS):
            _extra_hosts=stream_tmp.pop(S_EXTRA_HOSTS)

        for service_name,service in stream_tmp['services'].items():
            for key in parse_key:
                if service.has_key(key):
                    service.pop(key)

            if self.driver == 'bridge' and service.get('network_mode','') != 'host':
                if not service.has_key('extra_hosts'):
                    service['extra_hosts']={}
                service['extra_hosts'].update(_extra_hosts)

            # extra_hosts = service.get('extra_hosts',{})
            # extra_hosts.update(_extra_hosts)
        yaml.safe_dump(stream_tmp, open(DOCKER_COMPOSE_FILE, 'w+'), default_flow_style=False, width=float("inf"))


    def build_host(self, id='local'):
        try:
            return Host(id, self.hostip(id))
        except KeyError:
            return None

    def build_service(self, id=''):

        service = self.get_service(id)

        hostip = self.hostip(service.get('host','local'))
        try:
            return Container(id=id, service=service, hostip=hostip)
        except KeyError:
            return None

    def concrete(self):
        pool = ThreadPool(len(self.hosts))
        host_instances = []
        for host in self.hosts:
            instance = self.build_host(host)
            self.new_host_instance(instance)
            host_instances.append(instance)
        pool.map(host_connect, host_instances)
        pool.close()
        pool.join()

        for service_name in self.services.keys():
            container = self.build_service(service_name)
            service = self.get_service(service_name)
            hostid = service.get('host','local')
            container.client = self.get_host_by_id(hostid).client
            self.newcontainer(container)

    def ps(self, services=None, ignore_deps=False, parameter=''):
        result = {}
        services = self.check_service(services, msg='In PS:')

        if services != self.sorted_services:
            if ignore_deps is False:
                depends_all = []
                for service in services:
                    container = self.getcontainer(service)
                    depends_all.extend(container.s_depends_on)
                services.extend(depends_all)
        services = list(set(services))

        pool_containers = []
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            status_code = -1
            if host.status != 'running':
                result.update({service: status_code})
                continue
            pool_containers.append(self.getcontainer(service))
        if services:
            pool = ThreadPool(len(services))
            pool.map(Container.ps_thread, pool_containers)
            pool.close()
            pool.join()

        for container in pool_containers:
            result.update({container.id: container.status_code})
        return result

    def show_status(self, services=None):
        services = self.check_service(services, msg='In SHOW STATUS:')

        table_data = []
        table_data.append(
            ['Service', 'Host', 'Service-Status', 'Image-Status', 'Depends-On', 'Ports', 'Network-Mode'])

        try:
            default_network = self.stream['networks']['default']['driver']
        except:
            default_network = 'default'

        for service in services:
            container = self.getcontainer(service)
            host = self.get_host_instance_by_containerid(service)
            image_status = ''

            host_color = "{%s}%s{/%s}" % (
                host.color, container.hostip, host.color)
            container_color = "{%s}%s{/%s}" % (
                container.color, container.status, container.color)
            if container._image_status == 'changed':
                image_status = container._image_status
            depends = ''
            for depend in container.s_depends_on:
                depend_container = self.getcontainer(depend)
                depend_container_color = "- {%s}%s{/%s}\n" % (
                    depend_container.color, depend, depend_container.color)
                depends += (Color(depend_container_color))
            depends = depends.strip('\n')

            ports = ''
            for port in container.ports:
                ports += "- %s\n"%port
            ports = ports.strip('\n')

            nm = default_network if container.network_mode == '' else container.network_mode

            table_data.append([container.id, Color(host_color),
                               Color(container_color), image_status,
                               depends,ports, nm])

        table_instance = AsciiTable(table_data)

        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table

    def up(self, services=None, ignore_deps=False, **kwargs):
        services = self.check_service(services, msg='In UP:')
        # if services == self.sorted_services:
        #     confirm_input('Going to start ALL-Services.')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('UP [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            if ignore_deps is False:
                if self.check_depends(service) is False:
                    global SYS_RETURN_CODE
                    SYS_RETURN_CODE = 179  # check depends error
                    continue

            container = self.getcontainer(service)
            container.up(**kwargs)
            container.image_history.insert_current()
        sys.exit(SYS_RETURN_CODE)

    def check_depends(self, id):
        container = self.getcontainer(id)
        for service_depends in container.s_depends_on:
            host = self.get_host_instance_by_containerid(service_depends)
            if host.status != 'running':
                logging.error('check_depends [%s]:'
                              ' Connect [%s] error.' % (
                                  service_depends, host.id))
                return False
            container_depends = self.getcontainer(service_depends)
            container_depends.ps_container()
            container_depends.healthcheck()
            if container_depends.status_code != SERVICE_RUNNING:
                logging.error(
                    '[%s] depends on [%s]. but [%s] status is %s' % (
                        id, service_depends, service_depends,
                        container_depends.status))
                return False
        return True

    def start(self, services=None):
        services = self.check_service(services, msg='In START:')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('start [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.start()

    def logs(self, services=None, parameter=''):
        services = self.check_service(services, msg='In LOGS:')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('logs [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.logs(parameter)

    def stop(self, services=None):
        services = self.check_service(services, msg='In STOP:')
        if services == self.sorted_services:
            confirm_input('Going to stop ALL-Services.')
            services.reverse()
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('stop [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.stop()

    def restart(self, services=None):
        services = self.check_service(services, msg='In RESTART:')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('restart [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.restart()

    def bash(self, services=None):
        services = self.check_service(services, msg='In BASH:')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('bash [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.bash()

    def rm(self, services=None, **kwargs):
        services = self.check_service(services, msg='In RM:')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('rm [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.rm(**kwargs)

    def pull(self, services=None):
        services = self.check_service(services, msg='In PULL:')
        if services == self.sorted_services:
            confirm_input('Going to update ALL-Services Images.')
        for service in services:
            host = self.get_host_instance_by_containerid(service)
            if host.status != 'running':
                logging.error('pull [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.getcontainer(service)
            container.pull()
            container.image_history.insert_current()

    def images(self, args, services=None):
        services = self.check_service(services, msg='In IMAGES:')

        for service in services:
            container = self.getcontainer(service)
            container.image_history.insert_current()
            container.image_history.show()
            if args.config:
                sel = raw_input('Press enter to keep the current choics[*], or type index number: ')
                if sel == '':
                    return
                valid_choices = [str(i) for i in range(0, len(container.image_history.content))]
                if sel in valid_choices:
                    container.image_history.change_current(int(sel))
                else:
                    print 'Invalid Choice. Nothing Changed.'

    def _probe(self, services=None, merge=True):
        _results = []
        _results_async = []
        pool = ThreadPool(len(self.services))

        services = self.check_service(services,msg='In Inspect:')
        for service_name in services:
            host = self.get_host_instance_by_containerid(service_name)
            service = self.get_service(service_name)

            if host.status != 'running':
                _results.append(ImageInspect(service=service_name,image=service['image'])())
                continue
            else:
                container = self.getcontainer(service_name)
                _results_async.append(pool.apply_async(container.image_label))
        pool.close()
        pool.join()
        for r in _results_async:
            _results.append(r.get())
        _results.sort(key=lambda obj:obj.get('image'),reverse=False)

        if not merge:
            return _results

        #合并相同记录
        _show_tmp = {}
        for r in _results:
            key = r['image'] + str(r['Id']) + r['Match']
            if not _show_tmp.has_key(key):
                _show_tmp[key] = {
                    'image':r['image'],
                    'service': r['service'],
                    'Id': r['Id'],
                    'Created': r['Created'],
                    'Labels': r['Labels'],
                    'Match': r['Match']
                }
            else:
                _show_tmp[key]['service'] += '\n'+r['service']
        return _show_tmp

    def inspect(self, services=None):

        _show_tmp = self._probe(services)
        table_data = []
        table_instance = SingleTable(table_data, self.stream_name)
        table_data.append(['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

        for key in sorted(_show_tmp.keys()):
            table_data.append([_show_tmp[key]['image']+'\n'+_show_tmp[key]['Match'], _show_tmp[key]['service'],
                               _show_tmp[key]['Id'], _show_tmp[key]['Created'], _show_tmp[key]['Labels']])
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table

    def save(self, suffix, services=None, only_tag=False, only_push=False, no_interaction=False, text=False):

        if only_tag and only_push:
            print 'please note that. Only one of [--only-tag|--only-push] can be use.'
            return
        _show = self._probe(services, merge=False)
        table_data = []
        if not _show:
            return

        longest_image = max([len(v['image']) for v in _show])
        longest_service = max([len(v['service']) for v in _show])
        longest_imageId = max([len(v['Id']) for v in _show])
        longest_match = max([len(v['Match']) for v in _show])

        title = '\n  {image:<{longest_image}} | {service:<{longest_service}} | {imageid:<{longest_imageId}} | {match:<{longest_match}}' \
                '\n  {ind:-<{wedth}}'.format(
                    image='Image', service='Service', imageid='Image-Id',match='Match',
                    longest_image=longest_image, longest_service=longest_service, longest_imageId=longest_imageId, longest_match=longest_match,
                    ind='-',wedth=longest_image+longest_service+longest_imageId+longest_match+9)

        for v in _show:
            table_data.append('{image:<{longest_image}} | {service:<{longest_service}} | {imageid:<{longest_imageId}} | {match:<{longest_match}}'.format(
                image=v['image'],service=v['service'],imageid=v['Id'], match=v['Match'],longest_image=longest_image,
                longest_service=longest_service, longest_imageId=longest_imageId, longest_match=longest_match))

        selected_service = []
        if no_interaction:
            selected_service.extend(_show)
        else:
            try:
                selected = pick(table_data, 'Please choose your images for save (press SPACE to mark, ENTER to continue, Ctrl+C to exit): ' + title,
                                indicator='*', multi_select=True, min_selection_count=0)
            except KeyboardInterrupt:
                return
            if selected:
                for s in selected:
                    v = _show[s[1]]
                    selected_service.append(v)
            else:
                print 'Select 0 image.'
                return
        # confirm_input(msg='Select these images.')

        print 'List:'
        _skip=False
        not_ready = []

        for s in selected_service:
            _action = 'skip'
            if s['Id'] == '':
                _action += '(not exist)'
                _skip = True
            elif s['Match'] != '':
                _action += '(not match)'
                _skip = True
            else:
                _action = 'do'

            s['Action'] = _action
            if _action == 'do':
                _action = Color('{autogreen}%s{/autogreen}'%(_action))
            else:
                _action = Color('{autored}%s{/autored}'%(_action))
                not_ready.append(s)
            print '{action:<25} {image_old:<{longest_image}} => {image_new:<{longest_image}}'.format(action=_action,
                                                                                        longest_image=longest_image,
                                                                                        image_old=s['image'],
                                                                                        image_new=s['image']+suffix)
        if only_tag:
            _msg = 'Tag these images.'
        elif only_push:
            _msg = 'Push these images.'
        else:
            _msg = 'Tag and Push these images.'
        if _skip:
            if no_interaction:
                _msg += Color('\n{autored}These service`s image is not ready, please fix it first.{/autored}')

                print _msg
                table_data = []
                table_instance = SingleTable(table_data, 'Not Ready')
                table_data.append(['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

                for s in not_ready:
                    table_data.append(
                        [s['image'] + '\n' + s['Match'], s['service'],
                         s['Id'], s['Created'], s['Labels']])
                table_instance.inner_heading_row_border = False
                table_instance.inner_row_border = True
                print table_instance.table
                sys.exit(-1)
            else:
                _msg +=  Color('\n{autored}Some service`s image is not ready. \n' \
                       'You can use k2-compose pull/up to fix it, otherwise these images will be skipped.{/autored}\n')
                confirm_input(msg=_msg)

        if not only_push:
            pool = ThreadPool(len(selected_service))
            for s in selected_service:
                if s['Action'] == 'do':
                    container = self.getcontainer(s['service'])
                    pool.apply(container.tag, (suffix,))
            pool.close()
            pool.join()

        if only_tag:
            return

        _result = []
        pool = ThreadPool(len(selected_service))
        print 'Pushing...'
        for s in selected_service:
            if s['Action'] == 'do':
                container = self.getcontainer(s['service'])
                _result.append(pool.apply_async(container.push, (suffix,)))
        pool.close()
        pool.join()
        for r in _result:
            print r.get()
        print Color('{autogreen}Push all done.{/autogreen}\n')
        if text:
            print "#".join(['Image', 'Service', 'Image-Id', 'Created', 'Labels'])
            for s in selected_service:
                print "#".join((s['image'], s['service'],
                     s['Id'], s['Created'], s['Labels'].replace('\n',' ')))
        else:
            table_data = []
            table_instance = SingleTable(table_data, 'Done')
            table_data.append(['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

            for s in selected_service:
                table_data.append(
                    [s['image'], s['service'],
                     s['Id'], s['Created'], s['Labels']])
            table_instance.inner_heading_row_border = False
            table_instance.inner_row_border = True
            print table_instance.table
        return


class K2ComposeCMD(object):
    def __init__(self, compose_concrete_instance):
        self.composeconcrete = compose_concrete_instance

    def use(self, **kwargs):
        self.__init__(**kwargs)

    def ps(self, json_format=False, json_outfile='', **kwargs):
        result = self.composeconcrete.ps(**kwargs)
        if json_format:
            self.json_format(json_outfile)
        else:
            self.composeconcrete.show_status(**kwargs)
        return result

    def up(self, **kwargs):
        self.composeconcrete.up(**kwargs)

    def start(self, **kwargs):
        self.composeconcrete.start(**kwargs)
        pass

    def stop(self, **kwargs):
        self.composeconcrete.stop(**kwargs)
        pass

    def restart(self, **kwargs):
        self.composeconcrete.restart(**kwargs)
        pass

    def logs(self, **kwargs):
        self.composeconcrete.logs(**kwargs)
        pass

    def bash(self, **kwargs):
        self.composeconcrete.bash(**kwargs)
        pass

    def rm(self, **kwargs):
        self.composeconcrete.rm(**kwargs)

    def pull(self, **kwargs):
        self.composeconcrete.pull(**kwargs)

    def images(self, **kwargs):
        self.composeconcrete.images(**kwargs)

    def inspect(self, **kwargs):
        self.composeconcrete.inspect(**kwargs)

    def save(self, **kwargs):
        self.composeconcrete.save(**kwargs)

    def json_format(self, outfile=None):
        deployment = {'id': self.composeconcrete.project,
                      'updatedAt': long(time.time() * 1000)}
        graph = {'nodes': [], 'edges': []}

        hosts = self.composeconcrete.hosts_instance
        for host, host_docker_service in hosts.items():
            # print host_node.to_string()
            graph['nodes'].append(host_docker_service.get_dict())

        containers = self.composeconcrete._containers
        services = self.composeconcrete.sorted_services
        for service in services:
            c_node = containers[service]

            #            print c_node.to_string()
            graph['nodes'].append(c_node.get_dict())

            # runs_on edge
            host = c_node.hostname
            if host:
                edge = RunsOn(c_node.id, host)
                #                print edge.to_string()
                graph['edges'].append(edge.get_dict())

            deps = c_node.s_depends_on
            if deps:
                for dep in deps:
                    edge = DependsOn(c_node.id, dep)
                    #                    print edge.to_string()
                    graph['edges'].append(edge.get_dict())

        deployment['status'] = "normal"
        deployment['graph'] = graph
        print json.dumps(deployment, indent=2)
        if outfile:
            json.dump(deployment, open(outfile, 'w'), indent=2)
        return deployment


class K2Platform:
    def __init__(self):
        self.client = None

    @classmethod
    def up(cls, args):
        parameter = ''
        if args.d:
            parameter += ' -d'
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))

        if args.force_update:
            k2compose.pull(services=args.services)
            k2compose.stop(services=args.services)
        k2compose.up(services=args.services, parameter=parameter,
                     ignore_deps=args.ignore_deps,
                     confirm_update=args.y)
        status_store(args)
        logging.debug('k2-compose up')

    @classmethod
    def ps(cls, args):
        logging.debug('k2-compose ps')
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        status = k2compose.ps(services=args.services, json_format=args.json, json_outfile=args.json_file)
        if len(status.values()) == 1:
            sys.exit(status.values()[0] - 3)

    @classmethod
    def start(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.start(services=args.services)
        status_store(args)
        logging.debug('k2-compose start')

    @classmethod
    def logs(cls, args):
        parameter = ''
        if args.follow:
            parameter += ' --follow'
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.logs(services=args.services, parameter=parameter)
        logging.debug('k2-compose logs')

    @classmethod
    def stop(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.stop(services=args.services)
        status_store(args)
        logging.debug('k2-compose stop')

    @classmethod
    def restart(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.restart(services=args.services)
        status_store(args)
        logging.debug('k2-compose restart')

    @classmethod
    def rm(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.rm(services=args.services, force=args.force)
        status_store(args)
        logging.debug('k2-compose rm')

    @classmethod
    def pull(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.pull(services=args.services)
        logging.debug('k2-compose pull')

    @classmethod
    def images(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.images(args=args, services=args.services)
        logging.debug('k2-compose images')

    @classmethod
    def bash(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.bash(services=args.services)
        logging.debug('k2-compose bash')

    @classmethod
    def show(cls, args):
        k2compose = ComposeFile(filename=args.file, url=args.url)
        k2compose.show(services=args.services)
        logging.debug('k2-compose show')

    @classmethod
    def inspect(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.inspect(services=args.services)
        logging.debug('k2-compose inspect')

    @classmethod
    def save(cls, args):
        k2compose = K2ComposeCMD(ComposeConcrete(filename=args.file, url=args.url))
        k2compose.save(suffix=args.suffix, services=args.services, only_tag=args.only_tag, only_push=args.only_push,
                       no_interaction=args.no_interaction, text=args.text)
        logging.debug('k2-compose save')
    #
    # def config(self, args):
    #     print Color('{autored}NOTICE: You can define network_mode by using --net=[host,bridge,overlay,none]. default is overlay.{/autored}')
    #
    #     sel = Selector()
    #     if args.input_config:
    #         config = yaml.load(open(args.input_config))
    #         kmx_version = config.get('kmx-version', None)
    #     else:
    #         config = sel.ask_for_version()
    #         kmx_version = config.get('kmx-version', None)
    #
    #     if kmx_version is None:
    #         print "Missing kmx-version"
    #         sys.exit(-1)
    #     composer = sel.get_composer(kmx_version)
    #     if composer is None:
    #         print "Invalid kmx-version %s. Select from %s" % (
    #             kmx_version, json.dumps(sel.available_versions))
    #         sys.exit(-1)
    #
    #     if args.net:
    #         try:
    #             composer.set_network(args.net)
    #         except Exception as e:
    #             print Color("{autored}"+e.message +"{/autored}")
    #             sys.exit(-1)
    #         else:
    #             print Color("{autored}NOTICE: Use %s network_mode.{/autored}"%args.net)
    #     else:
    #         print Color("{autored}NOTICE: Use overlay network_mode by default.{/autored}")
    #
    #     time.sleep(2)
    #
    #     if args.input_config:
    #         composer.set_config(yaml.load(open(args.input_config)))
    #     else:
    #         composer.ask_for_config()
    #
    #     if args.only_save:
    #         composer.save()
    #         print '--only-save will be discarded in future version b/c user answer is always saved'
    #     else:
    #         composer.save()
    #         composer.optimize()
    #         composer.confirm()
    #         composer.generate_main()
    #         composer.generate_init()
    #         composer.generate_utils()
    #         composer.generate_misc()
    #         composer.generate_monitor()
    #
    #         composer.update_extra_hosts()
    #         print 'Ready to fire! (Of course you may make necessary changes to those compose files)'

    def _load_compose_file_for_agent(self, filename, url=None):
        # auto-detecting cluster and overlay network
        start_time = time.time()
        compose_concrete = ComposeConcrete(filename=filename, url=url)

        logging.debug("%s consumed loading compose file" % (time.time() - start_time))
        # check cluster
        clusters = {}
        logging.debug('Checking docker cluster info...')
        for host_name, host_instance in compose_concrete.hosts_instance.items():
            if host_instance.status_code == HOST_DISCONNECT:
                continue
            cli = host_instance.client
            try:
                info = cli.info()
            except (errors.APIError, errors.DockerException) as e:
                logging.error(e.message)
            except Exception as e:
                logging.error(e.message)
            else:
                clusters.update({host_name: info['ClusterStore']})

        # if len(set(clusters.values())) > 1:
        #     print Color(
        #         '{autored}Not all docker hosts shares the same cluster store. Are they really in the same cluster?{/autored}')
        #     sys.exit(-1)
        # else:
        #     cluster = clusters.values()[0]
        cluster = clusters.values()[0]
        net = compose_concrete.net
        print 'summary of status data tags:'
        print '\tnet=%s' % net
        print '\tdeployment=%s' % compose_concrete.project
        # print '\tcomponent=one of %s' % json.dumps(compose_concrete.services.keys())
        print '\tgroup=<beginning time of a check>'
        return {
            'cluster': cluster,
            'net': net,
            'compose_concrete': compose_concrete
        }

    def agent(self, args):
        print 'status_check_interval=%s' % args.interval
        print 'status_store=%s' % args.status_store
        print 'dry run=%s' % args.dry_run
        print 'auto-reload=%s' % args.auto_reload
        print 'service check list=%s' % args.services
        print 'restart if unhealthy=%s' % args.restart_if_unhealthy
        writer = db_writer.Writer(args.status_store)

        loaded_compose = self._load_compose_file_for_agent(filename=args.file, url=args.url)

        while True:
            start_loop_ts = time.time()

            cluster = loaded_compose['cluster']
            net = loaded_compose['net']
            compose_concrete = loaded_compose['compose_concrete']
            service_result = {
                'tags': {
                    'cluster': cluster,
                    'net': net,
                    'deployment': compose_concrete.project,
                    'group': long(time.time() * 1000 * 1000 * 1000),  # nano
                },
                'services': {}
            }
            host_result = {
                'tags': {
                    'cluster': cluster,
                    'deployment': compose_concrete.project,
                    'group': long(time.time() * 1000 * 1000 * 1000),  # nano
                },
                'hosts': {}
            }
            container_cpu_result = {
                'tags': {
                    'cluster': cluster,
                    'deployment': compose_concrete.project,
                },
                'cpu': {}
            }
            container_mem_result = {
                'tags': {
                    'cluster': cluster,
                    'deployment': compose_concrete.project,
                },
                'mem': {}
            }

            print '\thost=one of %s' % loaded_compose['compose_concrete'].hosts

            for host_name, host_instance in loaded_compose['compose_concrete'].hosts_instance.items():
                start_time = time.time()
                if host_instance.status_code == HOST_CONNECT:
                    host_result['hosts'].update({host_instance.metadata['dockerHost']: (start_time, HOST_CONNECT)})
                else:
                    host_result['hosts'].update({host_instance.metadata['dockerHost']: (start_time, HOST_DISCONNECT)})
            writer.write(host_result)  # hosts health

            services = compose_concrete.check_service(args.services)

            print '\tcomponent=one of %s' % (services)

            for s in services:
                start_time = time.time()
                status = compose_concrete.ps(services=[s], ignore_deps=True)
                print status
                if status.get(s) == SERVICE_RUNNING or status.get(s) == SERVICE_ERROR:
                    container = compose_concrete.getcontainer(s)
                    cpu_percent, mem_percent, mem_limit = container.stats()
                    if cpu_percent is not None and mem_percent is not None:
                        container_cpu_result['cpu'].update({s: (start_time, cpu_percent)})
                        container_mem_result['mem'].update({s: (start_time, mem_percent, mem_limit)})
                start_time = time.time()
                service_result['services'].update({s: (start_time, status.get(s))})
                if args.dry_run:
                    print service_result
                else:
                    writer.write(service_result)
                if args.restart_if_unhealthy is not None and s in args.restart_if_unhealthy:
                    if status.get(s) != SERVICE_RUNNING and status.get(s) != SERVICE_UNDEPLOYED:
                        print 'restarting %s (status=%s)' % (s, status.get(s))
                        compose_concrete.restart(services=[s])
                # host = compose_concrete.get_host_instance_by_containerid(s)
                # host_result['hosts'].update({host.metadata['dockerHost']: (start_time, host.status_code)})
            writer.write(container_cpu_result)
            writer.write(container_mem_result)
            if time.time() - start_loop_ts < args.interval:
                time.sleep(args.interval)
            if args.auto_reload:
                loaded_compose = self._load_compose_file_for_agent(filename=args.file, url=args.url)


class Cmdline:
    L1_SUB_COMMANDS = ['up', 'ps', 'start', 'stop', 'restart', 'rm', 'logs',
                       # 'pull', 'bash', 'config', 'agent', 'show', 'images', 'inspect', 'save']
                        'pull', 'bash', 'agent', 'show', 'images', 'inspect', 'save']

    @classmethod
    def cmdline(cls):
        parser = argparse.ArgumentParser(description='K2Data platform command line tool')
        parser.add_argument('--debug', '-d', action='store_true', help='debug mode')
        # parser.add_argument('-v', '--verbose', action='store_true', help='verbose')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--file', '-f', help='k2 compose file', default='k2-compose.yml')
        group.add_argument('--url', help='k2 compose file via http')
        # group.add_argument('--project','-p', help='k2 compose project name;support path/to/project,eg ${PWD}/project')
        subparsers = parser.add_subparsers(title='subcommands',
                                           description='valid subcommands',
                                           help='sub-commands')
        k2platform = K2Platform()
        for c in cls.L1_SUB_COMMANDS:
            command_parser = subparsers.add_parser(c)
            # map handler funcs by name,
            # e.g., "k2 list" goes to func "list" in K2Platform class
            command_parser.set_defaults(func=getattr(k2platform, c))
            # set extra parameters by calling corresponding funcs
            getattr(cls, c)(k2platform, command_parser)

        args, others = parser.parse_known_args()
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.debug("debug mode enabled")
            global DEBUG
            DEBUG = True
        # env(args)
        return args

    @classmethod
    def up(cls, cs, parser):
        parser.add_argument(
            '-d',
            action='store_true',
            help="Detached mode: Run containers in the background"
        )
        parser.add_argument(
            '-y',
            action='store_true',
            help="Don't ask to confirm update"
        )
        parser.add_argument(
            '--ignore-deps',
            action='store_true',
            help='ignore dependency order of containers'
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='update container. if the container is exist, this cmd will pull image, stop and recreate it.'
        )
        parser.add_argument(
            'services',
            nargs='*',
            help='service (chain) to run'
        )

    @classmethod
    def ps(cls, cs, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='output in json format'
        )

        parser.add_argument(
            "--json-file",
            help='output in json format and write to file'
        )

        parser.add_argument(
            'services',
            nargs='*',
            help='services to ps'
        )

    @classmethod
    def stop(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='*',
            help="services to stop"
        )

    @classmethod
    def restart(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='+',
            help="services to restart"
        )

    @classmethod
    def rm(cls, cs, parser):
        parser.add_argument(
            '-f',
            '--force',
            action='store_true',
            help="Don't ask to confirm removal"
        )
        parser.add_argument(
            "services",
            nargs='+',
            help="Removes stopped service containers."
        )

    @classmethod
    def logs(cls, cs, parser):
        parser.add_argument(
            '-f',
            '--follow',
            action='store_true',
            help='Follow log output'
        )
        parser.add_argument(
            "services",
            nargs='+',
            help="Displays log output from services."
        )

    @classmethod
    def pull(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='*',
            help="Pulls service images."
        )

    @classmethod
    def images(cls, cs, parser):
        parser.add_argument(
            '--config',
            action='store_true',
            help="switch image among history"
        )
        parser.add_argument(
            "services",
            nargs=1,
            help="show image and history for given service."
        )

    @classmethod
    def start(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='+',
            help="Starts existing containers for a service."
        )

    @classmethod
    def bash(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs=1,
            help="Execute bash in running container."
        )

    @classmethod
    def show(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='*',
            help="Show service and topological infomation described in YML."
        )

    @classmethod
    def inspect(cls, cs, parser):
        parser.add_argument(
            "services",
            nargs='*',
            help="Show image label information."
        )

    @classmethod
    def save(cls, cs, parser):

        parser.add_argument(
            "services",
            nargs='*',
            help="Save image from the service."
        )

        parser.add_argument(
            '--suffix',
            required=True,
            help="Save image with suffix."
        )

        parser.add_argument(
            '--only-tag',
            action='store_true',
            help="Only tag image"
        )

        parser.add_argument(
            '--only-push',
            action='store_true',
            help="Only push image"
        )

        parser.add_argument(
            '--no-interaction',
            action='store_true',
            help="No interaction"
        )

        parser.add_argument(
            '--text',
            action='store_true',
            help="output format"
        )

    # @classmethod
    # def config(cls, cs, parser):
    #     parser.add_argument('--input-config', '-i', help='config file')
    #     parser.add_argument('--net', '-n', help='define network mode, select from [host,bridge,overlay,none], default is overlay.')
    #     parser.add_argument('--only-save', action='store_true', default=False, help='save answers into a file')

    @classmethod
    def agent(cls, cs, parser):
        parser.add_argument('--interval', default=30,
                            help='sleep time between to check group (not exactly sample interval)')
        parser.add_argument('--status-store',
                            default='influxdb://localhost:8086',
                            help='Health status store')
        parser.add_argument('--auto-reload', action='store_true', default=False,
                            help='reload compose file before each check interval')
        parser.add_argument('--restart-if-unhealthy',
                            action='append',
                            help='list of services to restart if unhealthy')
        parser.add_argument('--dry-run',
                            action='store_true',
                            help='dry run, do not actually write result to database')
        parser.add_argument(
            'services',
            nargs='*',
            help='service (chain) to run'
        )


def run():
    args = Cmdline.cmdline()
    args.func(args)


if __name__ == '__main__':
    run()
