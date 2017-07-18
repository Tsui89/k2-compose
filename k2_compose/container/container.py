import os
import time
import signal
import logging
import subprocess

from docker import errors
from ..compose_file.compose_file import ComposeService
from ..common.common import *
from ..k2cutils.class_utils import cached_property
from ..image.image_history import ImageHistory
from ..compose_utils.confirm_input import confirm_input
from ..image.image_show import ImageInspect

from colorclass import Color


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


class Container(ComposeService):
    def __init__(self, id='', service=None, hostip='',project=DOCKER_PROJECT_PREFIX, docker_compose_file=DOCKER_COMPOSE_FILE):
        ComposeService.__init__(self, id=id, service=service)
        self._hostip = hostip
        self._client = None
        # self._service = service
        self._image_status = 'unchanged'
        # self._inspect_image=
        self.project = project
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