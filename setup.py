#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='DISCOS Client',
    version='0.1',
    description='Python client for DISCOS',
    packages=find_packages(),
    license='GPL',
    platforms='all',
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.9.4',
    ],
    include_package_data=True,
    package_data={
        "discos_client": ["schemas/*.json"],
    },
)
