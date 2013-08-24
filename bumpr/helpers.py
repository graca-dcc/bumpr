# -*- coding: utf-8 -*-
import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


class BumprError(Exception):
    pass


def check_output(*args, **kwargs):
    '''Compatibility wrapper for Python 2.6 missin g subprocess.check_output'''
    if hasattr(subprocess, 'check_output'):
        return subprocess.check_output(*args, **kwargs)
    else:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, **kwargs)
        output, _ = process.communicate()
        retcode = process.poll()
        if retcode:
            error = subprocess.CalledProcessError(retcode, args[0])
            error.output = output
            raise error
        return output


def execute(command, verbose=False, replacements=None, dryrun=False):
    replacements = replacements or {}
    if not command:
        return
    elif isinstance(command, (list, tuple)):
        if not isinstance(command[0], (list, tuple)):
            command = [command]
        commands = []
        for cmd in command:
            commands.append([part.format(**replacements) for part in cmd])
    else:
        commands = [shlex.split(cmd.format(**replacements)) for cmd in command.split('\n') if cmd.strip()]

    output = ''
    for cmd in commands:
        if dryrun:
            logger.dryrun('execute: {0}'.format(' '.join(cmd)))
        elif verbose:
            subprocess.check_call(cmd)
        else:
            try:
                output += check_output(cmd)
            except subprocess.CalledProcessError as exception:
                logger.error('Command "%s" failed with exit code %s', cmd, exception.returncode)
                print(exception.output)
    return output


class ObjectDict(dict):
    '''A dictionnary with object-like attribute access and depp merge'''
    def __init__(self, *args, **kwargs):  # pylint: disable=W0231
        self.update(*args, **kwargs)

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, ObjectDict):
            value = ObjectDict(value)
        self[key] = value

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, ObjectDict):
            value = ObjectDict(value)
        super(ObjectDict, self).__setitem__(key, value)

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            if isinstance(value, dict) and not isinstance(value, ObjectDict):
                value = ObjectDict(value)
            self[key] = value

    def merge(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            if isinstance(value, dict):
                if not isinstance(value, ObjectDict):
                    value = ObjectDict(value)
                if key in self and isinstance(self[key], ObjectDict):
                    self[key].merge(value)
                    continue
            self[key] = value
