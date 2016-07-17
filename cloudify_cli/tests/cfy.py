########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import sys
import shlex
import shutil
import tempfile

# import mock
import click.testing as clicktest
from testfixtures import log_capture

from cloudify.utils import setup_logger

import cloudify_cli  # NOQA

from .. import cli
from .. import logger
from .. import commands


WORKDIR = os.path.join(tempfile.gettempdir(), '.cloudify-tests')
runner_lgr = setup_logger('cli_runner')


@log_capture()
def invoke(command, capture):
    # TODO: replace ~/.cloudify with WORKDIR. Right now
    # it will actually work on the user's `~/.cloudify` folder.
    logger.configure_loggers()
    logger.set_global_verbosity_level(verbose=True, debug=False)

    cli = clicktest.CliRunner()

    lexed_command = shlex.split(command)
    # Safety measure in case someone wrote `cfy` at the beginning
    # of the command
    if lexed_command[0] == 'cfy':
        del lexed_command[0]
    func = lexed_command[0]
    params = lexed_command[1:]

    outcome = cli.invoke(getattr(commands, func), params)
    outcome.command = command
    outcome.logs = \
        [capture.records[m].msg for m in range(len(capture.records))]

    return outcome


class ClickInvocationException(Exception):
    def __init__(self, message, logs=None, error_code=1):
        self.message = message
        self.logs = logs
        self.error_code = error_code

    def __str__(self):
        return '{0} (Error Code: {1})\n{2}'.format(
            self.message, self.error_code, self.logs)


def purge_dot_cloudify():
    shutil.rmtree(os.path.expanduser('~/.cloudify'))


def run_cli_expect_system_exit_0(command):
    run_cli_expect_system_exit_code(command, expected_code=0)


def run_cli_expect_system_exit_1(command):
    run_cli_expect_system_exit_code(command, expected_code=1)


def run_cli_expect_system_exit_code(command, expected_code):
    try:
        run_cli(command)
    except SystemExit as e:
        assert e.code == expected_code
    else:
        raise RuntimeError("Expected SystemExit with {0} return code"
                           .format(expected_code))


def run_cli(command):
    cli.set_global_verbosity_level(cli.NO_VERBOSE)
    runner_lgr.info(command)
    sys.argv = command.split()
    cli.main()

    # Return the content of the log file
    # this enables making assertions on the output
    if os.path.exists(DEFAULT_LOG_FILE):
        with open(DEFAULT_LOG_FILE, 'r') as f:
            return f.read()
    return ''
