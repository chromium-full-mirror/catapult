# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
from dashboard.services import request

_CABE_HTTP_URL = 'https://cabe-http.luci.app'


def GetCabeAnalysis(job_id):
  """Returns CABE analysis for a job via HTTP REST API.
  Currently only regressions will be returned, and the response is expected to
  be in the following format:
  {
    'Benchmark': 'speedometer3',
    'Results': {
       'Charts-chartjs': {stat data}
    }
  }

  Args:
    job_id: The Pinpoint job ID.

  Returns:
    The analysis data as a dictionary, or None if the request fails.
  """
  url = '%s/getanalysis/%s' % (_CABE_HTTP_URL, job_id)
  # TODO(wenbinzhang): Add more parameters here if needed, such as alpha.
  # E.g., use_fdr_control is by default True as we want to align with the
  # default behavior of Perf-On-CQ. The default alpha in this case is 0.075.
  # However, the sandwich validation is using another CABE instance in
  # cabe.skia.org, which may have a different default alpha (0.05) and doesn't
  # use FDR control.
  params = {
      'use_fdr_control': 'True',
  }

  try:
    # use_auth=True is default in RequestJson
    return request.RequestJson(url, method='GET', **params)
  except Exception as e:  # pylint: disable=broad-except
    logging.error('Failed to get analysis from CABE HTTP for job %s: %s',
                  job_id, str(e))
    return None
