# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import unittest
from unittest import mock

from telemetry import decorators
from telemetry.internal.platform import win_platform_backend

class WinPlatformBackendTest(unittest.TestCase):

  def testGetSystemProcessInfo(self):
    backend = win_platform_backend.WinPlatformBackend()
    processes = [
        mock.Mock(
            info={
                'pid':
                    1,
                'ppid':
                    0,
                'name':
                    'browser.exe',
                'create_time':
                    10.5,
                'cmdline': [
                    r'C:\Program Files\Browser\browser.exe',
                    '--type=renderer',
                ],
            }),
        mock.Mock(
            info={
                'pid': 2,
                'ppid': 1,
                'name': None,
                'create_time': None,
                'cmdline': None,
            }),
    ]

    with mock.patch.object(win_platform_backend.psutil,
                           'process_iter',
                           return_value=processes) as process_iter:
      process_info = backend.GetSystemProcessInfo()

    self.assertEqual(process_info, [
        {
            'ProcessId':
                1,
            'ParentProcessId':
                0,
            'Name':
                'browser.exe',
            'CreationDate':
                10.5,
            'CommandLine':
                (r'"C:\Program Files\Browser\browser.exe" --type=renderer'),
        },
        {
            'ProcessId': 2,
            'ParentProcessId': 1,
            'Name': None,
            'CreationDate': None,
            'CommandLine': None,
        },
    ])
    process_iter.assert_called_once_with(
        attrs=['pid', 'ppid', 'name', 'create_time', 'cmdline'], ad_value=None)

  @decorators.Enabled('win')
  def testTypExpectationsTagsForLaptop(self):
    backend = win_platform_backend.WinPlatformBackend()
    with mock.patch.object(backend, 'GetPcSystemType', return_value='2'):
      tags = backend.GetTypExpectationsTags()
      self.assertIn('win-laptop', tags)
