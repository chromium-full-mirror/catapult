# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import signal
import unittest
from unittest import mock

from devil.utils import signal_handler


class SignalHandlerTest(unittest.TestCase):

  def testSignalHandler_normal(self):
    called = False

    def dummy_handler(_sig, _frame):
      nonlocal called
      called = True

    with signal_handler.SignalHandler(signal.SIGTERM, dummy_handler):
      current = signal.getsignal(signal.SIGTERM)
      self.assertEqual(current, dummy_handler)
      current(signal.SIGTERM, None)
    self.assertTrue(called)

  def testSignalHandler_whenGetsignalReturnsNone(self):
    dummy_handler = lambda _sig, _frame: None
    with mock.patch('signal.getsignal', return_value=None):
      with mock.patch('signal.signal') as mock_signal:
        with signal_handler.SignalHandler(signal.SIGTERM, dummy_handler):
          pass
        mock_signal.assert_called_with(signal.SIGTERM, signal.SIG_DFL)
        self.assertTrue(mock_signal.called)

  def testAddSignalHandler_normal(self):
    called = False

    def dummy_handler(_sig, _frame):
      nonlocal called
      called = True

    with signal_handler.AddSignalHandler(signal.SIGTERM, dummy_handler):
      current = signal.getsignal(signal.SIGTERM)
      self.assertTrue(callable(current))
      current(signal.SIGTERM, None)
    self.assertTrue(called)

  def testAddSignalHandler_whenGetsignalReturnsNone(self):
    dummy_handler = lambda _sig, _frame: None
    with mock.patch('signal.getsignal', return_value=None):
      with mock.patch('signal.signal') as mock_signal:
        with signal_handler.AddSignalHandler(signal.SIGTERM, dummy_handler):
          pass
        mock_signal.assert_called_with(signal.SIGTERM, signal.SIG_DFL)
        self.assertTrue(mock_signal.called)

  def testAddSignalHandler_executesAdditionalHandlerWhenExistingIsNone(self):
    called = False

    def additional_handler(_sig, _frame):
      nonlocal called
      called = True

    with mock.patch('signal.getsignal', return_value=None):
      with mock.patch('signal.signal') as mock_signal:
        with signal_handler.AddSignalHandler(signal.SIGTERM,
                                             additional_handler):
          installed_handler = mock_signal.call_args[0][1]
          installed_handler(signal.SIGTERM, None)
    self.assertTrue(called)


if __name__ == '__main__':
  unittest.main()
