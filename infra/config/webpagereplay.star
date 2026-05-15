# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI configuration for webpagereplay.

After modifying this file execute main.star ('infra/config/main.star')
to regenerate the configs. This is also enforced by PRESUBMIT.py script.
"""

luci.cq_group(
    name = "webpagereplay",
    watch = cq.refset(
        repo = "https://chromium.googlesource.com/webpagereplay",
        refs = ["refs/heads/.+"],
    ),
    retry_config = cq.retry_config(
        single_quota = 1,
        global_quota = 2,
        failure_weight = 1,
        transient_failure_weight = 1,
        timeout_weight = 2,
    ),
)

luci.builder(
    name = "webpagereplay-linux-presubmit",
    bucket = "try",
    executable = luci.recipe(
        name = "run_presubmit",
        cipd_package = "infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build",
        use_bbagent = True,
    ),
    build_numbers = True,
    dimensions = {
        "pool": "luci.flex.try",
        "os": "Ubuntu-24.04",
        "cpu": "x86-64",
    },
    execution_timeout = 2 * time.hour,
    service_account = "catapult-try-builder@chops-service-accounts.iam.gserviceaccount.com",
    properties = {
        "$kitchen": {"devshell": True, "git_auth": True},
        "repo_name": "webpagereplay",
    },
)

luci.cq_tryjob_verifier(
    builder = "webpagereplay-linux-presubmit",
    cq_group = "webpagereplay",
    disable_reuse = True,
)

luci.cq_tryjob_verifier(
    builder = "Catapult Linux Tryserver",
    cq_group = "webpagereplay",
)
