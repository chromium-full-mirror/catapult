#!/usr/bin/env vpython3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
from pathlib import Path
import unittest
from unittest import mock

app_path = Path(__file__).parent.parent.parent
if str(app_path) not in sys.path:
  sys.path.insert(0, str(app_path))

from application.perf_api import datastore_client


class DatastoreClientTest(unittest.TestCase):

  def setUp(self):
    self.client = datastore_client.DataStoreClient()
    self.client._client = mock.MagicMock()

  def test_create_legacy_test_key_short_path(self):
    self.assertIsNone(self.client._create_legacy_test_key('master/bot'))

  def test_create_legacy_test_key_valid_path(self):
    self.client._client.key.return_value = 'mock_key'
    key = self.client._create_legacy_test_key('master/bot/test/metric')
    self.client._client.key.assert_called_once_with('Master', 'master', 'Bot',
                                                    'bot', 'Test', 'test',
                                                    'Test', 'metric')
    self.assertEqual(key, 'mock_key')

  def test_GetFirstRowForRevision_without_test_path(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = [{'revision': 123}]

    row = self.client.GetFirstRowForRevision(123)

    self.client._client.query.assert_called_once_with(kind='Row',
                                                      order=['-revision'])
    mock_query.add_filter.assert_called_once_with('revision', '<=', 123)
    mock_query.fetch.assert_called_once_with(limit=1)
    self.assertEqual(row, {'revision': 123})

  def test_GetFirstRowForRevision_with_test_path(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = [{'revision': 123}]
    self.client._client.key.return_value = 'mock_key'

    row = self.client.GetFirstRowForRevision(123, 'master/bot/test')

    self.client._client.query.assert_called_once_with(kind='Row',
                                                      order=['-revision'])
    self.client._client.key.assert_called_once_with('Master', 'master', 'Bot',
                                                    'bot', 'Test', 'test')
    mock_query.add_filter.assert_has_calls([
        mock.call('parent_test', '=', 'mock_key'),
        mock.call('revision', '<=', 123)
    ])
    mock_query.fetch.assert_called_once_with(limit=1)
    self.assertEqual(row, {'revision': 123})

  def test_GetFirstRowForRevision_no_results(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = []

    row = self.client.GetFirstRowForRevision(123)

    self.client._client.query.assert_called_once_with(kind='Row',
                                                      order=['-revision'])
    mock_query.add_filter.assert_called_once_with('revision', '<=', 123)
    mock_query.fetch.assert_called_once_with(limit=1)
    self.assertEqual(row, {})

  def test_GetFirstRowForRevision_with_target_key_post_revision_true(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = [
        {'revision': 123},
        {'revision': 124, 'r_fuchsia_integ_int_git': 'hash124'}
    ]

    row = self.client.GetFirstRowForRevision(
        123, target_key='r_fuchsia_integ_int_git', post_revision=True)

    self.client._client.query.assert_called_once_with(kind='Row',
                                                      order=['revision'])
    mock_query.add_filter.assert_called_once_with('revision', '>=', 123)
    mock_query.fetch.assert_called_once_with(limit=10)
    self.assertEqual(
        row, {'revision': 124,
              'r_fuchsia_integ_int_git': 'hash124'})

  def test_GetFirstRowForRevision_with_target_key_post_revision_false(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = [
        {'revision': 123},
        {'revision': 122, 'r_fuchsia_integ_int_git': 'hash122'}
    ]

    row = self.client.GetFirstRowForRevision(
        123, target_key='r_fuchsia_integ_int_git', post_revision=False)

    self.client._client.query.assert_called_once_with(kind='Row',
                                                      order=['-revision'])
    mock_query.add_filter.assert_called_once_with('revision', '<=', 123)
    mock_query.fetch.assert_called_once_with(limit=10)
    self.assertEqual(
        row, {'revision': 122,
              'r_fuchsia_integ_int_git': 'hash122'})

  def test_GetFirstRowForRevision_with_target_key_no_match(self):
    mock_query = mock.MagicMock()
    self.client._client.query.return_value = mock_query
    mock_query.fetch.return_value = [
        {'revision': 123},
        {'revision': 122}
    ]

    row = self.client.GetFirstRowForRevision(
        123, target_key='r_fuchsia_integ_int_git', post_revision=False)

    self.assertEqual(row, {})


if __name__ == '__main__':
  unittest.main()
