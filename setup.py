# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='pandocr',
    version='0.1.1',
    packages=find_packages(),
    install_requires=[
        'flask',
        'requests',
        'py'
    ],
    entry_points={
        'console_scripts': [
            'pandocr-server=pandocr.server:main',
            'pandocr=pandocr.client:main'
        ]
    }
)
