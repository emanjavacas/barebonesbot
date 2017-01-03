#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='BarebonesBot',
    version='0.1',
    description='A configurable Twitter-bot',
    author='Enrique Manjavacas',
    license='MIT',
    install_requires=[
        'birdy>=0.2'
    ]
)
