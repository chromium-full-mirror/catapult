# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
r"""Export chromeperf PageState entities to Spanner with Beam & Cloud Dataflow.

Example command line to start a Dataflow job:

  $ SVC_ACCT=bigquery-exporter@chromeperf.iam.gserviceaccount.com
  $ python bq_export/export_page_state_spanner.py \
        --service_account_email=$SVC_ACCT \
        --runner=DataflowRunner \
        --region=us-central1 \
        --temp_location=gs://chromeperf-dataflow-temp/ \
        --setup_file=bq_export/setup.py \
        --max_num_workers=60 \
        --num_workers=10 \
        --instance=tfgen-spanid-20250415224933743 \
        --database=mordeckimarcin_test \
        --table=page_states
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from bq_export import spanner_dash_page_state

if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  spanner_dash_page_state.main()
