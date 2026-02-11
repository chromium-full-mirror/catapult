# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for displaying a results2 file."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging

from flask import make_response, Response, request

from dashboard.api import api_auth
from dashboard.api import api_request_handler
from dashboard.common import cloud_metric
from dashboard.common import datastore_hooks
from dashboard.common import utils
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import results2


def _CheckUser():
  if utils.IsDevAppserver():
    return

  # We shouldn't use api_auth.Authorize() here because strictly enforces OAuth
  # client IDs which might not match if we are using query-param tokens or
  # cookies. Instead, we just check that the user is logged in and authorized.
  try:
    email = utils.GetEmail()
    if not email:
      logging.info('No user email found for request to results2-serve.')
      raise api_auth.NotLoggedInError
  except utils.oauth.OAuthRequestError as e:
    # Transient errors when checking the token result should result in HTTP 500
    logging.exception(
        'OAuthRequestError when checking user for results2-serve.')
    raise api_auth.OAuthError from e

  logging.info('Authenticated user: %s for results2-serve.', email)
  if not utils.IsTryjobUser():
    logging.warning(
        'User %s is not authorized for results2-serve (not a tryjob user).',
        email)
    raise api_request_handler.ForbiddenError()

  if utils.IsInternalUser():
    datastore_hooks.SetPrivilegedRequest()


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
    if request.args.get('access_token'):
      _CheckUser()
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

  except api_auth.NotLoggedInError as e:
    return make_response(str(e), 401)
  except api_auth.OAuthError as e:
    return make_response(str(e), 403)
  except api_request_handler.ForbiddenError as e:
    return make_response(str(e), 403)
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
