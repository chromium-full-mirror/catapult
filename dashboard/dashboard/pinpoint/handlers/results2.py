# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for displaying a results2 file."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging

from flask import make_response, Response

from dashboard.common import cloud_metric
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import results2


def Results2Handler(job_id):
  try:
    job = job_module.JobFromId(job_id)
    if not job:
      raise results2.Results2Error('Error: Unknown job %s' % job_id)

    if not job.completed:
      return make_response(json.dumps({'status': 'job-incomplete'}))

    url = results2.GetCachedResults2(job)
    if url:
      logging.debug('Results2Handler: job %s complete, url: %s', job_id, url)
      return make_response(
          json.dumps({
              'status': 'complete',
              'url': url,
              'updated': job.updated.isoformat(),
          }))
    logging.debug('Results2Handler: job %s pending generation', job_id)
    if results2.ScheduleResults2Generation(job):
      return make_response(json.dumps({'status': 'pending'}))

    return make_response(json.dumps({'status': 'failed'}))

  except results2.Results2Error as e:
    return make_response(str(e), 400)


@cloud_metric.APIMetric("pinpoint", "/api/results2-serve")
def Results2ServeHandler(job_id):
  try:
    job = job_module.JobFromId(job_id)
    if not job:
      raise results2.Results2Error('Error: Unknown job %s' % job_id)

    if not job.completed:
      return make_response('Job incomplete', 404)

    html_content = results2.GetResults2FileContent(job)
    if not html_content:
      logging.error('Results2ServeHandler: content not found for job %s',
                    job_id)
      return make_response('Results not found', 404)

    logging.debug('Results2ServeHandler: serving %d bytes for job %s',
                  len(html_content), job_id)
    return Response(html_content, mimetype='text/html')

  except results2.Results2Error as e:
    return make_response(str(e), 400)
  except Exception as e:  # pylint: disable=broad-except
    logging.exception('Unexpected error in Results2ServeHandler for job %s',
                      job_id)
    return make_response('Internal Server Error: %s' % str(e), 500)


@cloud_metric.APIMetric("pinpoint", "/api/generate-results2")
def Results2GeneratorHandler(job_id):
  try:
    job = job_module.JobFromId(job_id)
    if not job:
      logging.debug('No job [%s]', job_id)
      raise results2.Results2Error('Error: Unknown job %s' % job_id)
    results2.GenerateResults2(job)
    return make_response('', 200)
  except results2.Results2Error as e:
    return make_response(str(e), 400)
