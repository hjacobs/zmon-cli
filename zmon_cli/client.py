import ast
import logging
import json
import functools
import re

from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit, SplitResult

import requests

from zmon_cli import __version__


API_VERSION = 'v1'

ZMON_USER_AGENT = 'zmon-client/{}'.format(__version__)

ACTIVE_ALERT_DEF = 'checks/all-active-alert-definitions'
ACTIVE_CHECK_DEF = 'checks/all-active-check-definitions'
ALERT_DATA = 'status/alert'
ALERT_DEF = 'alert-definitions'
CHECK_DEF = 'check-definitions'
DASHBOARD = 'dashboard'
DOWNTIME = 'downtimes'
ENTITIES = 'entities'
GRAFANA = 'grafana2-dashboards'
GROUPS = 'groups'
MEMBER = 'member'
PHONE = 'phone'
SEARCH = 'quick-search'
STATUS = 'status'
TOKENS = 'onetime-tokens'

ALERT_DETAILS_VIEW_URL = '#/alert-details/'
CHECK_DEF_VIEW_URL = '#/check-definitions/view/'
DASHBOARD_VIEW_URL = '#/dashboards/views/'
GRAFANA_DASHBOARD_URL = 'grafana/dashboard/db/'
TOKEN_LOGIN_URL = 'tv/'

logger = logging.getLogger(__name__)

parentheses_re = re.compile('[(]+|[)]+')
invalid_entity_id_re = re.compile('[^a-zA-Z0-9-@_.\[\]\:]+')


class JSONDateEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.isoformat() if isinstance(obj, datetime) else super().default(obj)


class ZmonError(Exception):
    """ZMON client error."""

    def __init__(self, message=''):
        super().__init__('ZMON client error: {}'.format(message))


class ZmonArgumentError(ZmonError):
    """A ZMON client error indicating that a supplied object has missing or invalid attributes."""
    pass


def logged(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except:
            logger.error('ZMON client failed in: {}'.format(f.__name__))
            raise

    return wrapper


def compare_entities(e1, e2):
    try:
        e1_copy = e1.copy()
        e1_copy.pop('last_modified', None)

        e2_copy = e2.copy()
        e2_copy.pop('last_modified', None)

        return (json.loads(json.dumps(e1_copy, cls=JSONDateEncoder)) ==
                json.loads(json.dumps(e2_copy, cls=JSONDateEncoder)))
    except:
        # We failed during json serialiazation/deserialization, fallback to *not-equal*!
        logger.exception('Failed in `compare_entities`')
        return False


def get_valid_entity_id(e):
    return invalid_entity_id_re.sub('-', parentheses_re.sub(lambda m: '[' if '(' in m.group() else ']', e.lower()))


class Zmon:
    """ZMON client class that enables communication with ZMON backend.

    :param url: ZMON backend base url.
    :type url: str

    :param token: ZMON authentication token.
    :type token: str

    :param username: ZMON authentication username. Ignored if ``token`` is used.
    :type username: str

    :param password: ZMON authentication password. Ignored if ``token`` is used.
    :type password: str

    :param timeout: HTTP requests timeout. Default is 10 sec.
    :type timeout: int

    :param verify: Verify SSL connection. Default is ``True``.
    :type verify: bool

    :param user_agent: ZMON user agent. Default is generated by ZMON client and includes lib version.
    :type user_agent: str
    """

    def __init__(
            self, url, token=None, username=None, password=None, timeout=10, verify=True, user_agent=ZMON_USER_AGENT):
        """Initialize ZMON client."""
        self.timeout = timeout

        split = urlsplit(url)
        self.base_url = urlunsplit(SplitResult(split.scheme, split.netloc, '', '', ''))
        self.url = urljoin(self.base_url, self._join_path(['api', API_VERSION, '']))

        self._session = requests.Session()

        self._session.timeout = timeout
        self.user_agent = user_agent

        if username and password and token is None:
            self._session.auth = (username, password)

        self._session.headers.update({'User-Agent': user_agent, 'Content-Type': 'application/json'})

        if token:
            self._session.headers.update({'Authorization': 'Bearer {}'.format(token)})

        if not verify:
            logger.warning('ZMON client will skip SSL verification!')
            requests.packages.urllib3.disable_warnings()
            self._session.verify = False

    @property
    def session(self):
        return self._session

    @staticmethod
    def is_valid_entity_id(entity_id):
        return invalid_entity_id_re.search(entity_id) is None

    @staticmethod
    def validate_check_command(src):
        """
        Validates if ``check command`` is valid syntax. Raises exception in case of invalid syntax.

        :param src: Check command python source code.
        :type src: str

        :raises: ZmonError
        """
        try:
            ast.parse(src)
        except Exception as e:
            raise ZmonError('Invalid check command: {}'.format(e))

    def _join_path(self, parts):
        return '/'.join(str(p).strip('/') for p in parts)

    def endpoint(self, *args, trailing_slash=True, base_url=None):
        parts = list(args)

        # Ensure trailing slash!
        if trailing_slash:
            parts.append('')

        url = self.url if not base_url else base_url

        return urljoin(url, self._join_path(parts))

    def json(self, resp):
        resp.raise_for_status()

        return resp.json()

########################################################################################################################
# DEEPLINKS
########################################################################################################################

    def check_definition_url(self, check_definition: dict) -> str:
        """
        Return direct deeplink to check definition view on ZMON UI.

        :param check_definition: check_difinition dict.
        :type check_definition: dict

        :return: Deeplink to check definition view.
        :rtype: str
        """
        return self.endpoint(CHECK_DEF_VIEW_URL, check_definition['id'], base_url=self.base_url)

    def alert_details_url(self, alert: dict) -> str:
        """
        Return direct deeplink to alert details view on ZMON UI.

        :param alert: alert dict.
        :type alert: dict

        :return: Deeplink to alert details view.
        :rtype: str
        """
        return self.endpoint(ALERT_DETAILS_VIEW_URL, alert['id'], base_url=self.base_url)

    def dashboard_url(self, dashboard_id: int) -> str:
        """
        Return direct deeplink to ZMON dashboard.

        :param dashboard_id: ZMON Dashboard ID.
        :type dashboard_id: int

        :return: Deeplink to dashboard.
        :rtype: str
        """
        return self.endpoint(DASHBOARD_VIEW_URL, dashboard_id, base_url=self.base_url)

    def token_login_url(self, token: str) -> str:
        """
        Return direct deeplink to ZMON one-time login.

        :param token: One-time token.
        :type token: str

        :return: Deeplink to ZMON one-time login.
        :rtype: str
        """
        return self.endpoint(TOKEN_LOGIN_URL, token, base_url=self.base_url)

    def grafana_dashboard_url(self, dashboard: dict) -> str:
        """
        Return direct deeplink to Grafana dashboard.

        :param dashboard: Grafana dashboard dict.
        :type dashboard: dict

        :return: Deeplink to Grafana dashboard.
        :rtype: str
        """
        return self.endpoint(GRAFANA_DASHBOARD_URL, dashboard['dashboard']['id'], base_url=self.base_url)

    @logged
    def status(self) -> dict:
        """
        Return ZMON status from status API.

        :return: ZMON status.
        :rtype: dict
        """
        resp = self.session.get(self.endpoint(STATUS))

        return self.json(resp)

########################################################################################################################
# ENTITIES
########################################################################################################################

    @logged
    def get_entities(self, query=None) -> list:
        """
        Get ZMON entities, with optional filtering.

        :param query: Entity filtering query. Default is ``None``. Example query ``{'type': 'instance'}`` to return
                      all entities of type: ``instance``.
        :type query: dict

        :return: List of entities.
        :rtype: list
        """
        query_str = json.dumps(query) if query else ''
        logger.debug('Retrieving entities with query: {} ...'.format(query_str))

        params = {'query': query_str} if query else None

        resp = self.session.get(self.endpoint(ENTITIES), params=params)

        return self.json(resp)

    @logged
    def get_entity(self, entity_id: str) -> str:
        """
        Retrieve single entity.

        :param entity_id: Entity ID.
        :type entity_id: str

        :return: Entity dict.
        :rtype: dict
        """
        logger.debug('Retrieving entities with id: {} ...'.format(entity_id))

        resp = self.session.get(self.endpoint(ENTITIES, entity_id, trailing_slash=False))
        return self.json(resp)

    @logged
    def add_entity(self, entity: dict) -> requests.Response:
        """
        Create or update an entity on ZMON.

        .. note::

            ZMON PUT entity API doesn't return JSON response.

        :param entity: Entity dict.
        :type entity: dict

        :return: Response object.
        :rtype: :class:`requests.Response`
        """
        if 'id' not in entity or 'type' not in entity:
            raise ZmonArgumentError('Entity "id" and "type" are required.')

        if not self.is_valid_entity_id(entity['id']):
            raise ZmonArgumentError('Invalid entity ID.')

        logger.debug('Adding new entity: {} ...'.format(entity['id']))

        data = json.dumps(entity, cls=JSONDateEncoder)
        resp = self.session.put(self.endpoint(ENTITIES, trailing_slash=False), data=data)

        resp.raise_for_status()

        return resp

    @logged
    def delete_entity(self, entity_id: str) -> bool:
        """
        Delete entity from ZMON.

        .. note::

            ZMON DELETE entity API doesn't return JSON response.

        :param entity_id: Entity ID.
        :type entity_id: str

        :return: True if succeeded, False otherwise.
        :rtype: bool
        """
        logger.debug('Removing existing entity: {} ...'.format(entity_id))

        resp = self.session.delete(self.endpoint(ENTITIES, entity_id))

        resp.raise_for_status()

        return resp.text == '1'

########################################################################################################################
# DASHBOARD
########################################################################################################################

    @logged
    def get_dashboard(self, dashboard_id: str) -> dict:
        """
        Retrieve a ZMON dashboard.

        :param dashboard_id: ZMON dashboard ID.
        :type dashboard_id: int, str

        :return: Dashboard dict.
        :rtype: dict
        """
        resp = self.session.get(self.endpoint(DASHBOARD, dashboard_id))

        return self.json(resp)

    @logged
    def update_dashboard(self, dashboard: dict) -> dict:
        """
        Create or update dashboard.

        If dashboard has an ``id`` then dashboard will be updated, otherwise a new dashboard is created.

        :param dashboard: ZMON dashboard dict.
        :type dashboard: int, str

        :return: Dashboard dict.
        :rtype: dict
        """
        if 'id' in dashboard and dashboard['id']:
            logger.debug('Updating dashboard with ID: {} ...'.format(dashboard['id']))

            resp = self.session.post(self.endpoint(DASHBOARD, dashboard['id']), json=dashboard)
        else:
            # new dashboard
            logger.debug('Adding new dashboard ...')
            resp = self.session.post(self.endpoint(DASHBOARD), json=dashboard)

        resp.raise_for_status()

        return self.json(resp)

########################################################################################################################
# CHECK-DEFS
########################################################################################################################

    @logged
    def get_check_definition(self, definition_id: int) -> dict:
        """
        Retrieve check defintion.

        :param defintion_id: Check defintion id.
        :type defintion_id: int

        :return: Check definition dict.
        :rtype: dict
        """
        resp = self.session.get(self.endpoint(CHECK_DEF, definition_id))

        # TODO: total hack! API returns 200 if check def does not exist!
        if resp.text == '':
            resp.status_code = 404
            resp.reason = 'Not Found'

        return self.json(resp)

    @logged
    def get_check_definitions(self) -> list:
        """
        Return list of all ``active`` check definitions.

        :return: List of check-defs.
        :rtype: list
        """
        resp = self.session.get(self.endpoint(ACTIVE_CHECK_DEF))

        return self.json(resp).get('check_definitions')

    @logged
    def update_check_definition(self, check_definition: dict) -> dict:
        """
        Update existing check definition.

        Atrribute ``owning_team`` is required. If ``status`` is not set, then it will be set to ``ACTIVE``.

        :param check_definition: ZMON check definition dict.
        :type check_definition: dict

        :return: Check definition dict.
        :rtype: dict
        """
        if 'owning_team' not in check_definition:
            raise ZmonArgumentError('Check definition must have "owning_team"')

        if 'status' not in check_definition:
            check_definition['status'] = 'ACTIVE'

        self.validate_check_command(check_definition['command'])

        resp = self.session.post(self.endpoint(CHECK_DEF), json=check_definition)

        return self.json(resp)

    @logged
    def delete_check_definition(self, check_definition_id: int) -> requests.Response:
        """
        Delete existing check definition.

        :param check_definition_id: ZMON check definition ID.
        :type check_definition_id: int

        :return: HTTP response.
        :rtype: :class:`requests.Response`
        """
        resp = self.session.delete(self.endpoint(CHECK_DEF, check_definition_id))

        resp.raise_for_status()

        return resp

########################################################################################################################
# ALERT-DEFS & DATA
########################################################################################################################

    @logged
    def get_alert_definition(self, alert_id: int) -> dict:
        """
        Retrieve alert definition.

        :param alert_id: Alert definition ID.
        :type alert_id: int

        :return: Alert definition dict.
        :rtype: dict
        """
        resp = self.session.get(self.endpoint(ALERT_DEF, alert_id))

        return self.json(resp)

    @logged
    def get_alert_definitions(self) -> list:
        """
        Return list of all ``active`` alert definitions.

        :return: List of alert-defs.
        :rtype: list
        """
        resp = self.session.get(self.endpoint(ACTIVE_ALERT_DEF))

        return self.json(resp).get('alert_definitions')

    @logged
    def create_alert_definition(self, alert_definition: dict) -> dict:
        """
        Create new alert definition.

        Attributes ``last_modified_by`` and ``check_definition_id`` are required.
        If ``status`` is not set, then it will be set to ``ACTIVE``.

        :param alert_definition: ZMON alert definition dict.
        :type alert_definition: dict

        :return: Alert definition dict.
        :rtype: dict
        """
        if 'last_modified_by' not in alert_definition:
            raise ZmonArgumentError('Alert definition must have "last_modified_by"')

        if 'status' not in alert_definition:
            alert_definition['status'] = 'ACTIVE'

        if 'check_definition_id' not in alert_definition:
            raise ZmonArgumentError('Alert defintion must have "check_definition_id"')

        resp = self.session.post(self.endpoint(ALERT_DEF), json=alert_definition)

        return self.json(resp)

    @logged
    def update_alert_definition(self, alert_definition: dict) -> dict:
        """
        Update existing alert definition.

        Atrributes ``id``, ``last_modified_by`` and ``check_definition_id`` are required.
        If ``status`` is not set, then it will be set to ``ACTIVE``.

        :param alert_definition: ZMON alert definition dict.
        :type alert_definition: dict

        :return: Alert definition dict.
        :rtype: dict
        """
        if 'last_modified_by' not in alert_definition:
            raise ZmonArgumentError('Alert definition must have "last_modified_by"')

        if 'id' not in alert_definition:
            raise ZmonArgumentError('Alert definition must have "id"')

        if 'check_definition_id' not in alert_definition:
            raise ZmonArgumentError('Alert defintion must have "check_definition_id"')

        if 'status' not in alert_definition:
            alert_definition['status'] = 'ACTIVE'

        resp = self.session.put(
            self.endpoint(ALERT_DEF, alert_definition['id']), json=alert_definition)

        return self.json(resp)

    @logged
    def delete_alert_definition(self, alert_definition_id: int) -> dict:
        """
        Delete existing alert definition.

        :param alert_definition_id: ZMON alert definition ID.
        :type alert_definition_id: int

        :return: Alert definition dict.
        :rtype: dict
        """
        resp = self.session.delete(self.endpoint(ALERT_DEF, alert_definition_id))

        return self.json(resp)

    @logged
    def get_alert_data(self, alert_id: int) -> dict:
        """
        Retrieve alert data.

        Response is a ``dict`` with entity ID as a key, and check return value as a value.

        :param alert_id: ZMON alert ID.
        :type alert_id: int

        :return: Alert data dict.
        :rtype: dict

        Example:

        .. code-block:: json

            {
                "entity-id-1": 122,
                "entity-id-2": 0,
                "entity-id-3": 100
            }
        """
        resp = self.session.get(self.endpoint(ALERT_DATA, alert_id, 'all-entities'))

        return self.json(resp)

########################################################################################################################
# SEARCH
########################################################################################################################

    @logged
    def search(self, q, teams: list=None) -> dict:
        """
        Search ZMON dashboards, checks, alerts and grafana dashboards with optional team filtering.

        :param q: search query.
        :type q: str

        :param teams: List of team IDs. Default is None.
        :type teams: list

        :return: Search result.
        :rtype: dict

        Example:

        .. code-block:: json

            {
                "alerts": [{"id": "123", "title": "ZMON alert", "team": "ZMON"}],
                "checks": [{"id": "123", "title": "ZMON check", "team": "ZMON"}],
                "dashboards": [{"id": "123", "title": "ZMON dashboard", "team": "ZMON"}],
                "grafana_dashboards": [{"id": "123", "title": "ZMON grafana", "team": ""}],
            }
        """
        if not q:
            raise ZmonArgumentError('No search query value!')

        if teams and type(teams) not in (list, tuple):
            raise ZmonArgumentError('"teams" should be a list!')

        params = {'query': q}
        if teams:
            params['teams'] = ','.join(teams)

        resp = self.session.get(self.endpoint(SEARCH), params=params)

        return self.json(resp)


########################################################################################################################
# ONETIME-TOKENS
########################################################################################################################

    @logged
    def list_onetime_tokens(self) -> list:
        """
        List exisitng one-time tokens.

        :return: List of one-time tokens, with relevant attributes.
        :retype: list

        Example:

        .. code-block:: yaml

            - bound_at: 2016-09-08 14:00:12.645999
              bound_expires: 1503744673506
              bound_ip: 192.168.20.16
              created: 2016-08-26 12:51:13.506000
              token: 9pSzKpcO
        """
        resp = self.session.get(self.endpoint(TOKENS))

        return self.json(resp)

    @logged
    def get_onetime_token(self) -> str:
        """
        Retrieve new one-time token.

        You can use :func:`zmon_cli.client.Zmon.token_login_url` to return a deeplink to one-time login.

        :return: One-time token.
        :retype: str
        """
        resp = self.session.post(self.endpoint(TOKENS), json={})

        resp.raise_for_status()

        return resp.text

########################################################################################################################
# GRAFANA
########################################################################################################################

    @logged
    def get_grafana_dashboard(self, grafana_dashboard_id: str) -> dict:
        """
        Retrieve Grafana dashboard.

        :param grafana_dashboard_id: Grafana dashboard ID.
        :type grafana_dashboard_id: str

        :return: Grafana dashboard dict.
        :rtype: dict
        """
        resp = self.session.get(self.endpoint(GRAFANA, grafana_dashboard_id))

        return self.json(resp)

    @logged
    def update_grafana_dashboard(self, grafana_dashboard: dict) -> dict:
        """
        Update existing Grafana dashboard.

        Atrributes ``id`` and ``title`` are required.

        :param grafana_dashboard: Grafana dashboard dict.
        :type grafana_dashboard: dict

        :return: Grafana dashboard dict.
        :rtype: dict
        """
        if 'id' not in grafana_dashboard['dashboard']:
            raise ZmonArgumentError('Grafana dashboard must have "id"')
        elif 'title' not in grafana_dashboard['dashboard']:
            raise ZmonArgumentError('Grafana dashboard must have "title"')

        resp = self.session.post(self.endpoint(GRAFANA), json=grafana_dashboard)

        return self.json(resp)

########################################################################################################################
# DOWNTIMES
########################################################################################################################

    @logged
    def create_downtime(self, downtime: dict) -> dict:
        """
        Create a downtime for specific entities.

        Atrributes ``entities`` list, ``start_time`` and ``end_time`` timestamps are required.

        :param downtime: Downtime dict.
        :type downtime: dict

        :return: Downtime dict.
        :rtype: dict

        Example downtime:

        .. code-block:: json

            {
                "entities": ["entity-id-1", "entity-id-2"],
                "comment": "Planned maintenance",
                "start_time": 1473337437.312921,
                "end_time": 1473341037.312921,
            }
        """
        if not downtime.get('entities'):
            raise ZmonArgumentError('At least one entity ID should be specified')

        if not downtime.get('start_time') or not downtime.get('end_time'):
            raise ZmonArgumentError('Downtime must specify "start_time" and "end_time"')

        resp = self.session.post(self.endpoint(DOWNTIME), json=downtime)

        return self.json(resp)

########################################################################################################################
# GROUPS - MEMBERS - ???
########################################################################################################################

    @logged
    def get_groups(self):
        resp = self.session.get(self.endpoint(GROUPS))

        return self.json(resp)

    @logged
    def switch_active_user(self, group_name, user_name):
        resp = self.session.delete(self.endpoint(GROUPS, group_name, 'active'))

        if not resp.ok:
            logger.error('Failed to de-activate group: {}'.format(group_name))
            resp.raise_for_status()

        logger.debug('Switching active user: {}'.format(user_name))

        resp = self.session.put(self.endpoint(GROUPS, group_name, 'active', user_name))

        if not resp.ok:
            logger.error('Failed to switch active user {}'.format(user_name))
            resp.raise_for_status()

        return resp.text == '1'

    @logged
    def add_member(self, group_name, user_name):
        resp = self.session.put(self.endpoint(GROUPS, group_name, MEMBER, user_name))

        resp.raise_for_status

        return resp.text == '1'

    @logged
    def remove_member(self, group_name, user_name):
        resp = self.session.delete(self.endpoint(GROUPS, group_name, MEMBER, user_name))

        resp.raise_for_status()

        return resp.text == '1'

    @logged
    def add_phone(self, member_email, phone_nr):
        resp = self.session.put(self.endpoint(GROUPS, member_email, PHONE, phone_nr))

        resp.raise_for_status()

        return resp.text == '1'

    @logged
    def remove_phone(self, member_email, phone_nr):
        resp = self.session.delete(self.endpoint(GROUPS, member_email, PHONE, phone_nr))

        resp.raise_for_status()

        return resp.text == '1'

    @logged
    def set_name(self, member_email, member_name):
        resp = self.session.put(self.endpoint(GROUPS, member_email, PHONE, member_name))

        resp.raise_for_status()

        return resp
