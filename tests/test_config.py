# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import os
import io
import shutil
import sys
import tempfile

import pytest

from contextlib import contextmanager
from copy import deepcopy
from mock import patch
from textwrap import dedent


from bumpr.config import DEFAULTS, Config, ValidationError, __name__ as config_module_name
from bumpr.version import Version
from bumpr.hooks import HOOKS, ReadTheDocHook

if sys.version_info[0] == 3:
    unicode = str


@contextmanager
def mock_ini(data):
    open_name = '{0}.open'.format(config_module_name)
    with patch(open_name, return_value=io.StringIO(unicode(dedent(data))), create=True) as mock:
        yield mock


class ConfigTest(object):

    @pytest.fixture(autouse=True)
    def cleandir(self):
        self.currentdir = os.getcwd()
        self.workdir = tempfile.mkdtemp()
        os.chdir(self.workdir)
        yield
        os.chdir(self.currentdir)
        shutil.rmtree(self.workdir)

    def test_defaults(self):
        '''It should initialize with default values'''
        config = Config()
        expected = deepcopy(DEFAULTS)
        for hook in HOOKS:
            expected[hook.key] = False
        assert config == expected

    def test_from_dict(self):
        '''It can take a dictionnay as parameter but keeps defaults'''
        config_dict = {
            'module': 'test_module',
            'attribute': 'VERSION',
            'commit': True,
            'tag': True,
            'dryrun': True,
            'files': ['anyfile.py'],
            'bump': {
                'suffix': 'final',
                'message': 'Version {version}',
            },
            'prepare': {
                'part': 'minor',
                'suffix': 'dev',
                'message': 'Update to version {version}',
            },
        }
        config = Config(config_dict)
        expected = deepcopy(DEFAULTS)
        for key, value in config_dict.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    expected[key][nested_key] = nested_value
            else:
                expected[key] = value
        for hook in HOOKS:
            expected[hook.key] = False
        assert config == expected

    def test_from_dict_with_hook(self):
        '''It should take defaults from hooks if present and set it to false if not'''
        tested_hook = ReadTheDocHook
        config_dict = {
            tested_hook.key: {
                'bump': 'test'
            }
        }

        expected = deepcopy(DEFAULTS)
        for hook in HOOKS:
            if hook is tested_hook:
                expected[hook.key] = hook.defaults
                expected[hook.key]['bump'] = 'test'
            else:
                expected[hook.key] = False

        config = Config(config_dict)
        assert config == expected

    def test_override_from_config(self):
        bumprrc = '''\
        [bumpr]
        file = test.py
        files = README
        push = true
        [bump]
        message = test
        '''

        expected = deepcopy(DEFAULTS)
        expected['file'] = 'test.py'
        expected['files'] = ['README']
        expected['push'] = True
        expected['bump']['message'] = 'test'
        for hook in HOOKS:
            expected[hook.key] = False

        config = Config()
        with mock_ini(bumprrc) as mock:
            config.override_from_config('test.rc')

        mock.assert_called_once_with('test.rc')
        assert config == expected

    def test_override_from_setup_cfg(self):
        with io.open('setup.cfg', 'w') as cfg:
            cfg.write('\n'.join([
                '[bumpr]',
                'file = test.py',
                'files = README',
                'push = true',
                '[bumpr:bump]',
                'message = test',
            ]))

        expected = deepcopy(DEFAULTS)
        expected['file'] = 'test.py'
        expected['files'] = ['README']
        expected['push'] = True
        expected['bump']['message'] = 'test'
        for hook in HOOKS:
            expected[hook.key] = False

        config = Config()
        assert config == expected

    def test_override_from_setup_cfg_with_hooks(self):
        tested_hook = ReadTheDocHook
        with io.open('setup.cfg', 'w') as cfg:
            cfg.write('\n'.join([
                '[bumpr:{0}]'.format(tested_hook.key),
                'bump = test',
            ]))

        expected = deepcopy(DEFAULTS)
        for hook in HOOKS:
            if hook is tested_hook:
                expected[hook.key] = hook.defaults
                expected[hook.key]['bump'] = 'test'
            else:
                expected[hook.key] = False

        config = Config()
        assert config == expected

    def test_override_hook_from_config(self):
        tested_hook = ReadTheDocHook
        bumprrc = '''\
        [{0}]
        bump = test
        '''.format(tested_hook.key)

        expected = deepcopy(DEFAULTS)
        for hook in HOOKS:
            if hook is tested_hook:
                expected[hook.key] = hook.defaults
                expected[hook.key]['bump'] = 'test'
            else:
                expected[hook.key] = False

        config = Config()
        with mock_ini(bumprrc) as mock:
            config.override_from_config('test.rc')

        mock.assert_called_once_with('test.rc')
        assert config == expected

    def test_override_from_args(self):
        config = Config.parse_args(['test.py', '-M', '-v', '-s', 'test-suffix', '-c', 'fake'])

        expected = deepcopy(DEFAULTS)
        expected['file'] = 'test.py'
        expected['bump']['part'] = Version.MAJOR
        expected['bump']['suffix'] = 'test-suffix'
        expected['verbose'] = True
        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_override_args_keeps_config_values(self):
        bumprrc = '''\
        [bumpr]
        files = README
        [bump]
        message = test
        [prepare]
        part = minor
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['test.py', '-M', '-v', '-s', 'test-suffix', '-c', 'test.rc'])

        expected = deepcopy(DEFAULTS)
        expected['file'] = 'test.py'
        expected['bump']['part'] = Version.MAJOR
        expected['bump']['suffix'] = 'test-suffix'
        expected['verbose'] = True

        expected['files'] = ['README']
        expected['bump']['message'] = 'test'
        expected['prepare']['part'] = Version.MINOR

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_do_not_override_push_when_not_in_args(self):
        bumprrc = '''\
        [bumpr]
        push = true
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc'])

        expected = deepcopy(DEFAULTS)
        expected['push'] = True

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_override_push_from_args(self):
        bumprrc = '''\
        [bumpr]
        push = true
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc', '--no-push'])

        expected = deepcopy(DEFAULTS)
        expected['push'] = False

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_force_push_from_args(self):
        bumprrc = '''\
        [bumpr]
        push = false
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc', '--push'])

        expected = deepcopy(DEFAULTS)
        expected['push'] = True

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_do_not_override_commit_when_not_in_args(self):
        bumprrc = '''\
        [bumpr]
        commit = False
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc'])

        expected = deepcopy(DEFAULTS)
        expected['commit'] = False

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_do_not_override_bump_only_when_not_in_args(self):
        bumprrc = '''\
        [bumpr]
        bump_only = True
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc'])

        expected = deepcopy(DEFAULTS)
        expected['bump_only'] = True

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_do_not_override_prepare_only_when_not_in_args(self):
        bumprrc = '''\
        [bumpr]
        prepare_only = True
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc'])

        expected = deepcopy(DEFAULTS)
        expected['prepare_only'] = True

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_do_override_commit(self):
        bumprrc = '''\
        [bumpr]
        commit = True
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc', '-nc'])

        expected = deepcopy(DEFAULTS)
        expected['commit'] = False

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_skip_tests_from_args(self):
        bumprrc = '''\
        [bumpr]
        '''

        with mock_ini(bumprrc):
            with patch('bumpr.config.exists', return_value=True):
                config = Config.parse_args(['-c', 'test.rc', '--skip-tests'])

        expected = deepcopy(DEFAULTS)
        expected['skip_tests'] = True

        for hook in HOOKS:
            expected[hook.key] = False

        assert config == expected

    def test_validate(self):
        config = Config({'file': 'version.py'})
        config.validate()

    def test_validate_file_missing(self):
        config = Config()
        with pytest.raises(ValidationError):
            config.validate()
