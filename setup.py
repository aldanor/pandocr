# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='pandocr',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'pandocr-server=pandocr.server:main',
            'pandocr=pandocr.client:main'
        ]
    }
)
