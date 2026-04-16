# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest
from unittest import mock
from datetime import datetime
from apache_beam.utils.timestamp import Timestamp

import sys

mock_beam = mock.MagicMock()
sys.modules['apache_beam'] = mock_beam
sys.modules['apache_beam.options'] = mock_beam.options
sys.modules[
    'apache_beam.options.pipeline_options'] = mock_beam.options.pipeline_options
sys.modules['apache_beam.metrics'] = mock_beam.metrics
sys.modules['apache_beam.io'] = mock_beam.io
sys.modules['apache_beam.io.gcp'] = mock_beam.io.gcp
sys.modules['apache_beam.io.gcp.spanner'] = mock_beam.io.gcp.spanner

from bq_export.spanner_dash import AnomalyEntityToRowDict


class MockEntity(object):

  def __init__(self, data, key_id):
    self.data = data
    self.key = mock.MagicMock(id=key_id)

  def __getitem__(self, key):
    return self.data[key]

  def get(self, key, default=None):
    return self.data.get(key, default)

  def __contains__(self, key):
    return key in self.data


class SpannerDashTest(unittest.TestCase):

  def testAnomalyEntityToRowDict(self):
    mock_key = mock.MagicMock()
    mock_key.kind = 'Test'
    mock_key.flat_path = ['Master', 'master', 'Bot', 'bot', 'Test', 'test']

    test_dt = datetime(2026, 4, 16)

    data = {
        'test': mock_key,
        'timestamp': test_dt,
        'start_revision': 1000,
        'end_revision': 2000,
        'statistic': 'value',
        'bug_id': 654321,
        'internal_only': False,
        'is_improvement': False,
        'recovered': False,
    }
    entity = MockEntity(data, 12345)

    rows = AnomalyEntityToRowDict(entity)
    self.assertEqual(len(rows), 1)
    row_dict = rows[0]._asdict()
    self.assertEqual(row_dict['id'], 12345)
    self.assertEqual(row_dict['bug_id'], 654321)
    self.assertEqual(row_dict['test'], 'master/bot/test')
    self.assertEqual(row_dict['timestamp'], Timestamp(test_dt.timestamp()))

  def testAnomalyEntityToRowDict_withBytes(self):
    mock_key = mock.MagicMock()
    mock_key.kind = 'Test'
    mock_key.flat_path = ['Master', 'master', 'Bot', 'bot', 'Test', 'test']

    test_dt = datetime(2026, 4, 16)
    data = {
        'test': mock_key,
        'timestamp': test_dt,
        'anomaly_config': {
            'param': b'bytes_value'
        },
        'ownership': {
            'owner': b'owner_bytes'
        },
    }
    entity = MockEntity(data, 12345)

    rows = AnomalyEntityToRowDict(entity)
    self.assertEqual(len(rows), 1)

    import json
    row_dict = rows[0]._asdict()
    config = json.loads(row_dict['anomaly_config'])
    self.assertEqual(config['param'], 'bytes_value')
    ownership = json.loads(row_dict['ownership'])
    self.assertEqual(ownership['owner'], 'owner_bytes')

  def testAnomalyEntityToRowDict_withInfNaN(self):
    mock_key = mock.MagicMock()
    mock_key.kind = 'Test'
    mock_key.flat_path = ['Master', 'master', 'Bot', 'bot', 'Test', 'test']

    test_dt = datetime(2026, 4, 16)
    import math
    data = {
        'test': mock_key,
        'timestamp': test_dt,
        't_statistic': float('inf'),
        'p_value': float('nan'),
    }
    entity = MockEntity(data, 12345)

    rows = AnomalyEntityToRowDict(entity)
    self.assertEqual(len(rows), 1)

    row_dict = rows[0]._asdict()
    self.assertTrue(math.isinf(row_dict['t_statistic']))
    self.assertTrue(math.isnan(row_dict['p_value']))


if __name__ == '__main__':
  unittest.main()
