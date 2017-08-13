# -*- coding:utf-8 -*-
import copy
import logging
import os
import re
import sys
import time
import json
import yaml
from multiprocessing.dummy import Pool as ThreadPool

import requests
from colorclass import Color
from pick import pick
from terminaltables import SingleTable, AsciiTable

from ..common.common import *
from ..host.host import Host, host_connect
from ..container.container import Container
from ..image.image_show import ImageInspect
from ..k2cutils.class_utils import cached_property
from ..k2cutils.confirm_input import confirm_input
from ..k2cutils.toposort import toposort
from ..service.service import ComposeService
from ..agent.opentsdb import OpenTSDB_Sender
from ..agent.grafana import *


def check_compose_file(filename):
    if not os.path.isfile(filename):
        logging.error("Yaml [%s] does not exist" % (filename))
        return False

    try:
        yaml.safe_load(open(filename))
        # print compose_data
    except Exception as e:
        # logging.error(e)
        logging.error("Yaml format error, %s" % e)
        return False

    return True


class ComposeFile(object):
    def __init__(self, **kwargs):
        self.stream = None
        self.stream_name = ''
        self._safe_load(**kwargs)

        self.project = filter(str.isalnum, self.get_project())
        self.docker_compose_file = '.%s-compose.yml' % (self.project)

        self.sorted_services = self.sort()

    def _safe_load(self, filename=None, url=None):
        if os.environ.get("DEPLOYMENT_URL") and not url:
            url = os.environ.get("DEPLOYMENT_URL") + "/files/" + filename
        if url:
            try:
                rsp = requests.get(url)
                if rsp.status_code != 200:
                    logging.error('error get url %s: %s %s' % (
                    url, rsp.status_code, rsp.reason))
                rsp_json = rsp.json()
                file_content = rsp_json.get(
                    'content') if 'content' in rsp_json else rsp_json[
                    'body'].get('content')
                self.stream = yaml.safe_load(file_content)
                self.stream_name = url

            except Exception as e:
                logging.error('error get url %s: %s' % (url, e))
        elif check_compose_file(filename):
            self.stream = yaml.safe_load(open(filename))
            self.stream_name = filename
        else:
            sys.exit(-1)

    def get_project(self):
        try:
            project = self.stream.get('project', os.path.basename(
                os.path.dirname(os.path.realpath(self.stream_name))))
            return project
        except:
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
            data = self.stream.get('hosts', {})
            for s, v in self.services.items():
                if not v.has_key('host'):
                    docker_host = os.getenv("DOCKER_HOST", DOCKER_HOST_DEFAULT)
                    data.update({'default': docker_host})
                    break
            return data
        except KeyError:
            return {}

    @cached_property
    def services(self):
        return self.stream.get('services')

    def get_host_ip_by_hostname(self, id='default'):
        hosts = self.hosts
        return hosts.get(id)

    def get_service(self, id=''):
        try:
            return self.services.get(id)
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

        match_record = {}
        for s in services:
            match_record.update({s: 0})

        if services:
            # compile regular
            for service in services:
                tmp = service.replace('*', '.*')
                if re.search(r'\[\d-\d\]$', tmp) or '*' in tmp:
                    re_services.update({service: re.compile(r'%s' % tmp)})

            for service in self.sorted_services:

                if service in services:
                    tmp_services.append(service)
                    match_record[service] = match_record.get(service, 0) + 1

                for s, re_s in re_services.items():
                    if re_s.match(service):
                        if service not in tmp_services:
                            tmp_services.append(service)
                            match_record[s] = match_record.get(s, 0) + 1
                        else:
                            match_record[s] = match_record.get(s, 0) + 1
        else:
            tmp_services.extend(self.sorted_services)
        for s, s_match in match_record.items():
            if s_match == 0:
                logging.error('%s %s not match any service in YML.' % (msg, s))

        logging.debug("%s Match Results: %s" % (msg, match_record))
        # return set(tmp_services)
        return tmp_services

    def show(self, services=None):

        if services:
            services = self.check_service(services, msg='In SHOW:')
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
                if service_information.get('host', 'default') == host:
                    services.append(service)
            services.sort()
            services = yaml.dump(services, default_flow_style=False).strip('\n')

            table_data.append([host, dockerHost, services])
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table

    def create_grafana_dashbord(self, services=None, prefix=None,delay=30):
        services = self.check_service(services)
        metric_prefix = self.metric_prefix(prefix)
        dashboad = Dashboard(title=metric_prefix)

        row_hosts = Row(title='Hosts Status')
        row_hosts.height='90px'

        metric = "%s.%s" % (metric_prefix, HOSTS_METRIC)
        for host in sorted(self.hosts.keys()):
            description =self.hosts[host]
            panel = PanelNew(title=host,measurement=metric,
                             value=host,key='host',
                             description=description,
                             delay=delay)
            row_hosts.add_panel(panel)

        dashboad.add_row(row_hosts)
        row_services = Row(title='Services Status')
        row_services.height='90px'
        for service in services:
            service_detail = self.get_service(service)
            run_on = service_detail.get('host','default')
            metric = "%s.%s" % (metric_prefix, SERVICES_METRIC)
            panel = PanelNew(title=service,measurement=metric,
                             value=service,key='service',delay=delay,
                             description='Runs on %s'%(run_on))
            row_services.add_panel(panel)
        dashboad.add_row(row_services)

        for service in services:
            row_service = Row(title='Container '+service)

            metric = "%s.%s.%s" % (metric_prefix, CONTAINERS_METRIC, service)
            target = Target(service,metric,type="health_check")
            description='-20002ms undeployed\n\n' \
                        '-20001ms stopped\n\n' \
                        '<0ms error\n\n' \
                        '\\>=0ms running'
            panel = Panel(title='Health Check',yaxes_l='none', label_l=u"响应时间 ms",
                          description=description)
            panel.add_target(target)
            row_service.add_panel(panel)

            panel = Panel(title='Memory',yaxes_l = 'decmbytes',yaxes_r='percent')
            for t in ['mem_limit', 'mem_usage','mem_utilization']:
                metric = "%s.%s.%s"%(metric_prefix, CONTAINERS_METRIC, service)
                target = Target(t, metric,type=t)
                panel.add_target(target)
            row_service.add_panel(panel)

            panel = Panel(title='CPU Utilization',yaxes_l = 'percent')
            for t in ['cpu_utilization']:
                metric = "%s.%s.%s"%(metric_prefix, CONTAINERS_METRIC, service)
                target = Target(t, metric,type=t)
                panel.add_target(target)
            row_service.add_panel(panel)

            dashboad.add_row(row_service)
        json.dump(dashboad.__dict__,open('%s-dashboard.json'%metric_prefix,'w+'),indent=2)

    def metric_prefix(self, prefix=None):
        _deployment = self.project.__str__()
        if prefix:
            _prefix = prefix if prefix.endswith('.') else prefix + '.'
        else:
            _prefix = ""
        return _prefix + _deployment


class ComposeConcrete(ComposeFile):
    def __init__(self, **kwargs):
        ComposeFile.__init__(self, **kwargs)
        self.hosts_instance = {}
        self._containers = {}
        self.generate_yml()
        self.concrete()

    def set_host_instance(self, host_object):
        self.hosts_instance.__setitem__(host_object.id, host_object)

    def set_container_instance(self, composeservice_object):
        self._containers.__setitem__(composeservice_object.id,
                                     composeservice_object)

    def get_host_instance_by_container_id(self, service):
        container = self._containers.get(service)
        try:
            return self.hosts_instance.get(container.hostname)
        except KeyError:
            logging.error('Get service [%s]`s host[%s] error.' % (
                service, container.host))
            return None

    def get_container_instance_by_service_name(self, service):
        return self._containers.get(service)

    def get_host_instance_by_hostname(self, id):
        host = self.hosts_instance.get(id)
        if host:
            return host
        else:
            logging.error('Get host[%s] error.' % (id))
            sys.exit(-1)

    def generate_yml(self):
        parse_key = [DEPENDS_KEY, HEALTH_CHECK_KEY, HOST_KEY, URLS_KEY]
        stream_tmp = copy.deepcopy(self.stream)

        for key in [HOSTS_KEY, PROJECT_KEY, CM_SERVER_KEY]:
            if key in stream_tmp:
                stream_tmp.pop(key)

        # load extra_hosts
        _extra_hosts = {}
        if stream_tmp.has_key(S_EXTRA_HOSTS):
            _extra_hosts = stream_tmp.pop(S_EXTRA_HOSTS)

        for service_name, service in stream_tmp['services'].items():
            for key in parse_key:
                if service.has_key(key):
                    service.pop(key)

            if self.driver == 'bridge' and service.get('network_mode',
                                                       '') != 'host':
                if not service.has_key('extra_hosts'):
                    service['extra_hosts'] = {}
                service['extra_hosts'].update(_extra_hosts)

                # extra_hosts = service.get('extra_hosts',{})
                # extra_hosts.update(_extra_hosts)
        yaml.safe_dump(stream_tmp, open(self.docker_compose_file, 'w+'),
                       default_flow_style=False, width=float("inf"))

    def build_host(self, id='default'):
        try:
            return Host(id, self.get_host_ip_by_hostname(id))
        except KeyError:
            return None

    def build_service(self, id=''):

        service = ComposeService(id, self.get_service(id))
        hostip = self.get_host_ip_by_hostname(service.hostname)

        try:
            container = Container(id=id, service=self.get_service(id),
                                  hostip=hostip, project=self.project,
                                  docker_compose_file=self.docker_compose_file)
        except KeyError:
            return None
        else:
            container.client = self.get_host_instance_by_hostname(
                service.hostname).client
            return container

    def concrete(self):
        pool = ThreadPool(len(self.hosts))
        host_instances = []
        for host in self.hosts:
            instance = self.build_host(host)
            self.set_host_instance(instance)
            host_instances.append(instance)
        pool.map(host_connect, host_instances)
        pool.close()
        pool.join()
        for service_name in self.services.keys():
            container = self.build_service(service_name)
            self.set_container_instance(container)

    def ps(self, services=None, ignore_deps=False, parameter=''):
        result = {}
        services = self.check_service(services, msg='In PS:')

        if services != self.sorted_services:
            if ignore_deps is False:
                depends_all = []
                for service in services:
                    container = self.get_container_instance_by_service_name(
                        service)
                    depends_all.extend(container.s_depends_on)
                services.extend(depends_all)
        services = list(set(services))

        pool_containers = []
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            status_code = -1
            if host.status != 'running':
                result.update({service: status_code})
                continue
            pool_containers.append(
                self.get_container_instance_by_service_name(service))
        if services and len(pool_containers) > 0:
            pool = ThreadPool(len(pool_containers))
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
            ['Service', 'Host', 'Service-Status', 'Image-Status', 'Depends-On',
             'Ports', 'Network-Mode', 'Stats'])

        try:
            default_network = self.stream['networks']['default']['driver']
        except:
            default_network = 'bridge'

        for service in services:
            container = self.get_container_instance_by_service_name(service)
            host = self.get_host_instance_by_container_id(service)
            image_status = ''

            host_color = "{autobgwhite}{%s}%s{/%s}{/autobgwhite}" % (
                host.color, container.hostip, host.color)
            container_color = "{autobgwhite}{%s}%s{/%s}{/autobgwhite}" % (
                container.color, container.status, container.color)
            if container._image_status == 'changed':
                image_status = container._image_status
            depends = ''
            for depend in container.s_depends_on:
                depend_container = self.get_container_instance_by_service_name(
                    depend)
                depend_container_color = "- {autobgwhite}{%s}%s{/%s}{/autobgwhite}\n" % (
                    depend_container.color, depend, depend_container.color)
                depends += (Color(depend_container_color))
            depends = depends.strip('\n')

            ports = ''
            for port in container.ports:
                ports += "- %s\n" % port
            ports = ports.strip('\n')

            nm = default_network if container.network_mode == '' else container.network_mode
            stats=''
            for s in ['cpu:'+str(container.cpu_utilization)+'%'+'\n',
                      'mem:'+str(container.mem_usage)+'m'+'\n',
                      'check:'+str(container.exec_time)+'ms']:
                stats +=s
            table_data.append([container.id, Color(host_color),
                               Color(container_color), image_status,
                               depends, ports, nm, stats])

        table_instance = AsciiTable(table_data)

        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table

    def up(self, services=None, ignore_deps=False, **kwargs):
        services = self.check_service(services, msg='In UP:')
        # if services == self.sorted_services:
        #     confirm_input('Going to start ALL-Services.')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('UP [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            if ignore_deps is False:
                if self.check_depends(service) is False:
                    global SYS_RETURN_CODE
                    SYS_RETURN_CODE = 179  # check depends error
                    continue

            container = self.get_container_instance_by_service_name(service)
            container.up(**kwargs)
            container.image_history.insert_current()
        sys.exit(SYS_RETURN_CODE)

    def check_depends(self, id):
        container = self.get_container_instance_by_service_name(id)
        for service_depends in container.s_depends_on:
            host = self.get_host_instance_by_container_id(service_depends)
            if host.status != 'running':
                logging.error('check_depends [%s]:'
                              ' Connect [%s] error.' % (
                                  service_depends, host.id))
                return False
            container_depends = self.get_container_instance_by_service_name(
                service_depends)
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
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('start [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.start()

    def logs(self, services=None, parameter=''):
        services = self.check_service(services, msg='In LOGS:')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('logs [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.logs(parameter)

    def stop(self, services=None, time=10):
        services = self.check_service(services, msg='In STOP:')
        if services == self.sorted_services:
            confirm_input('Going to stop ALL-Services.')
            services.reverse()
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('stop [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.stop(time=time)

    def restart(self, services=None):
        services = self.check_service(services, msg='In RESTART:')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('restart [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.restart()

    def bash(self, services=None):
        services = self.check_service(services, msg='In BASH:')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('bash [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.bash()

    def rm(self, services=None, **kwargs):
        services = self.check_service(services, msg='In RM:')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('rm [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.rm(**kwargs)

    def pull(self, services=None):
        services = self.check_service(services, msg='In PULL:')
        if services == self.sorted_services:
            confirm_input('Going to update ALL-Services Images.')
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                logging.error('pull [%s]:'
                              ' Connect [%s] error.' % (service, host.id))
                continue
            container = self.get_container_instance_by_service_name(service)
            container.pull()
            container.image_history.insert_current()

    def images(self, args, services=None):
        services = self.check_service(services, msg='In IMAGES:')

        for service in services:
            container = self.get_container_instance_by_service_name(service)
            container.image_history.insert_current()
            container.image_history.show()
            if args.config:
                sel = raw_input(
                    'Press enter to keep the current choics[*], or type index number: ')
                if sel == '':
                    return
                valid_choices = [str(i) for i in
                                 range(0, len(container.image_history.content))]
                if sel in valid_choices:
                    container.image_history.change_current(int(sel))
                else:
                    print 'Invalid Choice. Nothing Changed.'

    def _probe(self, services=None, merge=True):
        _results = []
        _results_async = []
        pool = ThreadPool(len(self.services))

        services_list = self.check_service(services, msg='In Inspect:')
        for service_name in services_list:
            host = self.get_host_instance_by_container_id(service_name)
            service = ComposeService(service_name,
                                     self.get_service(service_name))

            if host.status != 'running':
                _results.append(
                    ImageInspect(service=service_name, image=service.image)())
                continue
            else:
                container = self.get_container_instance_by_service_name(
                    service_name)
                _results_async.append(pool.apply_async(container.image_label))
        pool.close()
        pool.join()
        for r in _results_async:
            _results.append(r.get())
        _results.sort(key=lambda obj: obj.get('image'), reverse=False)

        if not merge:
            return _results

        _show_tmp = {}
        for r in _results:
            key = r['image'] + str(r['Id']) + r['Match']
            if not _show_tmp.has_key(key):
                _show_tmp[key] = {
                    'image': r['image'],
                    'service': r['service'],
                    'Id': r['Id'],
                    'Created': r['Created'],
                    'Labels': r['Labels'],
                    'Match': r['Match']
                }
            else:
                _show_tmp[key]['service'] += '\n' + r['service']
        return _show_tmp

    def inspect(self, services=None):

        _show_tmp = self._probe(services)
        table_data = []
        table_instance = SingleTable(table_data, self.stream_name)
        table_data.append(['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

        for key in sorted(_show_tmp.keys()):
            table_data.append(
                [_show_tmp[key]['image'] + '\n' + _show_tmp[key]['Match'],
                 _show_tmp[key]['service'],
                 _show_tmp[key]['Id'], _show_tmp[key]['Created'],
                 _show_tmp[key]['Labels']])
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table

    def save(self, suffix, services=None, only_tag=False, only_push=False,
             no_interaction=False, text=False):

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
            image='Image', service='Service', imageid='Image-Id', match='Match',
            longest_image=longest_image, longest_service=longest_service,
            longest_imageId=longest_imageId,
            longest_match=longest_match,
            ind='-',
            wedth=longest_image + longest_service + longest_imageId + longest_match + 9)

        for v in _show:
            table_data.append(
                '{image:<{longest_image}} | {service:<{longest_service}} | {imageid:<{longest_imageId}} | {match:<{longest_match}}'.format(
                    image=v['image'], service=v['service'], imageid=v['Id'],
                    match=v['Match'],
                    longest_image=longest_image,
                    longest_service=longest_service,
                    longest_imageId=longest_imageId,
                    longest_match=longest_match))

        selected_service = []
        if no_interaction:
            selected_service.extend(_show)
        else:
            try:
                selected = pick(table_data,
                                'Please choose your images for save (press SPACE to mark, ENTER to continue, Ctrl+C to exit): ' + title,
                                indicator='*', multi_select=True,
                                min_selection_count=0)
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
        _skip = False
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
                _action = Color('{autogreen}%s{/autogreen}' % (_action))
            else:
                _action = Color('{autored}%s{/autored}' % (_action))
                not_ready.append(s)
            print '{action:<25} {image_old:<{longest_image}} => {image_new:<{longest_image}}'.format(
                action=_action,
                longest_image=longest_image,
                image_old=s['image'],
                image_new=s['image'] + suffix)
        if only_tag:
            _msg = 'Tag these images.'
        elif only_push:
            _msg = 'Push these images.'
        else:
            _msg = 'Tag and Push these images.'
        if _skip:
            if no_interaction:
                _msg += Color(
                    '\n{autored}These service`s image is not ready, please fix it first.{/autored}')

                print _msg
                table_data = []
                table_instance = SingleTable(table_data, 'Not Ready')
                table_data.append(
                    ['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

                for s in not_ready:
                    table_data.append(
                        [s['image'] + '\n' + s['Match'], s['service'],
                         s['Id'], s['Created'], s['Labels']])
                table_instance.inner_heading_row_border = False
                table_instance.inner_row_border = True
                print table_instance.table
                sys.exit(-1)
            else:
                _msg += Color('\n{autored}Some service`s image is not ready. \n' \
                              'You can use k2-compose pull/up to fix it, otherwise these images will be skipped.{/autored}\n')
                confirm_input(msg=_msg)

        if not only_push:
            pool = ThreadPool(len(selected_service))
            for s in selected_service:
                if s['Action'] == 'do':
                    container = self.get_container_instance_by_service_name(
                        s['service'])
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
                container = self.get_container_instance_by_service_name(
                    s['service'])
                _result.append(pool.apply_async(container.push, (suffix,)))
        pool.close()
        pool.join()
        for r in _result:
            print r.get()
        print Color('{autogreen}Push all done.{/autogreen}\n')
        if text:
            print "#".join(
                ['Image', 'Service', 'Image-Id', 'Created', 'Labels'])
            for s in selected_service:
                print "#".join((s['image'], s['service'],
                                s['Id'], s['Created'],
                                s['Labels'].replace('\n', ' ')))
        else:
            table_data = []
            table_instance = SingleTable(table_data, 'Done')
            table_data.append(
                ['Image', 'Service', 'Image-Id', 'Created', 'Labels'])

            for s in selected_service:
                table_data.append(
                    [s['image'], s['service'],
                     s['Id'], s['Created'], s['Labels']])
            table_instance.inner_heading_row_border = False
            table_instance.inner_row_border = True
            print table_instance.table
        return

    def agent(self, services=None, prefix=None, opentsdb_http=None):
        services = self.check_service(services)
        if services == None:
            print 'None Services'
            return
        self.ps(services, ignore_deps=True)
        sender = self._sender
        if opentsdb_http != None:
            sender = OpenTSDB_Sender(server=opentsdb_http).send

        data = []
        metric_prefix = self.metric_prefix(prefix)

        for host_name, host_instance in self.hosts_instance.items():
            metric = "%s.%s" % (metric_prefix, HOSTS_METRIC)
            data.append(self._message(metric,
                                      value=1 if host_instance.status_code == 0 else 3,
                                      host=host_name))

        for service_name in services:
            container = self.get_container_instance_by_service_name(service_name)

            metric = "%s.%s" % (metric_prefix, SERVICES_METRIC)

            if container.exec_time == HEALTH_CHECK_EXEC_TIME_UNDEPLOYED:
                value = SERVICE_UNDEPLOYED
            elif container.exec_time == HEALTH_CHECK_EXEC_TIME_STOPPED:
                value = SERVICE_STOP
            elif container.exec_time >= 0:
                value = SERVICE_RUNNING
            else:
                value = SERVICE_ERROR
            data.append(self._message(metric,
                                      value=value,
                                      service=service_name))

            metric = "%s.%s.%s" % (
            metric_prefix, CONTAINERS_METRIC, service_name)
            data.append(self._message(metric,
                                      value=container.exec_time,
                                      type="health_check"))

            for t in ['mem_limit', 'mem_usage', 'mem_utilization', 'cpu_utilization']:
                metric = "%s.%s.%s" % (
                metric_prefix, CONTAINERS_METRIC, service_name)
                data.append(self._message(metric,
                                          value=getattr(container, t),
                                          type=t))

        sender(data)
        sys.stdout.flush()

    @classmethod
    def _message(cls, name, value, **kwargs):
        now = int(time.time())  # ms
        tags = []
        for k, v in kwargs.items():
            tags.append("%s=%s" % (k, str(v)))
        return "put {name} {now} {value} {tags}".format(name=name,
                                                        now=now,
                                                        value=value,
                                                        tags=' '.join(tags))

    @classmethod
    def _sender(cls, lines):
        for line in lines:
            print line

    def help(self, services=None):
        services = self.check_service(services, msg='In HELP:')

        result = {}
        pool_containers = []
        help_context = "Connect Error"
        for service in services:
            host = self.get_host_instance_by_container_id(service)
            if host.status != 'running':
                result.update({service: help_context})
                continue
            pool_containers.append(
                self.get_container_instance_by_service_name(service))
        if services and len(pool_containers) > 0:
            pool = ThreadPool(len(pool_containers))
            for container in pool_containers:
                pool.apply_async(container.help)

            pool.close()
            pool.join()

        for container in pool_containers:
            result.update({container.id: container.help_context})

        for k, res in result.items():
            print "%s Help:" % k
            for l in res.split('\n'):
                print "  ", l
            print "End\n"
