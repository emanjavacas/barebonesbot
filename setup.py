#!/usr/bin/env python

from setuptools import setup

setup(
    name='EMMA-quotes',
    version='0.1',
    description='A Twitter-boot for the EMMA corpus',
    author='Enrique Manjavacas',
    install_requires=['wikiquote>=0.1.4', 'birdy>=0.2', 'segtok>=1.5.1']
)
