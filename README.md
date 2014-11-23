pandocr
=======

Python server and client for Pandoc.

The client supports all pandoc commands and optional arguments and behaves almost like a native `pandoc` tool. 
All input files are pushed to the server, and the output files are downloaded and moved to the designated
locations. The client also preserves the standard output and the exit code returned by the remote `pandoc` command.

Installation
------------

```sh
python setup.py install
```

Usage
-----

Starting the server:
```sh
$ pandoc-server --host 0.0.0.0 --port 8000
```

Using the client:
```sh
$ PANDOC_HOST=127.0.0.1 PANDOC_HOST=8000 pandocr -f markdown -t html -o foo.html foo.md
```


