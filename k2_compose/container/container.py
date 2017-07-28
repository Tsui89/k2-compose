import logging
import os
import signal
import subprocess
import time

import requests
from colorclass import Color
from docker import errors

from ..common.common import *
from ..compose_utils.confirm_input import confirm_input
from ..image.image_history import ImageHistory
from ..image.image_show import ImageInspect
from ..k2cutils.class_utils import cached_property
from ..service.service import ComposeService


def http_get(url, timeout=None, description=None, show_message=True):
    _time_begin = time.time()
    url = url if url.startswith('http://') or url.startswith(
        'https://') else 'http://' + url
    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as e:
        logging.error("%s %s"%(description,e.message))
        return HEALTH_CHECK_EXEC_TIME_ERROR

    _exec_time = int((time.time() - _time_begin) * 1000)  # ms
    logging.debug("%s %s" % (description, resp.text))
    if resp.status_code == 200:
        return _exec_time
    else:
        return -_exec_time


def subprocesscmd(cmd_str='', timeout=None, description='', env=os.environ,
                  show_message=True):
    logging.debug('%s DOCKER_HOST=%s %s ' % (
        description, env.get('DOCKER_HOST',DOCKER_HOST_DEFAULT), cmd_str))

    os_env = os.environ
    env = os_env.update(env)
    poll_time = 0.2
    _time_begin = time.time()
    if show_message:
        stdout = None
        stderr = None
    else:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE
    try:
        ret = subprocess.Popen(cmd_str, stdout=stdout, stderr=stderr,
                               shell=True, env=env)
    except OSError as e:
        logging.error('%s %s %s %s' % (description, e, cmd_str, str(env)))
        return HEALTH_CHECK_EXEC_TIME_ERROR
    try:
        if timeout:
            deadtime = _time_begin + timeout
            while time.time() < deadtime and ret.poll() is None:
                time.sleep(poll_time)
        else:
            ret.wait()
    except KeyboardInterrupt:
        ret.send_signal(signal.SIGINT)
        logging.error('Aborted by user.')
        return HEALTH_CHECK_EXEC_TIME_ERROR

    _exec_time = int((time.time() - _time_begin) * 1000)  # ms

    if ret.poll() is None:
        ret.send_signal(signal.SIGINT)
        logging.error(
            '%s : Exec [%s] overtime.' % (description, cmd_str))
        return -_exec_time

    if not show_message:
        for line in ret.stdout:
            if line:
                logging.info('%s %s' % (description, line.strip('\n')))
        for line in ret.stderr:
            if line:
                logging.error('%s %s' % (description, line.strip('\n')))

    if ret.returncode == 0:
        return _exec_time
    else:
        return -_exec_time


class Container(ComposeService):
    def __init__(self, id='', service=None, hostip='',
                 project=DOCKER_PROJECT_PREFIX,
                 docker_compose_file=DOCKER_COMPOSE_FILE):
        ComposeService.__init__(self, id=id, service=service)
        self._hostip = hostip
        self._client = None
        self._image_status = 'unchanged'
        self.project = project
        self.exec_time = HEALTH_CHECK_EXEC_TIME_UNDEPLOYED
        self.docker_compose_file = docker_compose_file
        self.containerid = self.project + '_' + self.id + \
                           DOCKER_PROJECT_SUFFIX

        self.base_cmd = 'docker-compose -f %s -p %s ' % (
            self.docker_compose_file, self.project)

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
        history = ImageHistory.load(self.image_name, self.image_tag,
                                    self._hostip)
        return history if history is not None else ImageHistory(self.image_name,
                                                                self.image_tag,
                                                                self._hostip,
                                                                self._client)

    def check_client(self, msg=''):
        return True

    def ps(self):
        if self.status_code is SERVICE_UNDEPLOYED:
            return
        cmd = '%s ps %s' % (self.base_cmd, self.id)
        subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip},
                      description='ps detail:', show_message=False)

    def stats(self):
        try:
            stats = self.client.stats(self.containerid, stream=False,
                                      decode=True)
            mem_limit = stats['memory_stats']['limit']
            mem_percent = float(
                stats['memory_stats']['usage'] * 100) / mem_limit
            cpu_percent = 0.0
            cpu_delta = float(stats['cpu_stats']['cpu_usage']['total_usage']
                              - stats['precpu_stats']['cpu_usage'][
                                  'total_usage'])
            system_delta = float(
                stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats'][
                    'system_cpu_usage'])
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
        if self.status_code == SERVICE_UNDEPLOYED:
            self.exec_time = HEALTH_CHECK_EXEC_TIME_UNDEPLOYED
            return

        if self.status_code == SERVICE_STOP:
            self.exec_time = HEALTH_CHECK_EXEC_TIME_STOPPED
            return

        health_check = self.health_check
        #health check , set exec_time
        timeout = health_check.get('timeout', 10)
        if health_check.has_key('shell'):
            cmd = health_check.get('shell', '')

            if cmd:
                self.exec_time = subprocesscmd(cmd, timeout, show_message=False,
                                               description='In [%s] health check:' % self.id)

            else:
                self.exec_time = HEALTH_CHECK_EXEC_TIME_RUNNING
        elif health_check.has_key('http'):
            url = health_check.get('http', '')
            if url:
                self.exec_time = http_get(url, timeout=timeout, show_message=False,
                                          description='In [%s] health check:' % self.id)
            else:
                self.exec_time = HEALTH_CHECK_EXEC_TIME_RUNNING
        else:
            self.exec_time = HEALTH_CHECK_EXEC_TIME_RUNNING

        #set container status_code
        if self.exec_time >= HEALTH_CHECK_EXEC_TIME_RUNNING:
            self.status_code = SERVICE_RUNNING
        else:
            self.status_code = SERVICE_ERROR

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
        cmd = 'docker-compose -f %s -p %s up %s %s' % (
            self.docker_compose_file, self.project, parameter,
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
            self.docker_compose_file, self.project, parameter, self.id)
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
        print Color(
            '{autored}#####In [%s] Container#####{/autored}' % (self.id))
        cmd = '%s exec %s bash' % (self.base_cmd, self.id)
        if subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip}) <0 :
            #use sh
            cmd = '%s exec %s sh' % (self.base_cmd, self.id)
            subprocesscmd(cmd, env={'DOCKER_HOST': self.hostip})
        print Color(
            '{autored}#####Out [%s] Container#####{/autored}' % (self.id))

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
        from ..common.common import get_debug
        if get_debug():
            container_instance.ps()

    def image_label(self):

        try:
            container_inspect = self.client.inspect_container(self.containerid)
        except:
            imageid = self.image
        else:
            imageid = container_inspect.get('Image')

        try:
            data = self.client.inspect_image(imageid)
        except:
            return ImageInspect(service=self.id, image=self.image)()
        else:
            return ImageInspect(service=self.id, image=self.image, **data)()

    def tag(self, suffix):
        index = self.image.rfind(':')
        _repository = self.image[:index]
        _tag = self.image[index + 1:] + suffix
        print 'Tagging %s => %s:%s ...' % (self.image, _repository, _tag)
        try:
            self.client.tag(image=self.image, repository=_repository, tag=_tag)
        except Exception as e:
            print e.message
            return False
        else:
            return True

    def push(self, suffix):
        index = self.image.rfind(':')
        _repository = self.image[:index]
        _tag = self.image[index + 1:] + suffix
        message = self.id
        # print 'Pushing %s:%s ...'%(_repository,_tag)
        try:
            # print 'push is running. please wait...'
            for _result in self.client.push(repository=_repository, tag=_tag,
                                            stream=True):
                r = eval(_result)
                try:
                    message += " => " + r['aux']['Digest']
                except:
                    pass

                try:
                    message += " => " + Color(
                        "{autored}%s{/autored}" % r['error'])
                except:
                    pass

        except Exception as e:
            print e
            return message
        else:
            # print 'Done.'
            return message
