#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from __future__ import print_function

import os
import sys
import json
import time
import argparse
import logging

# from health_agent import db_writer
from docker import  errors

from compose_utils.basenode import  DependsOn, RunsOn
from common.common import *
from compose_file.compose_file import ComposeConcrete, ComposeFile

logging.basicConfig(format='%(levelname)s: %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')

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

    # def _load_compose_file_for_agent(self, filename, url=None):
    #     # auto-detecting cluster and overlay network
    #     start_time = time.time()
    #     compose_concrete = ComposeConcrete(filename=filename, url=url)
    #
    #     logging.debug("%s consumed loading compose file" % (time.time() - start_time))
    #     # check cluster
    #     clusters = {}
    #     logging.debug('Checking docker cluster info...')
    #     for host_name, host_instance in compose_concrete.hosts_instance.items():
    #         if host_instance.status_code == HOST_DISCONNECT:
    #             continue
    #         cli = host_instance.client
    #         try:
    #             info = cli.info()
    #         except (errors.APIError, errors.DockerException) as e:
    #             logging.error(e.message)
    #         except Exception as e:
    #             logging.error(e.message)
    #         else:
    #             clusters.update({host_name: info['ClusterStore']})
    #
    #     # if len(set(clusters.values())) > 1:
    #     #     print Color(
    #     #         '{autored}Not all docker hosts shares the same cluster store. Are they really in the same cluster?{/autored}')
    #     #     sys.exit(-1)
    #     # else:
    #     #     cluster = clusters.values()[0]
    #     cluster = clusters.values()[0]
    #     net = compose_concrete.net
    #     print 'summary of status data tags:'
    #     print '\tnet=%s' % net
    #     print '\tdeployment=%s' % compose_concrete.project
    #     # print '\tcomponent=one of %s' % json.dumps(compose_concrete.services.keys())
    #     print '\tgroup=<beginning time of a check>'
    #     return {
    #         'cluster': cluster,
    #         'net': net,
    #         'compose_concrete': compose_concrete
    #     }
    #
    # def agent(self, args):
    #     print 'status_check_interval=%s' % args.interval
    #     print 'status_store=%s' % args.status_store
    #     print 'dry run=%s' % args.dry_run
    #     print 'auto-reload=%s' % args.auto_reload
    #     print 'service check list=%s' % args.services
    #     print 'restart if unhealthy=%s' % args.restart_if_unhealthy
    #     writer = db_writer.Writer(args.status_store)
    #
    #     loaded_compose = self._load_compose_file_for_agent(filename=args.file, url=args.url)
    #
    #     while True:
    #         start_loop_ts = time.time()
    #
    #         cluster = loaded_compose['cluster']
    #         net = loaded_compose['net']
    #         compose_concrete = loaded_compose['compose_concrete']
    #         service_result = {
    #             'tags': {
    #                 'cluster': cluster,
    #                 'net': net,
    #                 'deployment': compose_concrete.project,
    #                 'group': long(time.time() * 1000 * 1000 * 1000),  # nano
    #             },
    #             'services': {}
    #         }
    #         host_result = {
    #             'tags': {
    #                 'cluster': cluster,
    #                 'deployment': compose_concrete.project,
    #                 'group': long(time.time() * 1000 * 1000 * 1000),  # nano
    #             },
    #             'hosts': {}
    #         }
    #         container_cpu_result = {
    #             'tags': {
    #                 'cluster': cluster,
    #                 'deployment': compose_concrete.project,
    #             },
    #             'cpu': {}
    #         }
    #         container_mem_result = {
    #             'tags': {
    #                 'cluster': cluster,
    #                 'deployment': compose_concrete.project,
    #             },
    #             'mem': {}
    #         }
    #
    #         print '\thost=one of %s' % loaded_compose['compose_concrete'].hosts
    #
    #         for host_name, host_instance in loaded_compose['compose_concrete'].hosts_instance.items():
    #             start_time = time.time()
    #             if host_instance.status_code == HOST_CONNECT:
    #                 host_result['hosts'].update({host_instance.metadata['dockerHost']: (start_time, HOST_CONNECT)})
    #             else:
    #                 host_result['hosts'].update({host_instance.metadata['dockerHost']: (start_time, HOST_DISCONNECT)})
    #         writer.write(host_result)  # hosts health
    #
    #         services = compose_concrete.check_service(args.services)
    #
    #         print '\tcomponent=one of %s' % (services)
    #
    #         for s in services:
    #             start_time = time.time()
    #             status = compose_concrete.ps(services=[s], ignore_deps=True)
    #             print status
    #             if status.get(s) == SERVICE_RUNNING or status.get(s) == SERVICE_ERROR:
    #                 container = compose_concrete.getcontainer(s)
    #                 cpu_percent, mem_percent, mem_limit = container.stats()
    #                 if cpu_percent is not None and mem_percent is not None:
    #                     container_cpu_result['cpu'].update({s: (start_time, cpu_percent)})
    #                     container_mem_result['mem'].update({s: (start_time, mem_percent, mem_limit)})
    #             start_time = time.time()
    #             service_result['services'].update({s: (start_time, status.get(s))})
    #             if args.dry_run:
    #                 print service_result
    #             else:
    #                 writer.write(service_result)
    #             if args.restart_if_unhealthy is not None and s in args.restart_if_unhealthy:
    #                 if status.get(s) != SERVICE_RUNNING and status.get(s) != SERVICE_UNDEPLOYED:
    #                     print 'restarting %s (status=%s)' % (s, status.get(s))
    #                     compose_concrete.restart(services=[s])
    #             # host = compose_concrete.get_host_instance_by_containerid(s)
    #             # host_result['hosts'].update({host.metadata['dockerHost']: (start_time, host.status_code)})
    #         writer.write(container_cpu_result)
    #         writer.write(container_mem_result)
    #         if time.time() - start_loop_ts < args.interval:
    #             time.sleep(args.interval)
    #         if args.auto_reload:
    #             loaded_compose = self._load_compose_file_for_agent(filename=args.file, url=args.url)


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
            nargs='*',
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
            nargs='*',
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
