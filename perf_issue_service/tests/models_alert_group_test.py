# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from unittest import mock
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.alert_group import AlertGroup
from application.clients import datastore_client


class AlertGroupTest(unittest.TestCase):

  @mock.patch.object(AlertGroup, 'ds_client')
  @mock.patch('models.alert_group.AlertGroup.Get')
  @mock.patch(
      'application.clients.sheriff_config_client.GetSheriffConfigClient')
  def testGetGroupsForAnomaly_missingDomain(self, mock_sheriff, mock_get,
                                            mock_ds_client):
    # Mock sheriff config
    mock_sheriff_instance = mock.Mock()
    mock_sheriff_instance.Match.return_value = ([{
        'subscription': {
            'name': 'test_sub',
            'monorail_project_id': 'chromium'
        }
    }], None)
    mock_sheriff.return_value = mock_sheriff_instance

    # Mock an existing group missing the 'domain' key
    mock_group = mock.MagicMock()
    mock_group_dict = {
        'revision': {
            'start': 100,
            'end': 200
        },
        'subscription_name': 'test_sub'
    }
    mock_group.get.side_effect = mock_group_dict.get
    mock_group.__getitem__.side_effect = mock_group_dict.__getitem__
    mock_group.__contains__.side_effect = mock_group_dict.__contains__
    mock_group.key.name = "test_group"

    mock_get.return_value = [mock_group]

    # If the KeyError is fixed, this won't crash when it accesses g.get('domain')
    group_ids, new_ids = AlertGroup.GetGroupsForAnomaly(
        test_key="master/bot/benchmark",
        start_rev=150,
        end_rev=160,
        create_on_ungrouped=True)

    # Since domain doesn't match 'master', has_overlapped should be False,
    # so it should try to create a new group.
    mock_ds_client.NewAlertGroup.assert_called_once()

  def testGetUngroupedGroupName_staticmethod(self):
    # Verify it doesn't crash with TypeError when called as a staticmethod
    name = AlertGroup._GetUngroupedGroupName(
        datastore_client.AlertGroupType.test_suite)
    self.assertEqual(name, 'Ungrouped')


if __name__ == '__main__':
  unittest.main()
