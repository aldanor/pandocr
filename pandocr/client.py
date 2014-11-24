# -*- coding: utf-8 -*-

import os
import re
import sys
import uuid
import json
import keyword
import tarfile
import py.path
import argparse
import requests
import logging

NONE = type('NONE', (), {})()


class PandocOption(object):
    def __init__(self, short_opts, long_opts, metavar=None, choices=None, optional=False):
        self.short_opts = short_opts
        self.long_opts = long_opts
        self.metavar = metavar.upper() if metavar is not None else metavar
        self.choices = choices
        self.optional = optional

    @property
    def is_input(self):
        return ('--template' in self.long_opts or
                '--include-in-header' in self.long_opts or
                '--include-before-body' in self.long_opts or
                '--include-after-body' in self.long_opts or
                '--reference-odt' in self.long_opts or
                '--reference-docx' in self.long_opts or
                '--epub-stylesheet' in self.long_opts or
                '--epub-cover-image' in self.long_opts or
                '--epub-metadata' in self.long_opts or
                '--epub-embed-font' in self.long_opts or
                '--bibliography' in self.long_opts or
                '--csl' in self.long_opts or
                '--citation-abbreviations' in self.long_opts)

    @property
    def is_output(self):
        return ('--output' in self.long_opts or
                '--print-default-data-file' in self.long_opts)

    @property
    def is_path(self):
        return ('--data-dir' in self.long_opts or
                '--extract-media' in self.long_opts)

    @property
    def name(self):
        for opt in self.long_opts:
            name = opt[2:].replace('-', '_')
            if not keyword.iskeyword(name):
                return name

    @staticmethod
    def parse_spec(string, regex, regex_optional):
        options, choices, metavar, optional = [], None, None, False
        for spec in string.split(','):
            spec = spec.strip()
            if not spec:
                continue
            match = re.match(regex, spec.strip())
            if match is None:
                optional = True
                match = re.match(regex_optional, spec.strip())
            match = match.groupdict()
            options.append(match['option'])
            if match['metavar'] is not None and '|' in match['metavar']:
                choices = match['metavar'].split('|')
            else:
                metavar = match['metavar']
        return options, choices, metavar, optional

    @classmethod
    def from_line(cls, line):
        line = line.strip()
        split = line.find('--')
        short_opts, choices, metavar, optional = cls.parse_spec(
            line[:split], r'^(?P<option>\-\w)( (?P<metavar>\S+))?$',
            r'^(?P<option>\-\w)\[(?P<metavar>\S+)\]$')
        long_opts, choices, metavar, optional = cls.parse_spec(
            line[split:], r'^(?P<option>\-\-[\w\-]+)(\=(?P<metavar>\S+))?$',
            r'^(?P<option>\-\-[\w\-]+)\[\=(?P<metavar>\S+)\]$')
        return cls(short_opts, long_opts, metavar=metavar, choices=choices, optional=optional)

    @property
    def is_help(self):
        return '-h' in self.short_opts or '--help' in self.long_opts

    def update_parser(self, parser):
        opts = self.short_opts + self.long_opts
        kwargs = {}
        if self.metavar:
            kwargs['metavar'] = self.metavar
        if self.choices:
            kwargs['choices'] = self.choices
        if not self.metavar and not self.choices:
            kwargs['action'] = 'store_true'
        if self.optional:
            kwargs['nargs'] = '?'
        kwargs['dest'] = self.name
        kwargs['default'] = NONE
        parser.add_argument(*opts, **kwargs)


class PandocOptions(object):
    def __init__(self, options):
        self.options = {option.name: option for option in map(PandocOption.from_line, options)
                        if not option.is_help}

    @property
    def parser(self):
        parser = argparse.ArgumentParser(description='pandoc')
        for option in self.options.values():
            option.update_parser(parser)
        parser.add_argument('--debug', action='store_true', default=False, dest='debug')
        parser.add_argument('input', metavar='INPUT', nargs='+')
        return parser

    def __getitem__(self, name):
        return self.options[name]

    def parse_args(self):
        return {k: v for k, v in vars(self.parser.parse_args()).items() if v is not NONE}


class PandocClient(object):
    def __init__(self, host=None, port=None):
        if host is None:
            host = os.getenv('PANDOC_HOST')
        if port is None:
            port = os.getenv('PANDOC_PORT')
        if not host:
            raise RuntimeError('pandoc host not specified (set PANDOC_HOST)')
        if not port:
            raise RuntimeError('pandoc port not specified (set PANDOC_PORT)')
        self.host = host + ':' + port
        self.debug = False
        self.log = logging.getLogger('pandocr')

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        self._debug = bool(value)
        if self.debug:
            format_string = '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
            logging.basicConfig(level=logging.DEBUG, format=format_string)
            self.log.setLevel(logging.DEBUG)

    def api(self, route, *args):
        host = self.host
        if not host.startswith('http://'):
            host = 'http://' + host
        if host.endswith('/'):
            host = host[:-1]
        if route.startswith('/'):
            route = route[1:]
        return host + '/api/' + '/'.join([route] + list(args))

    def map_file(self, filename, output=False):
        f = py.path.local(filename)
        if not output and not f.isfile:
            raise OSError('file not found: {0}'.format(f))
        return str(uuid.uuid4()) + f.ext

    def run(self):
        response = requests.get(self.api('options'))
        options = PandocOptions(response.json()['options'])
        input_files, output_files = {}, {}
        parsed_args = options.parse_args()
        self.debug = parsed_args.pop('debug', False)
        args = []
        for name, arg in parsed_args.items():
            if name == 'input':
                for fn in arg:
                    filename = self.map_file(fn)
                    input_files[filename] = open(fn, 'rb')
                    args.append(filename)
            else:
                option = options[name]
                if option.is_input:
                    filename = self.map_file(arg)
                    input_files[filename] = open(arg, 'rb')
                    arg = filename
                elif option.is_output:
                    filename = self.map_file(arg, output=True)
                    output_files[filename] = py.path.local(arg, expanduser=True)
                    arg = filename
                args.append(option.long_opts[0])
                if arg not in (None, True):
                    args.append(arg)
        self.log.debug('args: {0!r}'.format(args))
        self.log.debug('output files: {0!r}'.format(output_files))
        form = {'args': json.dumps(args), 'output': json.dumps(list(output_files))}
        response = requests.post(self.api('convert'), files=input_files, data=form)
        results = response.json()
        self.log.debug('response: {0}, {1}'.format(response.status_code, results))
        if results['returncode'] != 0:
            sys.stdout.write(results['stdout'])
            sys.exit(results['returncode'])
        response = requests.get(self.api('get', results['tag']))
        self.log.debug('response: {0}, <binary>'.format(response.status_code))
        workdir = py.path.local.mkdtemp()
        self.log.debug('using temporary folder: {0}'.format(workdir))
        with workdir.as_cwd():
            tar = workdir.join('output.tar.bz2')
            with tar.open('wb') as f:
                f.write(response.content)
            with tarfile.open(tar.strpath, 'r:bz2') as t:
                self.log.debug('output.tar.bz2: {0!r}'.format([m.path for m in t.getmembers()]))
                t.extractall()
            for source, dest in output_files.items():
                source = workdir.join(source)
                if source.isfile:
                    self.log.debug('moving: {0} -> {1}'.format(source, dest))
                    dest.dirpath().ensure(dir=True)
                    source.move(dest)
        workdir.remove()
        if results['stdout']:
            sys.stdout.write(results['stdout'])


def main():
    client = PandocClient()
    client.run()

if __name__ == '__main__':
    main()
