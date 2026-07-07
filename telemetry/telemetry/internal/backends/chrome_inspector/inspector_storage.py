# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from telemetry.core import exceptions


class InspectorStorage():
  def __init__(self, inspector_websocket):
    self._websocket = inspector_websocket

  def ClearDataForOrigin(self, url, timeout):
    res = self._websocket.SyncRequest(
        {'method': 'Storage.clearDataForOrigin',
         'params': {
             'origin': url,
             'storageTypes': 'all',
         }}, timeout)
    if 'error' in res:
      raise exceptions.StoryActionError(res['error']['message'])
