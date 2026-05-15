# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest
from unittest import mock

import sys

# Mock apache_beam modules to prevent running full Beam pipeline logic
# and to match the environment of spanner_dash_test.py
mock_beam = mock.MagicMock()
sys.modules['apache_beam'] = mock_beam
sys.modules['apache_beam.options'] = mock_beam.options
sys.modules[
    'apache_beam.options.pipeline_options'] = mock_beam.options.pipeline_options
sys.modules['apache_beam.metrics'] = mock_beam.metrics
sys.modules['apache_beam.io'] = mock_beam.io
sys.modules['apache_beam.io.gcp'] = mock_beam.io.gcp
sys.modules['apache_beam.io.gcp.spanner'] = mock_beam.io.gcp.spanner

from bq_export.spanner_dash_page_state import PageStateEntityToRowDict, \
  _ExtractIds


class MockEntity(object):

  def __init__(self, data, key_name=None, key_id=None):
    self.data = data
    self.key = mock.MagicMock()
    self.key.name = key_name
    self.key.id = key_id

  def __getitem__(self, key):
    return self.data[key]

  def get(self, key, default=None):
    return self.data.get(key, default)

  def __contains__(self, key):
    return key in self.data

  def to_client_entity(self):
    return self


class SpannerDashPageStateTest(unittest.TestCase):

  def testExtractIds_int(self):
    self.assertEqual(_ExtractIds(12345), [12345])

  def testExtractIds_str_int(self):
    self.assertEqual(_ExtractIds('12345'), [12345])

  def testExtractIds_str_urlsafe(self):
    # An Example base64 legacy urlsafe key
    # This urlsafe key is: Key('Anomaly', 56789)
    urlsafe_str = 'ag5zfmNocm9tZXBlcmZyEwsSB0Fub21hbHkYmdkDAw'
    k_mock = mock.MagicMock()
    k_mock.kind = 'Anomaly'
    k_mock.id = 56789

    with mock.patch(
        'google.cloud.datastore.key.Key.from_legacy_urlsafe',
        return_value=k_mock):
      self.assertEqual(_ExtractIds(urlsafe_str), [56789])

  def testExtractIds_comma_str(self):
    self.assertEqual(_ExtractIds('123, 456, invalid_id, 789'), [123, 456, 789])

  def testExtractIds_list(self):
    self.assertEqual(_ExtractIds([123, '456', 'invalid']), [123, 456])

  def testExtractIds_dict(self):
    self.assertEqual(_ExtractIds({'key1': 123, 'key2': '456'}), [123, 456])

  def testPageStateEntityToRowDict_v2(self):
    data = {'value_v2': b'["key1", "key2"]'}
    entity = MockEntity(data, key_name='test_hash_v2')

    k1 = mock.MagicMock()
    k1.kind = 'Anomaly'
    k1.id = 123

    k2 = mock.MagicMock()
    k2.kind = 'Anomaly'
    k2.id = 456

    def mock_from_legacy_urlsafe(urlsafe):
      if urlsafe == 'key1':
        return k1
      if urlsafe == 'key2':
        return k2
      raise Exception('Unexpected urlsafe key')

    with mock.patch(
        'google.cloud.datastore.key.Key.from_legacy_urlsafe',
        side_effect=mock_from_legacy_urlsafe):
      rows = PageStateEntityToRowDict(entity)
      self.assertEqual(len(rows), 1)
      self.assertEqual(rows[0].state_id, 'test_hash_v2')
      self.assertEqual(sorted(rows[0].anomaly_ids), [123, 456])

  def testPageStateEntityToRowDict_value(self):
    data = {'value': b'["key_state"]'}
    entity = MockEntity(data, key_id=98765)

    k = mock.MagicMock()
    k.kind = 'Anomaly'
    k.id = 987

    with mock.patch(
        'google.cloud.datastore.key.Key.from_legacy_urlsafe', return_value=k):
      rows = PageStateEntityToRowDict(entity)
      self.assertEqual(len(rows), 1)
      self.assertEqual(rows[0].state_id, '98765')
      self.assertEqual(sorted(rows[0].anomaly_ids), [987])

  def testPageStateEntityToRowDict_rejected_comma_separated(self):
    data = {'value': b'123,456,789'}
    entity = MockEntity(data, key_id=12)
    rows = PageStateEntityToRowDict(entity)
    self.assertEqual(rows, [])

  def testPageStateEntityToRowDict_rejected_json_int(self):
    data = {'value': b'[123, 456, 789]'}
    entity = MockEntity(data, key_id=34)
    rows = PageStateEntityToRowDict(entity)
    self.assertEqual(rows, [])

  def testPageStateEntityToRowDict_rejected_non_anomaly(self):
    data = {'value': b'["urlsafe_non_anomaly"]'}
    entity = MockEntity(data, key_id=56)

    k = mock.MagicMock()
    k.kind = 'TestMetadata'
    k.id = 789

    with mock.patch(
        'google.cloud.datastore.key.Key.from_legacy_urlsafe', return_value=k):
      rows = PageStateEntityToRowDict(entity)
      self.assertEqual(rows, [])


if __name__ == '__main__':
  unittest.main()
