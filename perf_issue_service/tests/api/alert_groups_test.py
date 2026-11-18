# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
# Root vpython.toml pins jinja2==2.10.1 on Python 3.11, which still imports
# Mapping ABCs from collections instead of collections.abc.
if not hasattr(collections, 'Mapping'):
  import collections.abc
  collections.Mapping = collections.abc.Mapping
  collections.MutableMapping = collections.abc.MutableMapping

import json
import unittest
from unittest import mock

import flask

from application.app import create_app
from models import alert_group

_EXPECTED_CSP = "default-src 'none'; frame-ancestors 'none'"


class AlertGroupsTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.app = create_app()
    self.client = self.app.test_client()
    auth_patcher = mock.patch('application.utils.AuthorizeBearerToken',
                              return_value=True)
    auth_patcher.start()
    self.addCleanup(auth_patcher.stop)

  def _AssertSecurityHeaders(self, response):
    self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
    self.assertEqual(response.headers.get('Content-Security-Policy'),
                     _EXPECTED_CSP)

  @mock.patch.object(alert_group.AlertGroup, 'ds_client')
  def testGetAnomaliesMissingGroupReturnsPlainText404(self, mock_ds_client):
    mock_ds_client.AlertGroupKey.return_value = 'missing_key'
    mock_ds_client.GetEntityByKey.return_value = None

    response = self.client.get(
        '/alert_groups/%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E/anomalies')

    self.assertEqual(response.status_code, 404)
    self.assertEqual(response.mimetype, 'text/plain')
    self.assertEqual(response.headers.get('Content-Type'),
                     'text/plain; charset=utf-8')
    self._AssertSecurityHeaders(response)
    self.assertEqual(
        response.get_data(as_text=True),
        'No Alert Group Found with id: <img src=x onerror=alert(1)>')
    mock_ds_client.AlertGroupKey.assert_called_once_with(
        '<img src=x onerror=alert(1)>')

  @mock.patch.object(alert_group.AlertGroup, 'ds_client')
  def testGetAnomaliesReturnsJsonList(self, mock_ds_client):
    anomaly_1 = mock.Mock(id=101)
    anomaly_2 = mock.Mock(id=102)
    mock_ds_client.AlertGroupKey.return_value = 'group_key'
    mock_ds_client.GetEntityByKey.return_value = {
        'anomalies': [anomaly_1, anomaly_2]
    }

    response = self.client.get('/alert_groups/12345/anomalies')

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.mimetype, 'application/json')
    self._AssertSecurityHeaders(response)
    self.assertEqual(json.loads(response.get_data(as_text=True)), [101, 102])
    mock_ds_client.AlertGroupKey.assert_called_once_with(12345)

  @mock.patch.object(alert_group.AlertGroup, 'FindCanonicalGroupByIssue')
  def testFindCanonicalGroupReturnsJsonDict(self, mock_find_canonical):
    mock_find_canonical.return_value = 'abc'

    response = self.client.get(
        '/alert_groups/group-1/canonical/issue_id/999/project_name/chromium')

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.mimetype, 'application/json')
    self._AssertSecurityHeaders(response)
    self.assertEqual(json.loads(response.get_data(as_text=True)),
                     {'key': 'abc'})

  def testUnmatchedRouteCoercesHttpExceptionToPlainText(self):
    response = self.client.get('/nonexistent_route/<script>alert(1)</script>')

    self.assertEqual(response.status_code, 404)
    self.assertEqual(response.mimetype, 'text/plain')
    self.assertEqual(response.headers.get('Content-Type'),
                     'text/plain; charset=utf-8')
    self._AssertSecurityHeaders(response)

  def testDirectMakeResponseStringHardening(self):
    with self.app.app_context():
      response = flask.make_response('raw error', 400)

    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.mimetype, 'text/plain')
    self.assertEqual(response.headers.get('Content-Type'),
                     'text/plain; charset=utf-8')
    self._AssertSecurityHeaders(response)


if __name__ == '__main__':
  unittest.main()
