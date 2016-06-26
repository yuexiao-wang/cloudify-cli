########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import sys
import argparse
import StringIO
import traceback
from itertools import imap

import click

# from cloudify import logs
from cloudify_rest_client.exceptions import NotModifiedError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.exceptions import MaintenanceModeActiveError
from cloudify_rest_client.exceptions import MaintenanceModeActivatingError

# TODO: after fixing impossible imports, just import the commands package
from cloudify_cli import utils
from cloudify_cli import logger
from cloudify_cli.logger import configure_loggers
from cloudify_cli.exceptions import CloudifyBootstrapError
from cloudify_cli.exceptions import SuppressedCloudifyCliError

from cloudify_cli.commands import use
from cloudify_cli.commands import dev
from cloudify_cli.commands import ssh
from cloudify_cli.commands import init
from cloudify_cli.commands import logs
from cloudify_cli.commands import nodes
from cloudify_cli.commands import agents
from cloudify_cli.commands import events
from cloudify_cli.commands import groups
from cloudify_cli.commands import status
from cloudify_cli.commands import install
from cloudify_cli.commands import recover
from cloudify_cli.commands import version
from cloudify_cli.commands import plugins
from cloudify_cli.commands import upgrade
from cloudify_cli.commands import validate
from cloudify_cli.commands import teardown
from cloudify_cli.commands import rollback
from cloudify_cli.commands import uninstall
from cloudify_cli.commands import workflows
from cloudify_cli.commands import snapshots
from cloudify_cli.commands import bootstrap
from cloudify_cli.commands import blueprints
from cloudify_cli.commands import executions
from cloudify_cli.commands import deployments
from cloudify_cli.commands import maintenance
from cloudify_cli.commands import node_instances


def _set_cli_except_hook():

    def recommend(possible_solutions):

        from cloudify_cli.logger import get_logger
        logger = get_logger()

        logger.info('Possible solutions:')
        for solution in possible_solutions:
            logger.info('  - {0}'.format(solution))

    def new_excepthook(tpe, value, tb):

        from cloudify_cli.logger import get_logger
        logger = get_logger()

        prefix = None
        server_traceback = None
        output_message = True
        if issubclass(tpe, CloudifyClientError):
            server_traceback = value.server_traceback
            if not issubclass(
                    tpe,
                    (MaintenanceModeActiveError,
                     MaintenanceModeActivatingError,
                     NotModifiedError)):
                # this means we made a server call and it failed.
                # we should include this information in the error
                prefix = 'An error occurred on the server'
        if issubclass(tpe, SuppressedCloudifyCliError):
            output_message = False
        if issubclass(tpe, CloudifyBootstrapError):
            output_message = False
        if verbosity_level:
            # print traceback if verbose
            s_traceback = StringIO.StringIO()
            traceback.print_exception(
                etype=tpe,
                value=value,
                tb=tb,
                file=s_traceback)
            logger.error(s_traceback.getvalue())
            if server_traceback:
                logger.error('Server Traceback (most recent call last):')

                # No need for print_tb since this exception
                # is already formatted by the server
                logger.error(server_traceback)
        if output_message and not verbosity_level:

            # if we output the traceback
            # we output the message too.
            # print_exception does that.
            # here we just want the message (non verbose)
            if prefix:
                logger.error('{0}: {1}'.format(prefix, value))
            else:
                logger.error(value)
        if hasattr(value, 'possible_solutions'):
            recommend(getattr(value, 'possible_solutions'))

    sys.excepthook = new_excepthook


def longest_command_length(commands_dict):
    return max(imap(len, commands_dict))


class ConciseArgumentDefaultsHelpFormatter(
        argparse.ArgumentDefaultsHelpFormatter):

    def _get_help_string(self, action):

        default = action.default
        help = action.help

        if default != argparse.SUPPRESS and default not in [None, False]:
            if '%(default)' not in help:
                help += ' (default: %(default)s)'

        return help


def register_commands():
    """Register the CLI's commands.

    Here is where we decide which commands register with the cli
    and which don't. We should decide that according to whether
    a manager is currently `use`d or not.
    """
    is_manager_active = utils.is_manager_active()

    main.add_command(use.use)
    main.add_command(recover.recover)
    main.add_command(init.init_command)
    main.add_command(validate.validate)
    main.add_command(bootstrap.bootstrap)

    # TODO: Instead of manually stating each module,
    # we should try to import all modules in the `commands`
    # package recursively and check if they have a certain attribute
    # which indicates they belong to `manager`.
    if is_manager_active:
        main.add_command(dev.dev)
        main.add_command(ssh.ssh)
        main.add_command(logs.logs)
        main.add_command(nodes.nodes)
        main.add_command(agents.agents)
        main.add_command(events.events)
        main.add_command(groups.groups)
        main.add_command(status.status)
        main.add_command(plugins.plugins)
        main.add_command(upgrade.upgrade)
        main.add_command(teardown.teardown)
        main.add_command(rollback.rollback)
        main.add_command(workflows.workflows)
        main.add_command(snapshots.snapshots)
        main.add_command(blueprints.blueprints)
        main.add_command(executions.executions)
        main.add_command(install.remote_install)
        main.add_command(deployments.deployments)
        main.add_command(uninstall.remote_uninstall)
        main.add_command(maintenance.maintenance_mode)
        main.add_command(node_instances.node_instances)
    else:
        main.add_command(install.local_install)
        main.add_command(uninstall.local_uninstall)
        main.add_command(node_instances.node_instances_command)


@click.group(context_settings=utils.CLICK_CONTEXT_SETTINGS)
@click.option('-v',
              '--verbose',
              count=True,
              is_eager=True)
@click.option('--debug',
              default=False,
              is_flag=True)
@click.option('--version',
              is_flag=True,
              callback=version.version,
              expose_value=False,
              is_eager=True)
def main(verbose, debug):
    # TODO: when calling a command which only exists in the context
    # of a manager but no manager is currently `use`d, print out a message
    # stating that "Some commands only exist when using a manager. You can run
    # `cfy use MANAGER_IP` and try this command again."
    # TODO: fix verbosity placement
    configure_loggers()

    if debug:
        global_verbosity_level = logger.HIGH_VERBOSE
    else:
        global_verbosity_level = verbose
    logger.set_global_verbosity_level(global_verbosity_level)
    if global_verbosity_level >= logger.HIGH_VERBOSE:
        logger.set_debug()
    # _set_cli_except_hook()


register_commands()


# def _parse_args(args):
#     """
#     Parses the arguments using the Python argparse library.
#     Generates shell autocomplete using the argcomplete library.

#     :param list args: arguments from cli
#     :rtype: `python argument parser`
#     """

#     parser = register_commands()
#     argcomplete.autocomplete(parser)

#     if len(sys.argv) == 1:
#         parser.print_help()
#         sys.exit(1)

#     parsed = parser.parse_args(args)
#     if parsed.debug:
#         global_verbosity_level = HIGH_VERBOSE
#     else:
#         global_verbosity_level = parsed.verbosity
#     set_global_verbosity_level(global_verbosity_level)
#     if global_verbosity_level >= HIGH_VERBOSE:
#         set_debug()
#     return parsed


# def register_commands():
#     from cloudify_cli.config.parser_config import parser_config
#     parser_conf = parser_config()
#     parser = argparse.ArgumentParser(description=parser_conf['description'])

#     # Direct arguments for the 'cfy' command (like -v)
#     for argument_name, argument in parser_conf['arguments'].iteritems():
#         parser.add_argument(argument_name, **argument)

#     subparsers = parser.add_subparsers(
#         title='Commands',
#         metavar=''
#     )

#     for command_name, command in parser_conf['commands'].iteritems():

#         if 'sub_commands' in command:

#             # Add sub commands. Such as 'cfy blueprints list',
#             # 'cfy deployments create' ...
#             controller_help = command['help']
#             controller_parser = subparsers.add_parser(
#                 command_name, help=controller_help
#             )
#             controller_subparsers = controller_parser.add_subparsers(
#                 title='Commands',
#                 metavar=(' ' *
#                          (constants.HELP_TEXT_COLUMN_BUFFER +
#                           longest_command_length(command['sub_commands'])))
#             )
#             for controller_sub_command_name, controller_sub_command in \
#                     command['sub_commands'].iteritems():
#                 register_command(controller_subparsers,
#                                  controller_sub_command_name,
#                                  controller_sub_command)
#         else:

#             # Add direct commands. Such as 'cfy status', 'cfy ssh' ...
#             register_command(subparsers, command_name, command)

#     return parser


# def _register_argument(args, command_parser):
#     command_arg_names = []

#     for argument_name, argument in args.iteritems():
#         completer = argument.get('completer')
#         if completer:
#             del argument['completer']

#         arg = command_parser.add_argument(
#             *argument_name.split(','),
#             **argument
#         )

#         if completer:
#             arg.completer = completer

#         command_arg_names.append(argument['dest'])

#     return command_arg_names


# def register_command(subparsers, command_name, command):

#     command_help = command['help']
#     command_parser = subparsers.add_parser(
#         command_name, help=command_help,
#         formatter_class=ConciseArgumentDefaultsHelpFormatter
#     )

#     command_arg_names = []
#     arguments = command.get('arguments', {})

#     mutually_exclusive = arguments.pop('_mutually_exclusive', [])

#     command_arg_names += _register_argument(arguments,
#                                             command_parser)

#     for mutual_exclusive_group in mutually_exclusive:
#         command_arg_names += _register_argument(
#             mutual_exclusive_group,
#             command_parser.add_mutually_exclusive_group(required=True)
#         )
#     # Add verbosity flag for each command
#     command_parser.add_argument(
#         '-v', '--verbose',
#         dest='verbosity',
#         action='count',
#         default=NO_VERBOSE,
#         help='Set verbosity level (can be passed multiple times)'
#     )

#     # Add debug flag for each command
#     command_parser.add_argument(
#         '--debug',
#         dest='debug',
#         action='store_true',
#         help='Set debug output (equivalent to -vvv)'
#     )

#     def command_cmd_handler(args):
#         kwargs = {}
#         for arg_name in command_arg_names:
#             # Filter verbosity since it accessed globally
#             # and not via the method signature.
#             if hasattr(args, arg_name):
#                 arg_value = getattr(args, arg_name)
#                 kwargs[arg_name] = arg_value

#         command['handler'](**kwargs)

#     command_parser.set_defaults(handler=command_cmd_handler)


if __name__ == '__main__':
    main()
