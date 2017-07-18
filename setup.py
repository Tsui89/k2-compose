#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from distutils.core import setup
from setuptools import setup,find_packages
# import setuptools
# import version
setup(name="k2-compose",
      version='0.0.6',
      packages=find_packages(exclude=['tests.*']),
      # package_dir = {
      #   '':'k2_compose'
      # },
      # packages=[
      #     '',
      #     'health_agent',
      #     'k2cutils',
      #     'compose_utils',
      #     'common',
      #     'compose',
      #     'container',
      #     'image',
      #     'service',
      # ],
      # package_dir={
      #     '': 'python-modules',
      #     'health_agent': 'python-modules/health_agent',
      #     'k2cutils': 'python-modules/k2cutils',
      #     'compose_utils': 'python-modules/compose_utils',
      #     'common': 'python-modules/common',
      #     'compose': 'python-modules/compose',
      #     'container': 'python-modules/container',
      #     'image': 'python-modules/image',
      #     'service': 'python-modules/service'
      # },
      # include_package_data=True,
      # data_files=[('checkers',['*.sh'])],
      description='K2Platform deployment tool',
      author='hippopo',
      author_email='wch.c@qq.com',
      url='https://github.com/Tsui89/k2-compose',
      install_requires=[
          'colorama>=0.3.7',
          'requests==2.7.0',
          'docker-compose',
          'six>=1.9.0',
          'influxdb==3.0.0',
          'colorclass==2.2.0',
          'terminaltables==3.0.0',
          'pick',
      ],
      entry_points={                                                             
          'console_scripts': [
            'k2-compose=k2_compose.run:run',
          ]
      }
      )
