# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: reset region controller configuration settings."""

__all__ = ["Command"]

from maasserver.management.commands._config import ResetCommand as Command
