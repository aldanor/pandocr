# -*- coding: utf-8 -*-

import json
import uuid
import flask
import argparse
import tarfile
import py.path
import subprocess


class PandocServer(object):
    def __init__(self):
        self.app = flask.Flask(__name__)
        self.setup_routes()
        self.output = {}
        self.results = {}

    def setup_routes(self):
        self.api_options = self.app.route('/api/options', methods=['GET'])(self.api_options)
        self.api_convert = self.app.route('/api/convert', methods=['POST'])(self.api_convert)
        self.api_get = self.app.route('/api/get/<tag>', methods=['GET'])(self.api_get)

    def run(self, **kwargs):
        self.app.run(**kwargs)

    def api_options(self):
        text = subprocess.check_output(['pandoc', '--help'])
        return flask.jsonify({'options': text[text.find('Options:'):].splitlines()[1:]})

    def api_convert(self):
        workdir = py.path.local.mkdtemp()
        with workdir.as_cwd():
            for filename, f in flask.request.files.items():
                f.save(workdir.join(filename).strpath)
            args = json.loads(flask.request.form['args'])
            output = json.loads(flask.request.form['output'])
            results = {}
            try:
                stdout = subprocess.check_output(['pandoc'] + args, stderr=subprocess.STDOUT,
                                                 universal_newlines=True)
            except subprocess.CalledProcessError as exc:
                results['stdout'] = exc.output
                results['returncode'] = exc.returncode
            else:
                results['stdout'] = stdout
                results['returncode'] = 0
                results['tag'] = str(uuid.uuid4())
                self.output[results['tag']] = workdir
                with tarfile.open('output.tar.bz2', 'w:bz2') as t:
                    for filename in output:
                        t.add(filename)
        return flask.jsonify(results)

    def api_get(self, tag):
        if tag not in self.output:
            return flask.abort(400)
        response = flask.send_file(self.output[tag].join('output.tar.bz2').strpath)
        self.output.pop(tag).remove()
        return response


def main():
    parser = argparse.ArgumentParser(description='pandocr-server')
    parser.add_argument('--host', type=str, default='0.0.0.0', metavar='HOST')
    parser.add_argument('--port', type=int, default=8000, metavar='PORT')
    parser.add_argument('--debug', action='store_true', default=False)
    args = vars(parser.parse_args())
    server = PandocServer()
    server.run(**args)


if __name__ == '__main__':
    main()
