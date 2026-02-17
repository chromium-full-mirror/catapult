# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
if not hasattr(collections, 'Mapping'):
  import collections.abc
  collections.Mapping = collections.abc.Mapping
  collections.MutableMapping = collections.abc.MutableMapping

from unittest import mock
import unittest
import json

from application.clients import sheriff_config_client

class SheriffConfigClientTest(unittest.TestCase):

  @mock.patch('requests.post')
  @mock.patch('application.clients.sheriff_config_client.SheriffConfigClient._InitAuthHeaders')
  def testMatchEmpty(self, mock_init_auth, mock_post):
    mock_init_auth.return_value = None
    client = sheriff_config_client.SheriffConfigClient()
    client.auth_header = {}

    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = '{}'
    mock_response.ok = True
    mock_post.return_value = mock_response

    matched_configs, err_msg = client.Match('some/path')
    self.assertEqual(matched_configs, [])
    self.assertIsNone(err_msg)

  @mock.patch('requests.post')
  @mock.patch('application.clients.sheriff_config_client.SheriffConfigClient._InitAuthHeaders')
  def testMatch404(self, mock_init_auth, mock_post):
    mock_init_auth.return_value = None
    client = sheriff_config_client.SheriffConfigClient()
    client.auth_header = {}

    mock_response = mock.Mock()
    mock_response.status_code = 404
    mock_response.text = 'Not Found'
    mock_response.ok = False
    mock_post.return_value = mock_response

    matched_configs, err_msg = client.Match('some/path')
    self.assertEqual(matched_configs, [])
    self.assertIsNone(err_msg)

  @mock.patch('requests.post')
  @mock.patch('application.clients.sheriff_config_client.SheriffConfigClient._InitAuthHeaders')
  def testMatchSuccess(self, mock_init_auth, mock_post):
    mock_init_auth.return_value = None
    client = sheriff_config_client.SheriffConfigClient()
    client.auth_header = {}

    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = '{"subscriptions": [{"name": "sub1"}]}'
    mock_response.content = b'{"subscriptions": [{"name": "sub1"}]}'
    mock_response.ok = True
    mock_post.return_value = mock_response

    matched_configs, err_msg = client.Match('some/path')
    self.assertEqual(matched_configs, [{"name": "sub1"}])
    self.assertIsNone(err_msg)
