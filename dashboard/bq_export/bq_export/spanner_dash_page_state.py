# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Export PageState data from Datastore to
Spanner with Beam & Cloud Dataflow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
from typing import NamedTuple, List, Optional
import apache_beam as beam
from apache_beam import coders
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.metrics import Metrics
from apache_beam.io.gcp.spanner import SpannerInsertOrUpdate
from apache_beam.io.gcp.datastore.v1new import datastoreio
from apache_beam.io.gcp.datastore.v1new.types import Query

entities_read = Metrics.counter('main', 'entities_read')
failed_entity_transforms = Metrics.counter('main', 'failed_entity_transforms')


class PageStateRow(NamedTuple):
  sid: str
  anomaly_ids: List[int]
  is_legacy: bool


coders.registry.register_coder(PageStateRow, coders.RowCoder)


def _ExtractIds(data):
  """Helper function to recursively extract
  anomaly IDs from various forms of data."""
  if data is None:
    return []
  if isinstance(data, int):
    return [data]
  if isinstance(data, str):
    # Try simple integer parsing first
    try:
      return [int(data)]
    except ValueError:
      pass
    # Try legacy urlsafe decoding
    try:
      from google.cloud.datastore.key import Key
      k = Key.from_legacy_urlsafe(data)
      if k.kind == 'Anomaly' and k.id:
        return [k.id]
    except Exception:
      pass
    # Try comma split
    if ',' in data:
      parts = data.split(',')
      res = []
      for part in parts:
        res.extend(_ExtractIds(part.strip()))
      return res
    return []
  if isinstance(data, list):
    res = []
    for item in data:
      res.extend(_ExtractIds(item))
    return res
  if isinstance(data, dict):
    res = []
    for v in data.values():
      res.extend(_ExtractIds(v))
    return res
  return []


def _IsValidAlertKeysList(loaded):
  if not isinstance(loaded, list):
    return False
  if not loaded:
    return False
  from google.cloud.datastore.key import Key
  for item in loaded:
    if not isinstance(item, str):
      return False
    try:
      k = Key.from_legacy_urlsafe(item)
      if k.kind != 'Anomaly' or not k.id:
        return False
    except Exception:
      return False
  return True


def PageStateEntityToRowDict(entity):
  entities_read.inc()
  try:
    client_entity = entity.to_client_entity()
    state_id = client_entity.key.name or str(client_entity.key.id)

    val = client_entity.get('value_v2') or client_entity.get('value')
    if val is None:
      return []

    if isinstance(val, bytes):
      val_str = val.decode('utf-8', errors='replace')
    else:
      val_str = str(val)

    try:
      loaded = json.loads(val_str)
    except (ValueError, TypeError):
      return []

    if not _IsValidAlertKeysList(loaded):
      return []

    anomaly_ids = _ExtractIds(loaded)

    # Deduplicate IDs
    unique_ids = list(set(anomaly_ids))
    if unique_ids == []:
      return []

    return [
        PageStateRow(
            sid="\\x" + state_id, anomaly_ids=unique_ids, is_legacy=True)
    ]
  except Exception as e:
    failed_entity_transforms.inc()
    logging.error('Failed to convert PageState entity: %s', e)
    return []


def main():
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--instance', required=True)
  parser.add_argument('--database', required=True)
  parser.add_argument('--table', default='page_states')

  args, beam_args = parser.parse_known_args()

  project = 'chromeperf'
  project_spanner = 'skia-infra-corp'
  options = PipelineOptions(beam_args)
  options.view_as(GoogleCloudOptions).project = project

  p = beam.Pipeline(options=options)

  entities = (
      p
      | 'ReadFromDatastore(PageState)' >> datastoreio.ReadFromDatastore(
          query=Query(kind='PageState', project=project)))

  rows = (
      entities
      | 'ConvertEntityToRow(PageState)' >>
      beam.FlatMap(PageStateEntityToRowDict).with_output_types(PageStateRow))

  _ = (
      rows
      | 'WriteToSpanner(PageState)' >> SpannerInsertOrUpdate(
          project_id=project_spanner,
          instance_id=args.instance,
          database_id=args.database,
          table=args.table))

  result = p.run()
  result.wait_until_finish()


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  main()
