import click
import logging
import os

from clickclick import AliasedGroup, Action, info
from easydict import EasyDict

from zmon_cli import __version__

from zmon_cli.output import print_table

from zmon_cli.config import DEFAULT_CONFIG_FILE
from zmon_cli.config import get_config_data, configure_logging, set_config_file

from zmon_cli.client import Zmon


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

output_option = click.option('-o', '--output', type=click.Choice(['text', 'json', 'tsv']), default='text',
                             help='Use alternative output format')


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('ZMON CLI {}'.format(__version__))
    ctx.exit()


def get_client(config):
    verify = config.get('verify', True)

    if 'user' in config and 'password' in config:
        return Zmon(config['url'], username=config['user'], password=config['password'], verify=verify)
    elif 'token' in config:
        return Zmon(config['url'], token=config['token'], verify=verify)

    raise RuntimeError('Failed to intitialize ZMON client. Invalid configuration!')


########################################################################################################################
# CLI
########################################################################################################################

@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
@click.option('-c', '--config-file', help='Use alternative config file', default=DEFAULT_CONFIG_FILE, metavar='PATH')
@click.option('-v', '--verbose', help='Verbose logging', is_flag=True)
@click.option('-V', '--version', is_flag=True, callback=print_version, expose_value=False, is_eager=True)
@click.pass_context
def cli(ctx, config_file, verbose):
    """
    ZMON command line interface
    """
    configure_logging(logging.DEBUG if verbose else logging.INFO)

    fn = os.path.expanduser(config_file)
    config = {}

    if os.path.exists(fn):
        config = get_config_data(config_file)

    ctx.obj = EasyDict(config=config, client=get_client(config))


@cli.command()
@click.option('-c', '--config-file', help='Use alternative config file', default=DEFAULT_CONFIG_FILE, metavar='PATH')
@click.pass_context
def configure(ctx, config_file):
    '''Configure ZMON URL and credentials'''
    set_config_file(config_file, ctx.obj.get('url'))


@cli.command()
@click.pass_context
def status(ctx):
    """Check ZMON system status"""
    status = {}
    with Action('Retrieving status ...'):
        status = ctx.obj.client.status()

    click.secho('Alerts active: {}'.format(status.get('alerts_active')))

    info('Workers:')
    rows = []
    for worker in status.get('workers', []):
        rows.append(worker)

    rows.sort(key=lambda x: x.get('name'))

    print_table(['name', 'check_invocations', 'last_execution_time'], rows)

    info('Queues:')
    rows = []
    for queue in status.get('queues', []):
        rows.append(queue)

    rows.sort(key=lambda x: x.get('name'))

    print_table(['name', 'size'], rows)
