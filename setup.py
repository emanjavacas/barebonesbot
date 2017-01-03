#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='barebonesbot',
    version='0.3',
    package_dir={'barebonesbot': 'src'},
    packages=['barebonesbot'],
    description='A configurable Twitter-bot',
    author='Enrique Manjavacas',
    author_email='enrique.manjavacas@gmail.com',
    url='https://www.github.com/emanjavacas/barebonesbot/',
    download_url='https://api.github.com/repos/emanjavacas/barebonesbot/tarball',
    install_requires=[
        'birdy>=0.2'
    ],
    license='MIT'
)
