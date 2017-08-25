"""
VCloud Director client base class.
"""
import logging
import requests

from requests.auth import HTTPBasicAuth
from config import BASE_URL, PASSWORD, USERNAME

logging.basicConfig(level=logging.INFO, format='%(name)s %(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)

VCD_AUTH_HDR = 'x-vcloud-authorization'


def vcd_session():
    session = requests.Session()
    session.auth = HTTPBasicAuth(USERNAME, PASSWORD)
    session.headers = {'accept': 'application/*+xml;version=5.5'}
    session.verify = False
    return session


class VCloudDirectorBase(object):
    """Handles connections and basic request methods.
    """

    def __init__(self):
        """Initiate a session and login
        """
        self.session = vcd_session()
        self.login()

    def _request(self, method, path, *args, **kwargs):
        """Make and error check a request in the current session.
        """
        url = '{}/{}'.format(BASE_URL, path)
        return self.session.request(method, url, *args, **kwargs)

    def login(self):
        """Login to vCloud Director.
        """
        auth = self.session.post('{}/sessions'.format(BASE_URL))

        if 'x-vcloud-authorization' not in auth.headers:
            raise Exception('Not authorized to access vCloud Director')

        logger.debug('Login Successful')
        self.session.headers.update({'X-Vcloud-Authorization': auth.headers['x-vcloud-authorization']})

    def logout(self):
        """Log out of vCloud Director.
        """
        response = self.session.delete('{}/{}'.format(BASE_URL, '/session'))

        if response.status_code in (200, 204):
            logger.debug('Logout Successful')
            self.session = None
        else:
            logger.warn('Logout Failed')
            logger.error(response.status_code)
            logger.error(response.text)

    def vcd_request(self, method, href, *args, **kwargs):
        """Perform a VCD request using passed in href USE This for a fully
        formed HREF - such as those returned from other CCD calls.
        """
        return self.session.request(method, href, *args, **kwargs)
