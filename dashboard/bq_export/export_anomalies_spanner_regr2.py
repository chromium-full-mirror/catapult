# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
r"""Export chromeperf anomalies to Spanner with Beam & Cloud Dataflow.

Example command line to start a Dataflow job that transfers 365 anomalies:

  $ SVC_ACCT=bigquery-exporter@chromeperf.iam.gserviceaccount.com
  $ python bq_export/export_anomalies_spanner_regr2.py \
        --service_account_email=$SVC_ACCT \
        --runner=DataflowRunner \
        --region=us-central1 \
        --temp_location=gs://chromeperf-dataflow-temp/ \
        --setup_file=bq_export/setup.py \
        --max_num_workers=60 \
        --num_workers=10 \
        --instance=tfgen-spanid-20250415224933743 \
        --database=mordeckimarcin_test \
        --table=regressions2 \
        --end_date=yesterday \
        --num_days=365 \
        --master=v8
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from bq_export import spanner_dash_regressions2

if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  spanner_dash_regressions2.main()
