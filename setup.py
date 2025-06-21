#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='DISCOSClient',
    version='0.1',
    description='Python client for DISCOS',
    packages=find_packages(),
    #scripts=['scripts/subscriber.py'],
    license='GPL',
    platforms='all',
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.9.4',
    ],
)
