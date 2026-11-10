#!/bin/bash -x -e
# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Usage: days service_name1 service_name2 ...
# Args:
#   days[optional]: number of days from today to be deleted
#   service_name: the service name whose builds to be deleted
#
# This script is to clean up the last x days of builds that don't have
# any traffic.
#

days="$1"

# If the first argument is not a number, we will ignore it. This allows
# old calling convention to continue to work.
if [[ "${days}" =~ ^[0-9]+$ ]]; then
  shift
else
  days="28"
fi

date_to_remove=`date -I --date="-${days} day"`
project_id="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
region="${REGION:-us-central1}"
for SERVICE in "$@"; do
  versions=$(gcloud app versions list \
    --format="table[no-heading](VERSION.ID)" \
    --filter="SERVICE=${SERVICE} AND
              TRAFFIC_SPLIT=0 AND
              LAST_DEPLOYED.date()<${date_to_remove}")
  if [[ -n "${versions}" ]]; then
    echo "${versions}" | xargs --no-run-if-empty gcloud app versions delete -s "${SERVICE}"
    if [[ -n "${project_id}" ]]; then
      for version in ${versions}; do
        gcloud artifacts docker images delete \
          "${region}-docker.pkg.dev/${project_id}/gae-flexible/${SERVICE}.${version}" \
          --delete-tags --quiet || true
      done
    fi
  fi
done

