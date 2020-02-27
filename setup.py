#!/usr/bin/env python

import os
import sys

VERSION = '0.0.1'

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

license = """
Apache 2.0 License

Copyright (c) 2020 Ryan Snodgrass

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

setup(name='pyradiora_classic',
      version=VERSION,
      description='Python API for RS232 control of Lutron RadioRA Classic lighting',
      url='https://github.com/rsnodgrass/pyradiora-classic',
      author='Ryan Snodgrass',
      author_email='rsnodgrass@gmail.com',
      license='Apache2.0',
      install_requires=['pyserial>=3.4','pyserial-asyncio>=0.4'],
      packages=['pyradiora_classic'],
      classifiers=['Development Status :: 4 - Beta'],
      zip_safe=True)
