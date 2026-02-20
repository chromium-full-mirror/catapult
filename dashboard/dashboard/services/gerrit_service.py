# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions for interfacing with Gerrit, a web-based code review tool for Git.

API doc: https://gerrit-review.googlesource.com/Documentation/rest-api.html
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import urllib.parse

from dashboard.services import request

GERRIT_SCOPE = 'https://www.googleapis.com/auth/gerritcodereview'

NotFoundError = request.NotFoundError


def GetChange(server_url, change_id, fields=None):
  url = '%s/changes/%s' % (server_url, change_id)
  return request.RequestJson(url, use_auth=True, scope=GERRIT_SCOPE, o=fields)


def PostChangeComment(server_url, change_id, comment):
  url = '%s/a/changes/%s/revisions/current/review' % (server_url, change_id)
  request.Request(
      url,
      method='POST',
      body=comment,
      use_cache=False,
      use_auth=True,
      scope=GERRIT_SCOPE)


def GetCommitRevision(server_url, change_id, revision):
  """Get the commit message for a specific revision of a Gerrit change.
  More details about the API can be found at
  https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#get-commit

  Args:
    server_url: URL of the Gerrit server.
    change_id: The numeric ID of the Gerrit change.
    revision: The numeric ID of the revision (patchset) to retrieve,
                    or 'current' for the latest.

  Returns:
    The commit message for the specified revision, or an empty string if not found.
  """
  url = '%s/a/changes/%s/revisions/%s/commit' % (server_url, change_id,
                                                 revision)
  response = request.RequestJson(url, use_auth=True, scope=GERRIT_SCOPE)
  logging.debug('[TryJobPatch] GetCurrentCommit response: %s', response)
  return response.get('message', '')


def GetFileList(server_url, change_id, revision):
  """Get the list of files for a specific revision of a Gerrit change.
  More details about the API can be found at
  https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#list-files

  Args:
    server_url: URL of the Gerrit server.
    change_id: The numeric ID of the Gerrit change.
    revision: The numeric ID of the revision (patchset) to retrieve,
                    or 'current' for the latest.

  Returns:
    A dictionary mapping file paths to FileInfo entities.
  """
  url = '%s/a/changes/%s/revisions/%s/files' % (server_url, change_id, revision)
  response = request.RequestJson(url, use_auth=True, scope=GERRIT_SCOPE)
  logging.debug('[TryJobPatch] GetFileList response: %s', response)
  return response


def GetFileDiff(server_url, change_id, revision, file_id):
  """Get the diff for a specific file in a specific revision of a Gerrit change.
  More details about the API can be found at
  https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#get-file-diff

  Args:
    server_url: URL of the Gerrit server.
    change_id: The numeric ID of the Gerrit change.
    revision: The numeric ID of the revision (patchset) to retrieve,
                    or 'current' for the latest.
    file_id: The path of the file to retrieve the diff for.

  Returns:
    A list of diff content for the specified file, or an empty list if not found.
  """
  url = '%s/a/changes/%s/revisions/%s/files/%s/diff' % (
      server_url, change_id, revision, urllib.parse.quote_plus(file_id))
  response = request.RequestJson(url, use_auth=True, scope=GERRIT_SCOPE)
  logging.debug('[TryJobPatch] GetFileDiff response: %s', response)
  return response.get('content', [])
