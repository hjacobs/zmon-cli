import yaml

import click

from clickclick import AliasedGroup, Action, ok

from zmon_cli.cmds.command import cli, get_client, yaml_output_option, pretty_json
from zmon_cli.output import dump_yaml, Output, render_dashboard


@cli.group('dashboard', cls=AliasedGroup)
@click.pass_obj
def dashboard(obj):
    """Manage ZMON dashboards"""
    pass


@dashboard.command('init')
@click.argument('yaml_file', type=click.File('wb'))
@click.pass_obj
def init(obj, yaml_file):
    """Initialize a new dashboard YAML file"""
    name = click.prompt('Dashboard name', default='Example dashboard')
    alert_teams = click.prompt('Alert Teams (comma separated)', default='Team1, Team2')

    user = obj.config.get('user', 'unknown')

    data = {
        'id': '',
        'name': name,
        'last_modified_by': user,
        'alert_teams': [t.strip() for t in alert_teams.split(',')],
        'tags': [],
        'view_mode': 'FULL',
        'shared_teams': [],
        'widget_configuration': [],
    }

    yaml_file.write(dump_yaml(data).encode('utf-8'))
    ok()


@dashboard.command('get')
@click.argument("dashboard_id", type=int)
@click.pass_obj
@yaml_output_option
@pretty_json
def dashboard_get(obj, dashboard_id, output, pretty):
    """Get ZMON dashboard"""
    client = get_client(obj.config)
    with Output('Retrieving dashboard ...', nl=True, output=output, pretty_json=pretty) as act:
        dashboard = client.get_dashboard(dashboard_id)
        act.echo(dashboard)


@dashboard.command('update')
@click.argument('yaml_file', type=click.Path(exists=True))
@click.pass_obj
def dashboard_update(obj, yaml_file):
    """Create/Update a single ZMON dashboard"""
    client = get_client(obj.config)
    dashboard = {}
    with open(yaml_file, 'rb') as f:
        dashboard = yaml.safe_load(f)

    msg = 'Creating new dashboard ...'
    if 'id' in dashboard:
        msg = 'Updating dashboard {} ...'.format(dashboard.get('id'))

    with Action(msg, nl=True):
        dash_id = client.update_dashboard(dashboard)
        ok(client.dashboard_url(dash_id))


@dashboard.command('show')
@click.argument("dashboard_id", type=int)
@click.pass_obj
@yaml_output_option
@pretty_json
def dashboard_show(obj, dashboard_id, output, pretty):
    """Show ZMON dashboard"""
    client = get_client(obj.config)
    dashboard = client.get_dashboard(dashboard_id)

    if dashboard.get('alert_teams') is None:
        raise SystemExit

    alerts = client.get_alert_definitions()

    alerts = [alert for alert in alerts if alert.get('responsible_team') in dashboard['alert_teams']]

    if len(dashboard['tags']) > 0:
        for tag in dashboard['tags']:
            alerts = [alert for alert in alerts if tag in alert.get('tags')]

    id = ""

    for alert in alerts:
        id += str(alert.get('id')) + ","

    result = client.get_alert_status(id)

    """ result is dict of dicts, converting to list of dicts """

    final = []
    for key in dict.keys(result):
        temp = {}
        temp['id'] = key
        temp['start_time'] = 9999999999.9
        for alert in alerts:
            if str(key) == str(alert.get('id')):
                temp['name'] = alert.get('name')
                temp['priority'] = alert.get('priority')
                temp['responsible_team'] = alert.get('responsible_team')
        temp['entities'] = []
        for entity in dict.keys(result[key]):
            temp['entities'].append({entity: result[key][entity]})
            if result[key][entity]['start_time'] < temp['start_time']:
                temp['start_time'] = result[key][entity]['start_time']
        final.append(temp)

    if len(final) == 0:
        print("No Alerts")
        raise SystemExit

    with Output('Retrieving dashboard ...', nl=True, output=output, pretty_json=pretty,
                printer=render_dashboard) as act:

        act.echo(final)


@dashboard.command('help')
@click.pass_context
def help(ctx):
    print(ctx.parent.get_help())
