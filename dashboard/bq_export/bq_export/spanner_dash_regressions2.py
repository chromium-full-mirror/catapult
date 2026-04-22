# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export chromeperf dash data to reg2 Spanner with Beam & Cloud Dataflow."""

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
from apache_beam.io.gcp.spanner import SpannerInsert

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
  from datetime import datetime
  if isinstance(obj, datetime):
    return obj.isoformat()
  return str(obj)


def _SafeFloat(val):
  if val is None or val == '':
    return None
  return float(val)


def _SafeInt(val):
  if val is None or val == '':
    return None
  return int(val)


class Regressions2Row(NamedTuple):
  commit_number: Optional[int]
  prev_commit_number: Optional[int]
  alert_id: Optional[int]
  creation_time: Optional[Timestamp]
  median_before: Optional[float]
  median_after: Optional[float]
  is_improvement: Optional[bool]
  cluster_type: Optional[str]
  cluster_summary: Optional[str]
  frame: Optional[str]
  triage_status: Optional[str]
  triage_message: Optional[str]
  bug_id: Optional[int]
  sub_name: Optional[str]
  trace_id: Optional[bytes]


coders.registry.register_coder(Regressions2Row, coders.RowCoder)


# source of truth: dashboard/skia_export/skia_export/skia_pipeline.py
# copied it not to bother with relative imports.
V8_MASTERS = [
    'internal.client.v8',
    'client.v8',
    'client.v8.perf',
]


def getClusterType(entity):
  improvement_direction = entity.get('improvement_direction')
  up = improvement_direction == 'up'
  down = improvement_direction == 'down'
  is_improvement = bool(entity.get('is_improvement', False))
  if (up and is_improvement) or (down and not is_improvement):
    return 'high'
  if (down and is_improvement) or (up and not is_improvement):
    return 'low'
  return None


def Regressions2EntityToRowDict(entity, master_list):
  entities_read.inc()
  try:
    test_path = ''
    parts = []
    if 'test' in entity:
      test_path = TestPath(entity['test'])
      parts = test_path.split('/')

    if master_list:
      if 'test' not in entity:
        return []
      master = parts[0] if len(parts) > 0 else None
      if master not in master_list:
        return []

    # will have to be populated later.
    alert_id = None

    sub_names = entity.get('subscription_names', [])
    sub_name_str = None
    if isinstance(sub_names, list) and len(sub_names) > 0:
      sub_name_str = str(sub_names[0])
    elif isinstance(sub_names, str) and sub_names:
      try:
        loaded = json.loads(sub_names)
        if loaded and isinstance(loaded, list):
          sub_name_str = str(loaded[0])
        else:
          sub_name_str = str(sub_names)
      except Exception:
        sub_name_str = str(sub_names)
    bug_id = _SafeInt(entity.get('bug_id'))

    cluster_type = getClusterType(entity)

    mapped_fields = {
        'alert_id':
            alert_id,
        'commit_number':
            _SafeInt(entity.get('end_revision')),
        'prev_commit_number':
            _SafeInt(entity.get('start_revision')),
        'creation_time':
            Timestamp(entity['timestamp'].timestamp())
            if 'timestamp' in entity else None,
        'median_before':
            _SafeFloat(entity.get('median_before_anomaly')),
        'median_after':
            _SafeFloat(entity.get('median_after_anomaly')),
        'is_improvement':
            bool(entity.get('is_improvement', False)),
        'cluster_type':
            cluster_type,
        'triage_status':
            str(entity.get('state')) if entity.get('state') else
            'triaged' if bug_id is not None else 'untriaged',
        'triage_message':
            None,
        'bug_id':
            bug_id,
        'sub_name':
            sub_name_str,
        'trace_id':
            None,
    }

    # Get unmapped fields for frame extras
    used_keys = {
        'timestamp', 'end_revision', 'start_revision', 'median_before_anomaly',
        'median_after_anomaly', 'is_improvement', 'state', 'bug_id',
        'subscription_names'
    }
    all_keys = set(entity.keys())

    extras = {}
    for k in all_keys - used_keys:
      extras[k] = entity.get(k)

    paramset = {}
    if 'test' in entity:
      if len(parts) > 0:
        paramset["master"] = [parts[0]]
      if len(parts) > 1:
        paramset["bot"] = [parts[1]]
      if len(parts) > 2:
        paramset["benchmark"] = [parts[2]]
      paramset["test"] = [test_path]
      for i, p in enumerate(parts[3:]):
        paramset[f"subtest_{i+1}"] = [p]
    if 'statistic' in entity:
      paramset["stat"] = [entity.get('statistic')]
    if 'units' in entity:
      paramset["unit"] = [entity.get('units')]

    header = []
    end_rev = mapped_fields.get('commit_number')
    if end_rev is not None:
      header.append({"offset": end_rev})

    traceset_parts = []
    for k in sorted(paramset.keys()):
      if paramset[k]:
        traceset_parts.append(f"{k}={paramset[k][0]}")

    traceset = "," + ",".join(traceset_parts) + "," if traceset_parts else ","

    frame = {
        "msg": "",
        "skps": [],
        "dataframe": {
            "skip": 0,
            "header": header
        },
        "paramset": paramset,
        "traceset": {
            traceset: None
        },
        "traceMetadata": None,  # seems to always be null
        "anomalymap": None,  # no idea why it should be here
        "display_mode": None,  # no clue what it is
        "extras": extras
    }
    mapped_fields['frame'] = json.dumps(frame, default=_JsonFallback)

    # build a simple cluster_summary
    cluster_summary = {
        "num": 1,
        "step_point": {
            "offset": mapped_fields.get('commit_number')
        },
        "param_summaries2": []
    }

    # Not sure if that's how percents work.
    if 'test' in entity:
      if len(parts) > 0:
        cluster_summary["param_summaries2"].append({
            "value": f"master={parts[0]}",
            "percent": 100
        })
      if len(parts) > 1:
        cluster_summary["param_summaries2"].append({
            "value": f"bot={parts[1]}",
            "percent": 100
        })
      if len(parts) > 2:
        cluster_summary["param_summaries2"].append({
            "value": f"benchmark={parts[2]}",
            "percent": 100
        })
      cluster_summary["param_summaries2"].append({
          "value": f"test={test_path}",
          "percent": 100
      })

    if 'statistic' in entity:
      cluster_summary["param_summaries2"].append({
          "value": f"stat={entity.get('statistic')}",
          "percent": 100
      })

    mapped_fields['cluster_summary'] = json.dumps(
        cluster_summary, default=_JsonFallback)

    return [Regressions2Row(**mapped_fields)]
  except Exception as e:
    failed_entity_transforms.inc()
    key_id = getattr(getattr(entity, 'key', None), 'id', 'unknown')
    logging.error('Failed to convert entity %s: %s', key_id, e)
    return []


def main():
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--instance', required=True)
  parser.add_argument('--database', required=True)
  parser.add_argument('--table', default='regressions2')
  parser.add_argument('--master', default='')

  args, beam_args = parser.parse_known_args()

  project = 'chromeperf'
  project_spanner = 'skia-infra-corp'
  options = PipelineOptions(beam_args)
  options.view_as(GoogleCloudOptions).project = project

  masters = []
  # we cannot pass argument "master" directly, since turquoise and
  # fuchsia masters are separate.
  # Assigning masters this way provides more verbosity.
  if args.master == 'v8':
    masters = V8_MASTERS

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
      | 'ConvertEntityToRow(Regressions2)' >> beam.FlatMap(
          Regressions2EntityToRowDict,
          master_list=masters).with_output_types(Regressions2Row))

  _ = (
      anomaly_dicts
      | 'WriteToSpanner' >> SpannerInsert(
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
# /tmp/python/bin/python \
# dashboard/bq_export/bq_export/spanner_dash_regressions2.py \
# --instance=tfgen-spanid-20250415224933743     --database=mordeckimarcin_test \
# --table=regressions2     --runner=DirectRunner --end_date=yesterday \
# --num_days=1 --master=v8
