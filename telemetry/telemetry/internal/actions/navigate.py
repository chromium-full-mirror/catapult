# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import time

from telemetry.internal.actions import page_action


class NavigateAction(page_action.PageAction):

  def __init__(self, url, script_to_evaluate_on_commit=None,
               timeout_in_seconds=page_action.DEFAULT_TIMEOUT):
    super().__init__(timeout=timeout_in_seconds)
    assert url, 'Must specify url for navigate action'
    self._url = url
    self._script_to_evaluate_on_commit = script_to_evaluate_on_commit

  def _GetTimeLeftInSeconds(self, start_time):
    time_left = start_time + self.timeout - time.time()
    return max(0, time_left)

  def RunAction(self, tab):
    start_time = time.time()
    tab.Navigate(self._url, self._script_to_evaluate_on_commit,
                 self.timeout)

    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter(
        self._GetTimeLeftInSeconds(start_time))
    tab.WaitForFrameToBeDisplayed(
        timeout=self._GetTimeLeftInSeconds(start_time))

  def __str__(self):
    return "%s(%s)" % (self.__class__.__name__, self._url)
