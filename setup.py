#!/usr/bin/env python
# -*- coding: utf-8 -*-

# from distutils.core import setup
import os
from setuptools import setup,find_packages
# import setuptools
# import version

ROOT_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(ROOT_DIR)

setup(name="k2-compose",
      version='0.0.9rc7',
      packages=find_packages(exclude=['tests.*']),
      description='K2Platform deployment tool',
      author='hippopo',
      author_email='wch.c@qq.com',
      url='https://github.com/Tsui89/k2-compose',
      install_requires=[
          'docker-compose==1.14.0',
          'six>=1.9.0',
          'colorclass==2.2.0',
          'terminaltables==3.0.0',
          'pick',
          'pytz'
      ],
      entry_points={                                                             
          'console_scripts': [
            'k2-compose=k2_compose.run:run',
          ]
      }
      )
