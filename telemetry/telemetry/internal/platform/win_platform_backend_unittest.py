# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import unittest
from unittest import mock

from telemetry import decorators
from telemetry.internal.platform import win_platform_backend

class WinPlatformBackendTest(unittest.TestCase):
  @decorators.Enabled('win')
  def testTypExpectationsTagsForLaptop(self):
    backend = win_platform_backend.WinPlatformBackend()
    with mock.patch.object(backend, 'GetPcSystemType', return_value='2'):
      tags = backend.GetTypExpectationsTags()
      self.assertIn('win-laptop', tags)

  def testParseWmicDate(self):
    for raw_wmic_date, expected in [
      ('20260729102234.123456+300', '2026-07-29T10:22:34.123456+05:00'),
      ('20251210061210.234567-120', '2025-12-10T06:12:10.234567-02:00'),
      ('20240201170012.345678+0', '2024-02-01T17:00:12.345678+00:00'),
    ]:
      with self.subTest(raw_wmic_date=raw_wmic_date):
        wmic_date = win_platform_backend._ParseWmicDate(raw_wmic_date)
        self.assertEqual(wmic_date.isoformat(), expected)

  def testParseWmicDateWrongFormat(self):
    for raw_wmic_date in [
      '20261529102234.123456+300',
      'wrong_wmic_date',
    ]:
      with self.subTest(raw_wmic_date=raw_wmic_date):
        with self.assertRaises(ValueError):
          win_platform_backend._ParseWmicDate(raw_wmic_date)
