# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The general handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "GeneralHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.models.bootresource import BootResource
from maasserver.models.candidatename import gen_candidate_names
from maasserver.models.node import Node
from maasserver.node_action import ACTIONS_DICT
from maasserver.utils.osystems import (
    list_all_usable_osystems,
    list_all_usable_releases,
    list_osystem_choices,
    list_release_choices,
)
from maasserver.websockets.base import Handler


class GeneralHandler(Handler):
    """Provides general methods that can be called from the client."""

    class Meta:
        allowed_methods = [
            'architectures',
            'osinfo',
            'node_actions',
            'device_actions',
            'random_hostname',
            ]

    def architectures(self, params):
        """Return all supported architectures."""
        return sorted(BootResource.objects.get_usable_architectures())

    def osinfo(self, params):
        """Return all available operating systems and releases information."""
        osystems = list_all_usable_osystems()
        releases = list_all_usable_releases(osystems)
        return {
            "osystems": list_osystem_choices(osystems),
            "releases": list_release_choices(releases),
        }

    def dehydrate_actions(self, actions):
        """Dehydrate all the actions."""
        return [
            {
                "name": name,
                "title": action.display,
                "sentence": action.display_sentence,
            }
            for name, action in actions.items()
            ]

    def node_actions(self, params):
        """Return all possible node actions."""
        if self.user.is_superuser:
            actions = ACTIONS_DICT
        else:
            # Standard users will not be able to use any admin actions. Hide
            # them as they will never be actionable on any node.
            actions = dict()
            for name, action in ACTIONS_DICT.items():
                permission = action.permission
                if action.installable_permission is not None:
                    permission = action.installable_permission
                if permission != NODE_PERMISSION.ADMIN:
                    actions[name] = action
        return self.dehydrate_actions(actions)

    def device_actions(self, params):
        """Return all possible device actions."""
        # Remove the actions that can only be performed on installable nodes.
        actions = {
            name: action
            for name, action in ACTIONS_DICT.items()
            if not action.installable_only
            }
        return self.dehydrate_actions(actions)

    def random_hostname(self, params):
        """Return a random hostname."""
        for new_hostname in gen_candidate_names():
            try:
                Node.objects.get(hostname=new_hostname)
            except Node.DoesNotExist:
                return new_hostname
        return ""
