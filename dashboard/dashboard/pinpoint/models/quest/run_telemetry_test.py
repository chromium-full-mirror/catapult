# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Quest for running a Telemetry benchmark in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

from dashboard.pinpoint.models.quest import run_performance_test
from dashboard.services import crrev_service

_DEFAULT_EXTRA_ARGS = [
    '-v', '--upload-results', '--output-format', 'histograms'
]

_STORY_REGEX = re.compile(r'[^a-zA-Z0-9]')

_MAX_STRING_LENGTH = 200

# crbug/1146949
# Please keep this executable-argument mapping synced with perf waterfall:
#  https://chromium.googlesource.com/chromium/src/+/main/tools/perf/core/bot_platforms.py
_WATERFALL_ENABLED_GTEST_NAMES = {
    'base_perftests': [
        '--test-launcher-jobs=1', '--test-launcher-retry-limit=0'
    ],
    'components_perftests': ['--xvfb'],
    'dawn_perf_tests': [
        '--test-launcher-jobs=1', '--test-launcher-retry-limit=0'
    ],
    'gpu_perftests': [],
    'load_library_perf_tests': [],
    'performance_browser_tests': [
        '--full-performance-run',
        '--test-launcher-jobs=1',
        '--test-launcher-retry-limit=0',
        # Allow the full performance runs to take up to 60 seconds (rather
        # than the default of 30 for normal CQ browser test runs).
        '--ui-test-action-timeout=60000',
        '--ui-test-action-max-timeout=60000',
        '--test-launcher-timeout=60000',
        '--gtest_filter=*/TabCapturePerformanceTest.*:'
        '*/CastV2PerformanceTest.*',
    ],
    'sync_performance_tests': [
        '--test-launcher-jobs=1', '--test-launcher-retry-limit=0'
    ],
    'tracing_perftests': [],
    'views_perftests': ['--xvfb']
}

# GTEST_EXECUTABLE_NAME is based on the following link:
# https://source.chromium.org/chromium/chromium/src/+/main:tools/perf/core/bot_platforms.py;l=282
GTEST_EXECUTABLE_NAME = {
    'base_perftests': 'base_perftests',
    'components_perftests': 'components_perftests',
    'dawn_perf_tests': 'dawn_perf_tests',
    'gpu_perftests': 'gpu_perftests',
    'load_library_perf_tests': 'load_library_perf_tests',
    'performance_browser_tests': 'browser_tests',
    'sync_performance_tests': 'sync_performance_tests',
    'tracing_perftests': 'tracing_perftests',
    'views_perftests': 'views_perftests'
}

_CROSSBENCH_NAME = {
    # ODML
    'blink-ai.crossbench': 'blink-ai',
    # Jetstream
    'jetstream2.crossbench': 'jetstream_2',
    'jetstream2.0.crossbench': 'jetstream_2.0',
    'jetstream2.1.crossbench': 'jetstream_2.1',
    'jetstream2.2.crossbench': 'jetstream_2.2',
    'jetstream3.crossbench': 'jetstream_3',
    'jetstream3.0.crossbench': 'jetstream_3.0',
    'jetstream-main.crossbench': 'jetstream_main',
    # Motionmark
    'motionmark1.0.crossbench': 'motionmark_1.0',
    'motionmark1.1.crossbench': 'motionmark_1.1',
    'motionmark1.2.crossbench': 'motionmark_1.2',
    'motionmark1.3.crossbench': 'motionmark_1.3',
    'motionmark1.3.1.crossbench': 'motionmark_1.3.1',
    # Speedmeter
    'speedometer2.crossbench': 'speedometer_2',
    'speedometer2.0.crossbench': 'speedometer_2.0',
    'speedometer2.1.crossbench': 'speedometer_2.1',
    'speedometer3.crossbench': 'speedometer_3',
    'speedometer3.a11y.crossbench': 'speedometer_3',
    'speedometer3.0.crossbench': 'speedometer_3.0',
    'speedometer3.1.crossbench': 'speedometer_3.1',
    'speedometer-main.crossbench': 'speedometer_main',
    # Loadline
    'loadline_phone.crossbench': 'loadline-phone-fast',
    'loadline2_phone.crossbench': 'loadline2-phone',
    'loadline2_tablet.crossbench': 'loadline2-tablet',
    'loadline_tablet.crossbench': 'loadline-tablet-fast',
    # Embedder
    'embedder.crossbench': 'embedder',
    'gma.embedder.crossbench': 'embedder',
    'shell.embedder.crossbench': 'embedder',
    # Loading
    'loading.crossbench': 'loading',
    # webai.crossbench
    'webai.crossbench': 'webai',
    # devtools_frontend.crossbench
    'devtools_frontend.crossbench': 'devtools_frontend',
}

# These hardcoded args are only used while running benchmarks before commit
# position 1614510. Newer versions of run_performance_tests.py read the args
# from shard map.
# pylint: disable=line-too-long
_CROSSBENCH_EXTRA_ARGS = {
    'embedder.crossbench': (
        '--wpr=crossbench_android_embedder_000.wprgo',
        '--skip-wpr-script-injection',
        '--embedder=../../clank/android_webview/tools/crossbench_config/cipd/arm64/Velvet_arm64.apk',
        '--splashscreen=skip',
        '--cuj-config=../../third_party/crossbench/config/team/woa/embedder_cuj_config.hjson',
        '--probe-config=../../clank/android_webview/tools/crossbench_config/agsa_probe_config.hjson',
        '--repetitions=50',
        '--cool-down-threshold=moderate',
        '--http-request-timeout=2s',
        '--ignore-partial-failures',
        '--embedder-process-name=googleapp',
        '--embedder-setup-command-config=../../clank/android_webview/tools/crossbench_config/agsa_setup_config.hjson',
        '--embedder-drop-caches',
    ),
    'gma.embedder.crossbench': (
        '--wpr=crossbench_android_gma_embedder_000.wprgo',
        '--wpr-http-port=8080',
        '--wpr-https-port=8081',
        '--embedder=../../clank/android_webview/tools/crossbench_config/cipd/arm64/webview_test_app_binary.apk',
        '--splashscreen=skip',
        '--cuj-config=../../third_party/crossbench/config/team/woa/gma_interstitial_cuj_config.hjson',
        '--skip-wpr-script-injection',
        '--repetitions=50',
        '--cool-down-threshold=moderate',
        '--embedder-setup-command-config=../../third_party/crossbench/config/team/woa/gma_device_setup.hjson',
        '--embedder-teardown-command-config=../../third_party/crossbench/config/team/woa/gma_device_teardown.hjson',
        '--probe-config=../../third_party/crossbench/config/team/woa/gma_wv_latency.probe.config.hjson',
        '--ignore-partial-failures',
        '--android-activity=MainActivity',
        '--android-action=',
        '--embedder-push-files=/b/swarming/w/ir/third_party/crossbench/config/team/woa/hosts:/data/local/tmp/hosts',
        '--embedder-push-files=/b/swarming/w/ir/third_party/crossbench/config/team/woa/dnsmasq.conf:/data/local/tmp/dnsmasq.conf',
        '--embedder-push-files=/b/swarming/w/ir/clank/android_webview/tools/crossbench_config/cipd/arm64/dummy_vpn.apk:/data/local/tmp/dummy_vpn.apk',
    ),
    'shell.embedder.crossbench': (
        '--wpr=crossbench_android_loading_000.wprgo',
        '--embedder=webview_embedder',
        '--splashscreen=skip',
        '--probe-config=../../third_party/crossbench/config/team/woa/wv_shell_memory.probe.config.hjson',
        '--cuj-config=../../third_party/crossbench/config/team/woa/staggered_wv_startup_cuj_config.hjson',
        '--android-activity=ManuallyTriggeredStartupActivity',
        '--repetitions=50',
        '--cool-down-threshold=moderate',
    ),
    'loading.crossbench': (
        '--wpr=crossbench_android_loading_000.wprgo',
        '--probe=chrome_histograms:{"baseline":false,"metrics":{"Android.WebView.Startup.CreationTime.StartChromiumLocked":["mean"],"Android.WebView.Startup.CreationTime.Stage1.FactoryInit":["mean"],"PageLoad.PaintTiming.NavigationToFirstContentfulPaint":["mean"]}}',
        '--repetitions=50',
        '--cool-down-threshold=moderate',
        '--stories=cnn',
    ),
    'speedometer3.a11y.crossbench':
        ('--extra-browser-args=--force-renderer-accessibility',),
}
# pylint: enable=line-too-long


def _StoryToRegex(story_name):
  # Telemetry's --story-filter argument takes in a regex, not a
  # plain string. Stories can have all sorts of special characters
  # in their names (see crbug.com/983993) which would confuse a
  # regex. We thus keep only a small set of "safe chars"
  # and replace all others with match-any-character regex dots.
  return '^%s$' % _STORY_REGEX.sub('.', story_name)


def ChangeDependentArgs(args, change, configuration=None, benchmark=None):
  # For results2 to differentiate between runs, we need to add the
  # Telemetry parameter `--results-label <change>` to the runs.
  extra_args = list(args)
  extra_args += ('--results-label', str(change))
  if change.change_args:
    extra_args.extend(change.change_args)

  cl_number = 0
  if change.commits:
    commit0 = change.commits[0]
    if commit0.repository == 'chromium':
      logging.info('crbug/497884158 using chromium commit %s', commit0.git_hash)
      commit_info = crrev_service.GetCommit(commit0.git_hash)
      logging.info('crbug/497884158 commit info %s', commit_info)
      cl_number = int(commit_info.get('number', '0'))
    else:
      logging.warning(
          'crbug/497884158 main repo for change %s is %s instead of chromium',
          change, commit0.repository)
  else:
    logging.warning('crbug/497884158 change %s has no associated commits',
                    change)

  if cl_number:
    logging.info('crbug/497884158 change %s has CL number: %d', change,
                 cl_number)
  else:
    logging.warning(
        'crbug/497884158 Unable to determin CL number for change %s', change)

  if cl_number >= 1614510 and configuration:
    # On newer builds, pass in the bot config name so the test runner can load
    # extra arguments from the shard map.
    extra_args.append(f'--bot={configuration}')
  elif benchmark in _CROSSBENCH_EXTRA_ARGS:
    # On older builds, the test runner didn't know how to read the shard map,
    # so we have to give it the hardcoded extra arguments.
    extra_args += _CROSSBENCH_EXTRA_ARGS[benchmark]

  return extra_args


class RunTelemetryTest(run_performance_test.RunPerformanceTest):

  @classmethod
  def _ComputeCommand(cls, arguments):
    # We're moving the definition of which command to run here, instead of
    # relying on what's in the isolate because the 'command' feature is
    # deprecated and will be removed soon (EOY 2020).
    # TODO(dberris): Move this out to a configuration elsewhere.
    benchmark = arguments.get('benchmark')
    command = [
        'luci-auth',
        'context',
        '--',
        'vpython3',
        '../../testing/test_env.py',
        '../../testing/scripts/run_performance_tests.py',
    ]
    if benchmark in _WATERFALL_ENABLED_GTEST_NAMES:
      command.append(GTEST_EXECUTABLE_NAME[benchmark])
    elif benchmark in _CROSSBENCH_NAME:
      command.append('../../third_party/crossbench/cb.py')
    else:
      command.append('../../tools/perf/run_benchmark')
    relative_cwd = arguments.get('relative_cwd', 'out/Release')
    return relative_cwd, command

  def Start(self, change, isolate_server, isolate_hash):
    change_string = str(change)
    # If the change string is too long, truncate it to avoid
    # exceeding the swarming string length.
    if len(change_string) > _MAX_STRING_LENGTH:
      change_string = str(change)[:_MAX_STRING_LENGTH].strip()

    extra_swarming_tags = {'change': change_string}
    return self._Start(
        change,
        isolate_server,
        isolate_hash,
        ChangeDependentArgs(self._extra_args, change,
                            self._swarming_tags.get('pinpoint_configuration'),
                            self._swarming_tags.get('benchmark')),
        extra_swarming_tags,
        execution_timeout_secs=None)

  @classmethod
  def _CrossbenchExtraTestArgs(cls, benchmark, arguments):
    extra_test_args = []
    extra_test_args.append(f'--benchmark-display-name={benchmark}')
    extra_test_args.append(f'--benchmarks={_CROSSBENCH_NAME[benchmark]}')

    browser = arguments.get('browser')
    if not browser:
      raise TypeError('Missing "browser" argument for crossbench.')
    extra_test_args.append(f'--browser={browser}')

    extra_test_args += super()._ExtraTestArgs(arguments)
    return extra_test_args

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')

    if benchmark in _CROSSBENCH_NAME:
      return cls._CrossbenchExtraTestArgs(benchmark, arguments)

    extra_test_args = []

    if benchmark in _WATERFALL_ENABLED_GTEST_NAMES:
      # crbug/1146949
      # Pass the correct arguments to run gtests on pinpoint.
      # As we don't want to add dependency to chromium, the names of gtests are
      # hard coded here, instead of loading from bot_platforms.py.
      extra_test_args += ('--gtest-benchmark-name', benchmark)
      extra_test_args += ('--non-telemetry', 'true')
      extra_test_args.extend(_WATERFALL_ENABLED_GTEST_NAMES[benchmark])
    else:
      # If we're running a single test,
      # do so even if it's configured to be ignored in expectations.config.
      if not arguments.get('story_tags'):
        extra_test_args.append('-d')

      extra_test_args += ('--benchmarks', benchmark)

    story = arguments.get('story')
    if story:
      # TODO(crbug.com/982027): Note that usage of  "--story-filter" may be
      # replaced with --story=<story> (no regex needed). Support for --story
      # flag landed in
      # https://chromium-review.googlesource.com/c/catapult/+/1869800 (Oct 22,
      # 2019) so we cannot turn this on by default until we no longer need to be
      # able to run revisions older than that.
      extra_test_args += ('--story-filter', _StoryToRegex(story))

    story_tags = arguments.get('story_tags')
    if story_tags:
      extra_test_args += ('--story-tag-filter', story_tags)

    extra_test_args += ('--pageset-repeat', '1')

    browser = arguments.get('browser')
    if not browser:
      raise TypeError('Missing "browser" argument.')
    extra_test_args += ('--browser', browser)
    extra_test_args += _DEFAULT_EXTRA_ARGS
    extra_test_args += super(RunTelemetryTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args

  @classmethod
  def _GetSwarmingTags(cls, arguments):
    tags = {}
    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')
    tags['benchmark'] = benchmark
    story_filter = arguments.get('story')
    tag_filter = arguments.get('story_tags')
    tags['hasfilter'] = '1' if story_filter or tag_filter else '0'
    if story_filter:
      tags['storyfilter'] = story_filter
    if tag_filter:
      tags['tagfilter'] = tag_filter
    return tags
