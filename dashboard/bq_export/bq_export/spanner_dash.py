# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export chromeperf dashboard data to Spanner with Beam & Cloud Dataflow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
from typing import NamedTuple, List, Optional
import apache_beam as beam
from apache_beam.utils.timestamp import Timestamp
from apache_beam import coders
from apache_beam.options.pipeline_options import DebugOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics
from apache_beam.io.gcp.spanner import SpannerInsertOrUpdate

from bq_export.split_by_timestamp import ReadTimestampRangeFromDatastore
from bq_export.export_options import BqExportOptions
from bq_export.utils import (TestPath, PrintCounters)


class UnconvertibleAnomalyError(Exception):
  pass


entities_read = Metrics.counter('main', 'entities_read')
failed_entity_transforms = Metrics.counter('main', 'failed_entity_transforms')


def _JsonFallback(obj):
  if isinstance(obj, bytes):
    return obj.decode('utf-8', errors='replace')
  raise TypeError(
      f'Object of type {obj.__class__.__name__} is not JSON serializable')


def _SafeFloat(val):
  if val is None or val == '':
    return None
  return float(val)


class AnomalyRow(NamedTuple):
  id: int
  internal_only: bool
  timestamp: Optional[Timestamp]
  bug_id: Optional[int]
  project_id: Optional[str]
  groups: List[str]
  issues: Optional[str]
  state: Optional[str]
  subscription_names: List[str]
  anomaly_config: Optional[str]
  test: Optional[str]
  statistic: Optional[str]
  master_name: Optional[str]
  bot_name: Optional[str]
  benchmark_name: Optional[str]
  start_revision: Optional[int]
  end_revision: Optional[int]
  display_start: Optional[int]
  display_end: Optional[int]
  ownership: Optional[str]
  alert_grouping: List[str]
  segment_size_before: Optional[int]
  segment_size_after: Optional[int]
  median_before_anomaly: Optional[float]
  median_after_anomaly: Optional[float]
  std_dev_before_anomaly: Optional[float]
  window_end_revision: Optional[int]
  t_statistic: Optional[float]
  degrees_of_freedom: Optional[int]
  p_value: Optional[float]
  is_improvement: bool
  recovered: bool
  ref_test: Optional[str]
  units: Optional[str]
  pinpoint_bisects: List[str]
  recipe_bisects: List[str]
  earliest_input_timestamp: Optional[Timestamp]
  latest_input_timestamp: Optional[Timestamp]
  source: Optional[str]


coders.registry.register_coder(AnomalyRow, coders.RowCoder)


def AnomalyEntityToRowDict(entity):
  entities_read.inc()
  try:
    d = {
        'id':
            entity.key.id,
        'internal_only':
            entity.get('internal_only', False),
        'timestamp':
            Timestamp(entity['timestamp'].timestamp())
            if 'timestamp' in entity else None,
        'bug_id':
            entity.get('bug_id'),
        'project_id':
            entity.get('project_id'),
        'groups': [str(k) for k in entity.get('groups', [])],
        'issues':
            json.dumps([{
                'project_id': i.project_id,
                'issue_id': i.issue_id
            } for i in entity.get('issues', [])],
                       default=_JsonFallback) if 'issues' in entity else None,
        'state':
            entity.get('state'),
        'subscription_names':
            entity.get('subscription_names', []),
        'anomaly_config':
            json.dumps(entity.get('anomaly_config'), default=_JsonFallback)
            if 'anomaly_config' in entity else None,
        'test':
            TestPath(entity['test']) if 'test' in entity else None,
        'statistic':
            entity.get('statistic'),
        'master_name':
            TestPath(entity['test']).split('/')[0]
            if 'test' in entity else None,
        'bot_name':
            TestPath(entity['test']).split('/')[1]
            if 'test' in entity else None,
        'benchmark_name':
            TestPath(entity['test']).split('/')[2]
            if 'test' in entity else None,
        'start_revision':
            entity.get('start_revision'),
        'end_revision':
            entity.get('end_revision'),
        'display_start':
            entity.get('display_start'),
        'display_end':
            entity.get('display_end'),
        'ownership':
            json.dumps(entity.get('ownership'), default=_JsonFallback)
            if 'ownership' in entity else None,
        'alert_grouping':
            entity.get('alert_grouping', []),
        'segment_size_before':
            entity.get('segment_size_before'),
        'segment_size_after':
            entity.get('segment_size_after'),
        'median_before_anomaly':
            _SafeFloat(entity.get('median_before_anomaly')),
        'median_after_anomaly':
            _SafeFloat(entity.get('median_after_anomaly')),
        'std_dev_before_anomaly':
            _SafeFloat(entity.get('std_dev_before_anomaly')),
        'window_end_revision':
            entity.get('window_end_revision'),
        't_statistic':
            _SafeFloat(entity.get('t_statistic')),
        'degrees_of_freedom':
            entity.get('degrees_of_freedom'),
        'p_value':
            _SafeFloat(entity.get('p_value')),
        'is_improvement':
            entity.get('is_improvement', False),
        'recovered':
            entity.get('recovered', False),
        'ref_test':
            str(entity['ref_test']) if 'ref_test' in entity else None,
        'units':
            entity.get('units'),
        'pinpoint_bisects':
            entity.get('pinpoint_bisects', []),
        'recipe_bisects': [str(k) for k in entity.get('recipe_bisects', [])],
        'earliest_input_timestamp':
            Timestamp(entity['earliest_input_timestamp'].timestamp())
            if 'earliest_input_timestamp' in entity else None,
        'latest_input_timestamp':
            Timestamp(entity['latest_input_timestamp'].timestamp())
            if 'latest_input_timestamp' in entity else None,
        'source':
            entity.get('source'),
    }
    return [AnomalyRow(**d)]
  except Exception as e:
    failed_entity_transforms.inc()
    logging.error('Failed to convert entity: %s', e)
    return []


def main():
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--instance', required=True)
  parser.add_argument('--database', required=True)
  parser.add_argument('--table', default='anomalies')

  args, beam_args = parser.parse_known_args()

  project = 'chromeperf'
  project_spanner = 'skia-infra-corp'
  options = PipelineOptions(beam_args)
  options.view_as(GoogleCloudOptions).project = project

  bq_options = options.view_as(BqExportOptions)

  p = beam.Pipeline(options=options)

  entities = (
      p
      | 'ReadFromDatastore(Anomaly)' >> ReadTimestampRangeFromDatastore(
          {
              'project': project,
              'kind': 'Anomaly'
          },
          time_range_provider=bq_options.GetTimeRangeProvider()))

  anomaly_dicts = (
      entities
      | 'ConvertEntityToRow(Anomaly)' >>
      beam.FlatMap(AnomalyEntityToRowDict).with_output_types(AnomalyRow))

  _ = (
      anomaly_dicts
      | 'WriteToSpanner' >> SpannerInsertOrUpdate(
          project_id=project_spanner,
          instance_id=args.instance,
          database_id=args.database,
          table=args.table))

  result = p.run()
  result.wait_until_finish()
  PrintCounters(result)


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  main()

# Experimental.
# Verified using
# PYTHONPATH=./dashboard/bq_export \
# python3 dashboard/bq_export/bq_export/spanner_dash.py \
# --instance=tfgen-spanid-20250415224933743     --database=mordeckimarcin_test \
# --table=anomalies     --runner=DirectRunner --end_date=yesterday --num_days=1
