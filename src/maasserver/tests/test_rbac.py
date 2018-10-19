from unittest import mock

from maasserver.enum import NODE_PERMISSION
from maasserver.models import (
    Config,
    ResourcePool,
)
from maasserver.rbac import (
    ALL_RESOURCES,
    FakeRBACClient,
    RBAC,
    RBACClient,
    Resource,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from macaroonbakery.bakery import PrivateKey
from macaroonbakery.httpbakery.agent import (
    Agent,
    AuthInfo,
)
import requests


class TestRBACClient(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        key = PrivateKey.deserialize(
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')
        agent = Agent(
            url='https://auth.example.com', username='user@candid')
        auth_info = AuthInfo(key=key, agents=[agent])
        url = 'https://rbac.example.com'

        self.mock_request = self.patch(requests, 'request')
        self.client = RBACClient(url=url, auth_info=auth_info)

    def test_default_config_from_settings(self):
        Config.objects.set_config('rbac_url', 'https://rbac.example.com')
        Config.objects.set_config(
            'external_auth_url', 'https://auth.example.com')
        Config.objects.set_config('external_auth_user', 'user@candid')
        Config.objects.set_config(
            'external_auth_key',
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')
        client = RBACClient()
        self.assertEqual(client._url, 'https://rbac.example.com')
        self.assertEqual(
            client._auth_info.key,
            PrivateKey.deserialize(
                'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY='))
        [agent] = client._auth_info.agents
        self.assertEqual(agent.url, 'https://auth.example.com')
        self.assertEqual(agent.username, 'user@candid')

    def test_get_resources(self):
        resources = [
            {
                'identifier': '1',
                'name': 'pool-1',
            },
            {
                'identifier': '2',
                'name': 'pool-2',
            },
        ]
        response = mock.MagicMock(status_code=200)
        response.json.return_value = resources
        self.mock_request.return_value = response
        self.assertCountEqual(self.client.get_resources('resource-pool'), [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ])
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=None))

    def test_update_resources(self):
        updates = [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ]
        removals = [11, 22, 33]
        json = {
            'last-sync-id': 'a-b-c',
            'updates': [
                {
                    'identifier': '1',
                    'name': 'pool-1',
                },
                {
                    'identifier': '2',
                    'name': 'pool-2',
                },
            ],
            'removals': ['11', '22', '33']
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {'sync-id': 'x-y-z'}
        self.mock_request.return_value = response
        sync_id = self.client.update_resources(
            'resource-pool', updates=updates, removals=removals,
            last_sync_id='a-b-c')
        self.assertEqual(sync_id, 'x-y-z')
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'POST',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=json))

    def test_update_resources_no_sync_id(self):
        updates = [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ]
        removals = [11, 22, 33]
        # removals are ignored
        json = {
            'last-sync-id': None,
            'updates': [
                {
                    'identifier': '1',
                    'name': 'pool-1',
                },
                {
                    'identifier': '2',
                    'name': 'pool-2',
                },
            ],
            'removals': []
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {'sync-id': 'x-y-z'}
        self.mock_request.return_value = response
        sync_id = self.client.update_resources(
            'resource-pool', updates=updates, removals=removals)
        self.assertEqual(sync_id, 'x-y-z')
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'POST',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=json))

    def test_allowed_for_user_all_resources(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = [""]
        self.mock_request.return_value = response

        user = factory.make_name('user')
        self.assertEqual(
            ALL_RESOURCES, self.client.allowed_for_user('maas', user, 'admin'))
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/maas/'
                'allowed-for-user?user={}&permission=admin'.format(user),
                auth=mock.ANY, cookies=mock.ANY, json=None))

    def test_allowed_for_user_resource_ids(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = ["1", "2", "3"]
        self.mock_request.return_value = response

        user = factory.make_name('user')
        self.assertEqual(
            [1, 2, 3], self.client.allowed_for_user('maas', user, 'admin'))
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/maas/'
                'allowed-for-user?user={}&permission=admin'.format(user),
                auth=mock.ANY, cookies=mock.ANY, json=None))


class TestRBACIsEnabled(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        Config.objects.set_config('external_auth_user', 'user@candid')
        Config.objects.set_config(
            'external_auth_key',
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')

    def test_local_disabled(self):
        Config.objects.set_config('external_auth_url', '')
        Config.objects.set_config('rbac_url', '')
        rbac = RBAC()
        self.assertFalse(rbac.is_enabled())

    def test_candid_disabled(self):
        Config.objects.set_config(
            'external_auth_url', 'http://candid.example.com')
        Config.objects.set_config('rbac_url', '')
        rbac = RBAC()
        self.assertFalse(rbac.is_enabled())

    def test_rbac_enabled(self):
        Config.objects.set_config('external_auth_url', '')
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        rbac = RBAC()
        self.assertTrue(rbac.is_enabled())


class TestRBACGetResourcePools(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        self.client = FakeRBACClient()
        self.store = self.client.store
        self.rbac = RBAC(client=self.client)
        self.default_pool = (
            ResourcePool.objects.get_default_resource_pool())
        self.store.add_pool(self.default_pool)

    def test_get_resource_pools_unknown_user(self):
        self.store.add_pool(factory.make_ResourcePool())
        self.assertNotIn('user', self.store.allowed)
        self.assertEqual(
            [],
            list(self.rbac.get_resource_pools('user', NODE_PERMISSION.VIEW)))

    def test_get_resource_pools_user_allowed_all(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow('user', ALL_RESOURCES, 'view')
        self.assertCountEqual(
            [self.default_pool, pool1, pool2],
            self.rbac.get_resource_pools('user', NODE_PERMISSION.VIEW))

    def test_get_resource_pools_user_allowed_other_permission(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow('user', pool1, 'view')
        self.store.allow('user', pool2, 'edit')
        self.assertCountEqual(
            [pool1],
            self.rbac.get_resource_pools('user', NODE_PERMISSION.VIEW))
        self.assertCountEqual(
            [],
            self.rbac.get_resource_pools('user', NODE_PERMISSION.ADMIN))

    def test_get_resource_pools_user_allowed_some(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow('user', pool1, 'view')
        self.assertEqual(
            sorted([pool1]),
            sorted(self.rbac.get_resource_pools('user', NODE_PERMISSION.VIEW)))
