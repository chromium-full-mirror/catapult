# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# type-hint gets caught by pylint
def GetAndroidTarget(bot_name, err):
  """Return Android Target according to bot_name

  bot_name: string of bot_name (configuration)
  err: Exception, to throw when there's a missing definition

  Returns:
    string of the isolate target.
    defaults to performance_test_suite for non android targets.
  """
  # Each Android binary has its own target, and different bots use different
  # binaries. Mapping based off of Chromium's
  # //tools/perf/core/perf_data_generator.py
  if bot_name.lower().startswith('android-go'):
    return 'performance_test_suite_android_trichrome_chrome_google_bundle'
  if bot_name.lower().startswith('android-pixel'):
    return 'performance_test_suite_android_trichrome_chrome_google_64_32_bundle'
  if 'android' in bot_name.lower():
    raise err

  return 'performance_test_suite'
