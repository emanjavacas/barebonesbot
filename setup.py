#!/usr/bin/env python

from setuptools import setup

setup(
    name='WikiQuoteBot',
    version='0.1',
    description='A configurable Twitter-bot for WikiQuotes',
    author='Enrique Manjavacas',
    license='MIT',
    install_requires=['wikiquote>=0.1.4', 'birdy>=0.2', 'segtok>=1.5.1']
)
